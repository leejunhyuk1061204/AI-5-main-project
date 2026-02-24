# ai/scripts/audio/train_audio_v3.py
"""
[파일 용도] 통합 멀티태스크 오디오 학습 도구 v3 (Option A)

[Core Architecture]
- 1-Call 2-Outputs: 하나의 모델이 두 가지를 동시에 예측 (Multi-Task Learning)
  1. sound_type (3-class): start, engine, brake (Inference시 Confidence에 따라 other 추가)
  2. is_abnormal (binary): 0 (Normal), 1 (Abnormal)

[Evaluation Style: Option A]
- Anomaly Detection (Step 1)은 전체 데이터에 대해 수행.
- Sound Type Classification (Step 2)은 Ground Truth가 '비정상'인 데이터에 대해서만 지표 계산.
- 'other'는 지표(Metrics) 계산에서 제외하되, Confusion Matrix에서는 예측 결과로 표시.

[Usage]
python ai/scripts/audio/train_audio_v3.py --arch cnn --mode baseline
"""

import argparse
import os
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Dict, List, Tuple
from collections import Counter

project_root = str(Path(__file__).parents[3])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
import librosa
import scipy.signal
import concurrent.futures
from transformers import ASTForAudioClassification, ASTFeatureExtractor, Trainer, TrainingArguments, ASTConfig, ASTModel
from datasets import Dataset, disable_caching
from sklearn.metrics import precision_recall_fscore_support, accuracy_score, confusion_matrix, balanced_accuracy_score, classification_report, average_precision_score
from sklearn.model_selection import train_test_split

from ai.app.services.audio.audio_preprocessing import preprocess_array

# =============================================================================
# [설정 & 환경 최적화]
# =============================================================================
def get_device_config():
    """VRAM 용량에 따른 환경 최적화 설정"""
    if torch.cuda.is_available():
        vram_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
        print(f"GPU: {torch.cuda.get_device_name(0)} ({vram_gb:.1f}GB VRAM)", flush=True)
        
        if vram_gb < 12: # Local (RTX 3050 8GB 등)
            return {"batch_size": 4, "gradient_accumulation": 4, "fp16": False}
        else: # RunPod (RTX 4090 24GB 등)
            return {"batch_size": 16, "gradient_accumulation": 1, "fp16": True}
    return {"batch_size": 2, "gradient_accumulation": 8, "fp16": False}

DEFAULT_AST_MODEL = "MIT/ast-finetuned-audioset-10-10-0.4593"
RUNPOD_DATA_PATH = "/workspace/large_data"
LOCAL_DATA_PATH = "./ai/data"
DATA_ROOT = RUNPOD_DATA_PATH if os.path.exists(RUNPOD_DATA_PATH) else LOCAL_DATA_PATH

TRAIN_DATA_DIR = os.path.join(DATA_ROOT, "audio/train")
TEST_DATA_DIR = os.path.join(DATA_ROOT, "audio/test")

# 레이블 정의 (Training: 3-class / Inference logic adds "other")
# output 1: sound_type (3-class) - start, engine, brake
TYPE_LABELS = ["start", "engine", "brake"]
type2id = {l: i for i, l in enumerate(TYPE_LABELS)}
id2type = {i: l for i, l in enumerate(TYPE_LABELS)}

# output 2: is_abnormal (binary) - 0 (정상), 1 (비정상)
ABNORMAL_LABELS = ["normal", "abnormal"]

# Inference threshold for "other" (Unknown abnormality)
OTHER_THRESHOLD = 0.3

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# =============================================================================
# 1. 모델 정의 (Multi-Task)
# =============================================================================

class ConvBlock(nn.Module):
    def __init__(self, in_c, out_c):
        super().__init__()
        self.conv1 = nn.Conv2d(in_c, out_c, kernel_size=3, padding=1, bias=False)
        self.conv2 = nn.Conv2d(out_c, out_c, kernel_size=3, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(out_c)
        self.bn2 = nn.BatchNorm2d(out_c)
        self.pool = nn.AvgPool2d(2)

    def forward(self, x):
        x = F.relu(self.bn1(self.conv1(x)))
        x = F.relu(self.bn2(self.conv2(x)))
        x = self.pool(x)
        return x

class MultiTaskCNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv_blocks = nn.Sequential(
            ConvBlock(1, 64),
            ConvBlock(64, 128),
            ConvBlock(128, 256),
            ConvBlock(256, 512),
            ConvBlock(512, 1024),
            ConvBlock(1024, 2048),
        )
        self.pool = nn.AdaptiveAvgPool2d(1)
        
        # Multi-head
        self.type_head = nn.Linear(2048, 3) # start, engine, brake
        self.abnormal_head = nn.Linear(2048, 1)

    def forward(self, x):
        if x.dim() == 3: x = x.unsqueeze(1)
        x = self.conv_blocks(x)
        x = self.pool(x).view(x.size(0), -1)
        
        t_logits = self.type_head(x)
        a_logits = self.abnormal_head(x).squeeze(-1)
        return t_logits, a_logits

    def load_backbone(self, path=None):
        if path is None: path = "./ai/weights/audio/hybrid_cnn14/cnn14.pt"
        if not os.path.exists(path):
            print(f"⚠️  Backbone 가중치를 찾을 수 없습니다: {path}", flush=True)
            return
            
        try:
            state_dict = torch.load(path, map_location="cpu", weights_only=True)
            if 'model' in state_dict: state_dict = state_dict['model']
            
            model_dict = self.state_dict()
            mapped_dict = {}
            for k, v in state_dict.items():
                new_k = k
                if k.startswith("conv_block"):
                    try:
                        num = int(k.split(".")[0].replace("conv_block", ""))
                        new_k = k.replace(f"conv_block{num}", f"conv_blocks.{num-1}")
                    except: pass
                
                if new_k in model_dict and v.shape == model_dict[new_k].shape:
                    mapped_dict[new_k] = v
            
            model_dict.update(mapped_dict)
            self.load_state_dict(model_dict)
            print(f"✅ CNN14 Backbone 로드 완료 (총 {len(mapped_dict)}개 레이어 로드됨)", flush=True)
        except Exception as e:
            print(f"⚠️  Backbone 로드 실패: {e}", flush=True)

class MultiTaskAST(nn.Module):
    def __init__(self, model_id=DEFAULT_AST_MODEL):
        super().__init__()
        self.ast = ASTModel.from_pretrained(model_id)
        self.type_head = nn.Linear(768, 3)
        self.abnormal_head = nn.Linear(768, 1)

    def forward(self, input_values, **kwargs):
        outputs = self.ast(input_values, **kwargs)
        feat = outputs.last_hidden_state.mean(dim=1)
        
        t_logits = self.type_head(feat)
        a_logits = self.abnormal_head(feat).squeeze(-1)
        return t_logits, a_logits

class MultiTaskPaSST(nn.Module):
    def __init__(self):
        super().__init__()
        try:
            from hear21passt.base import get_basic_model
            self.passt = get_basic_model(mode="all", arch="passt_s_swa_p16_128_ap476")
            self.passt.net.classifier = nn.Identity()
        except:
            print("⚠️  hear21passt library not found. MultiTaskPaSST will not work.", flush=True)
            self.passt = None
        
        self.type_head = nn.Linear(768, 3)
        self.abnormal_head = nn.Linear(768, 1)

    def forward(self, x):
        if self.passt is None: return torch.zeros(x.size(0), 3).to(x.device), torch.zeros(x.size(0)).to(x.device)
        feat = self.passt(x)
        if isinstance(feat, (tuple, list)): feat = feat[1]
        
        t_logits = self.type_head(feat)
        a_logits = self.abnormal_head(feat).squeeze(-1)
        return t_logits, a_logits

class MultiTaskFusion(nn.Module):
    def __init__(self):
        super().__init__()
        self.cnn = MultiTaskCNN()
        self.ast = MultiTaskAST()
        self.type_head = nn.Linear(2048 + 768, 3)
        self.abnormal_head = nn.Linear(2048 + 768, 1)

    def forward(self, input_values, mel_spec):
        with torch.no_grad():
            ast_feat = self.ast.ast(input_values).last_hidden_state.mean(dim=1)
            x = mel_spec.unsqueeze(1) if mel_spec.dim() == 3 else mel_spec
            x = self.cnn.conv_blocks(x)
            cnn_feat = self.cnn.pool(x).view(x.size(0), -1)
        
        feat = torch.cat([ast_feat, cnn_feat], dim=1)
        t_logits = self.type_head(feat)
        a_logits = self.abnormal_head(feat).squeeze(-1)
        return t_logits, a_logits

# =============================================================================
# 2. Utilities
# =============================================================================
def highpass_filter(y, sr, cutoff=50):
    b, a = scipy.signal.butter(4, cutoff, 'highpass', fs=sr)
    return scipy.signal.filtfilt(b, a, y)

def apply_spec_augment(mel, time_mask_max=15, freq_mask_max=8):
    """Reduced intensity SpecAugment to preserve hierarchical features"""
    n_mels, n_steps = mel.shape
    f = np.random.randint(0, freq_mask_max)
    f0 = np.random.randint(0, n_mels - f)
    mel = mel.copy()
    mel[f0:f0+f, :] = 0
    t = np.random.randint(0, time_mask_max)
    t0 = np.random.randint(0, n_steps - t)
    mel[:, t0:t0+t] = 0
    return mel

# =============================================================================
# 3. 데이터 처리
# =============================================================================

def get_data_list(base_dir):
    print(f"Searching for audio files in {base_dir}...", flush=True)
    data_list = []
    normal_dir = os.path.join(base_dir, "normal")
    if os.path.exists(normal_dir):
        for f in os.listdir(normal_dir):
            if f.endswith(".wav"):
                data_list.append({"path": os.path.join(normal_dir, f), "type": "normal", "abnormal": 0})
    
    abnormal_dir = os.path.join(base_dir, "abnormal")
    if os.path.exists(abnormal_dir):
        mapping = {"engine": "engine", "brake": "brake", "starter": "start"}
        for cls, target in mapping.items():
            cls_dir = os.path.join(abnormal_dir, cls)
            if os.path.exists(cls_dir):
                for f in os.listdir(cls_dir):
                    if f.endswith(".wav"):
                        data_list.append({"path": os.path.join(cls_dir, f), "type": target, "abnormal": 1})
    return data_list

def preprocess_item(item, arch=None, fe=None):
    try:
        y, sr = librosa.load(item["path"], sr=16000)
        y = highpass_filter(y, sr, cutoff=50)
        y = y / (np.sqrt(np.mean(y**2)) + 1e-8)
        
        y_proc, _ = preprocess_array(y, sr, label_name="normal" if item["abnormal"] == 0 else "abnormal")
        
        # VAD 등으로 인해 None이 반환된 경우 원본 오디오 사용 (안정성 강화)
        if y_proc is None or len(y_proc) == 0:
            y_proc = y
            
        y_proc = librosa.util.fix_length(y_proc, size=16000*5)
        
        # Mel Spectrogram (CNN용)
        mel = librosa.feature.melspectrogram(y=y_proc, sr=16000, n_mels=128, fmax=8000, power=1.0)
        mel_pcen = librosa.pcen(mel, sr=16000)
        mel_norm = (mel_pcen - mel_pcen.mean()) / (mel_pcen.std() + 1e-6)
        
        # AST/Fusion용 Feature 미리 계산 (학습 루프 속도 향상)
        ast_input = None
        if arch in ["ast", "fusion"] and fe is not None:
            ast_input = fe(y_proc, sampling_rate=16000, return_tensors="pt")["input_values"].squeeze(0)
            
        return {
            "audio": y_proc, 
            "mel": mel_norm, 
            "ast_input": ast_input,
            "type": item["type"], 
            "abnormal": float(item["abnormal"])
        }
    except Exception as e:
        # 파일 로드 실패 시 경로 출력
        print(f"⚠️  [Preprocessing Error] {item['path']}: {e}", flush=True)
        return None

class AudioDataset(torch.utils.data.Dataset):
    def __init__(self, data_list, arch, feature_extractor, is_training=False, desc="Dataset"):
        print(f"🛠️  [{desc}] Processing {len(data_list)} items...", flush=True)
        self.is_training = is_training
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(preprocess_item, item, arch, feature_extractor) for item in data_list]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
            
        self.data = [r for r in results if r is not None]
        print(f"✅ [{desc}] Ready with {len(self.data)} items.", flush=True)

    def __len__(self): return len(self.data)
    def __getitem__(self, idx):
        item = self.data[idx]
        mel = apply_spec_augment(item["mel"]) if self.is_training else item["mel"]
        return {
            "ast_input": item["ast_input"] if item["ast_input"] is not None else torch.zeros(1),
            "mel_input": torch.tensor(mel, dtype=torch.float32),
            "raw_audio": torch.tensor(item["audio"], dtype=torch.float32),
            "type_label": torch.tensor(type2id[item["type"]] if item["type"] in type2id else -100, dtype=torch.long),
            "abnormal_label": torch.tensor(item["abnormal"], dtype=torch.float32)
        }

# =============================================================================
# 4. 학습/평가 루프
# =============================================================================

def train(arch="cnn", epochs=10, batch_size=None, lr=3e-5, mode="train"):
    env_cfg = get_device_config()
    batch_size = batch_size or env_cfg["batch_size"]
    grad_accum = env_cfg["gradient_accumulation"]
    fp16 = env_cfg["fp16"]
    
    print(f"\n🚀 Mode: {mode.upper()} ({arch.upper()})", flush=True)
    fe = ASTFeatureExtractor.from_pretrained(DEFAULT_AST_MODEL)
    
    if arch == "cnn":
        model = MultiTaskCNN().to(device)
        model.load_backbone()
    elif arch == "ast":
        model = MultiTaskAST().to(device)
    elif arch == "passt":
        model = MultiTaskPaSST().to(device)
    else:
        model = MultiTaskFusion().to(device)
        model.cnn.load_backbone()
        
    save_path = f"./ai/weights/audio/v3_{arch}.pt"
    if mode == "baseline":
        epochs = 2
        save_path = f"./ai/weights/audio/v3_{arch}_baseline.pt"
        print(f"\n🔥 [Baseline Training] 모드 (Backbone 미고정 + 2 Epoch 학습)", flush=True)
    
    train_data = get_data_list(TRAIN_DATA_DIR)
    test_data = get_data_list(TEST_DATA_DIR)
    
    # [Priority/User 3] Safer Stratification (Normal/Abnormal + Type)
    strat_labels = [(x['type'] if x['abnormal'] == 1 else 'normal') for x in train_data]
    t_data, v_data = train_test_split(train_data, test_size=0.1, stratify=strat_labels, random_state=42)
    
    # Dataset Creation (with descriptive logging)
    train_ds = AudioDataset(t_data, arch, fe, is_training=True, desc="Train")
    val_ds = AudioDataset(v_data, arch, fe, is_training=False, desc="Valid")
    test_ds = AudioDataset(test_data, arch, fe, is_training=False, desc="Test")
    
    train_loader = torch.utils.data.DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = torch.utils.data.DataLoader(val_ds, batch_size=batch_size)
    test_loader = torch.utils.data.DataLoader(test_ds, batch_size=batch_size)
    
    # [Priority 4] Class Weights 계산 (NaN 방지를 위해 더 강력한 로직 사용)
    class_counts = Counter([x['type'] for x in t_data if x['type'] in TYPE_LABELS])
    print(f"📊 Class counts in training split: {class_counts}", flush=True)
    
    # 만약 어떤 클래스가 0개라면, 가중치를 모두 1로 초기화 (NaN 방지)
    if any(class_counts[l] == 0 for l in TYPE_LABELS):
        print("⚠️  Some classes have 0 counts. Using uniform weights.", flush=True)
        weights = torch.ones(len(TYPE_LABELS), device=device)
    else:
        # User 제안: min_count 기반 가중치
        min_count = min(class_counts.values())
        weights = torch.tensor([
            min_count / (class_counts[l] + 1e-6) for l in TYPE_LABELS
        ], device=device).float()
    
    # 🧪 [LR 분리형 옵티마이저] (backbone: 1e-4, heads: 1e-3)
    # 아키텍처별로 파라미터 그룹 분리
    if arch == "cnn":
        param_groups = [
            {"params": model.conv_blocks.parameters(), "lr": lr}, # Backbone
            {"params": model.type_head.parameters(), "lr": lr * 10},
            {"params": model.abnormal_head.parameters(), "lr": lr * 10},
        ]
    elif arch == "ast":
        param_groups = [
            {"params": model.ast.parameters(), "lr": lr},
            {"params": model.type_head.parameters(), "lr": lr * 10},
            {"params": model.abnormal_head.parameters(), "lr": lr * 10},
        ]
    elif arch == "fusion":
        param_groups = [
            {"params": model.cnn.parameters(), "lr": lr},
            {"params": model.ast.parameters(), "lr": lr},
            {"params": model.type_head.parameters(), "lr": lr * 10},
            {"params": model.abnormal_head.parameters(), "lr": lr * 10},
        ]
    else: # passt
        param_groups = [{"params": model.parameters(), "lr": lr}]
        
    optimizer = torch.optim.AdamW(param_groups)
    criterion_type = nn.CrossEntropyLoss(weight=weights, ignore_index=-100)
    criterion_abn = nn.BCEWithLogitsLoss()
    scaler = torch.amp.GradScaler('cuda', enabled=fp16)
    
    print(f"🔔 Starting Training Loop for {epochs} epochs...", flush=True)
    for epoch in range(epochs):
        model.train()
        total_loss = 0
        optimizer.zero_grad()
        print(f"📁 [Epoch {epoch+1}/{epochs}]", end=" ", flush=True)
        
        for i, batch in enumerate(train_loader):
            with torch.amp.autocast('cuda', enabled=fp16):
                # Labels
                t_lbl = batch["type_label"].to(device)
                a_lbl = batch["abnormal_label"].to(device)
                
                if arch == "cnn": t_log, a_log = model(batch["mel_input"].to(device))
                elif arch == "ast": t_log, a_log = model(batch["ast_input"].to(device))
                elif arch == "passt": t_log, a_log = model(batch["raw_audio"].to(device))
                else: t_log, a_log = model(batch["ast_input"].to(device), batch["mel_input"].to(device))
                
                # [User 1] Gated Type Loss (GT-Abnormal Only)
                is_abn = (a_lbl == 1)
                if is_abn.any():
                    loss_t = criterion_type(t_log[is_abn], t_lbl[is_abn])
                else:
                    loss_t = 0.0
                    
                loss = (loss_t + criterion_abn(a_log, a_lbl)) / grad_accum
            scaler.scale(loss).backward()
            if (i + 1) % grad_accum == 0:
                scaler.step(optimizer); scaler.update(); optimizer.zero_grad()
            
            total_loss += loss.item() * grad_accum
            if (i + 1) % 10 == 0 or (i + 1) == len(train_loader):
                print(f"[{i+1}/{len(train_loader)}]", end=" ", flush=True)
            
        print(f"\n⌛ Validating...", flush=True)
        avg_f1 = evaluate_model(model, val_loader, arch, f"Epoch {epoch+1} Valid")
        print(f"Epoch {epoch+1}/{epochs} | Loss: {total_loss/len(train_loader):.4f} | Val F1: {avg_f1:.4f}", flush=True)
        if avg_f1 > best_f1:
            best_f1 = avg_f1; torch.save(model.state_dict(), save_path)
    
    print("\n🏁 Final Test Evaluation")
    model.load_state_dict(torch.load(save_path))
    evaluate_model(model, test_loader, arch, "Final Test")

def evaluate_model(model, loader, arch, desc):
    model.eval()
    all_tp, all_tl, all_ap, all_al = [], [], [], []
    with torch.no_grad():
        for batch in loader:
            if arch == "cnn": t_log, a_log = model(batch["mel_input"].to(device))
            elif arch == "ast": t_log, a_log = model(batch["ast_input"].to(device))
            elif arch == "passt": t_log, a_log = model(batch["raw_audio"].to(device))
            else: t_log, a_log = model(batch["ast_input"].to(device), batch["mel_input"].to(device))
            
            t_probs = torch.softmax(t_log, dim=1)
            max_p, preds = torch.max(t_probs, dim=1)
            preds_with_other = preds.clone()
            preds_with_other[max_p < OTHER_THRESHOLD] = 3 # other
            
            all_tp.extend(preds_with_other.cpu().numpy())
            all_tl.extend(batch["type_label"].numpy())
            all_ap.extend((torch.sigmoid(a_log) > 0.5).cpu().numpy().astype(int))
            all_al.extend(batch["abnormal_label"].numpy().astype(int))

    # 📋 [Option A Logic]
    abn_f1 = precision_recall_fscore_support(all_al, all_ap, average='binary', zero_division=0)[2]
    
    all_tl_np, all_tp_np = np.array(all_tl), np.array(all_tp)
    mask = (all_tl_np != -100) # GT Abnormal Only
    hier_tl, hier_tp = all_tl_np[mask], all_tp_np[mask]
    
    if len(hier_tl) > 0:
        # [User 2] Corrected Balanced Accuracy Calculation (Exclude 3: other)
        valid_mask = (hier_tp != 3)
        if valid_mask.any():
            balanced_acc = balanced_accuracy_score(hier_tl[valid_mask], hier_tp[valid_mask])
        else:
            balanced_acc = 0.0
            
        acc = accuracy_score(hier_tl, hier_tp)
        p, r, f1, _ = precision_recall_fscore_support(hier_tl, hier_tp, labels=[0, 1, 2], average='macro', zero_division=0)
    else:
        acc = balanced_acc = p = r = f1 = 0
    
    print(f"\n# {'='*60}", flush=True)
    print(f"📊 AUDIO {arch.upper()} HIERARCHICAL PERFORMANCE ({desc})", flush=True)
    print(f"\n## 1️⃣ STEP: Anomaly Detection (Normal vs Abnormal)", flush=True)
    print(f"🟢 Anomaly Detection F1: {abn_f1:.4f}", flush=True)
    print(f"\n## 2️⃣ STEP: Sound Type Classification (Abnormal samples only)", flush=True)
    print(f"💡 [Option A] 'other' is excluded from metrics. (Conf < {OTHER_THRESHOLD*100}% -> other)", flush=True)
    print(f"🔵 Accuracy (Hier)   : {acc:.4f}", flush=True)
    print(f"🟣 Balanced Acc      : {balanced_acc:.4f}", flush=True)
    print(f"🟡 Macro Precision   : {p:.4f}", flush=True)
    print(f"🟠 Macro Recall      : {r:.4f} (결함 유형 식별력)", flush=True)
    print(f"🔴 Macro F1-Score    : {f1:.4f}", flush=True)
    
    if len(hier_tl) > 0:
        print(f"\n[ 상세 결함 유형별 분석 (Classification Report) ]", flush=True)
        print(classification_report(hier_tl, hier_tp, labels=[0, 1, 2], target_names=TYPE_LABELS, zero_division=0), flush=True)
        print(f"\n# [ Confusion Matrix (Including 'Other' predictions) ]", flush=True)
        DISP_LABELS = TYPE_LABELS + ["other"]
        print(f"{'':<10} " + " ".join([f"{l:<8}" for l in DISP_LABELS]), flush=True)
        cm = confusion_matrix(hier_tl, hier_tp, labels=[0, 1, 2, 3])
        for i in range(len(TYPE_LABELS)):
            print(f"{TYPE_LABELS[i]:<10} | " + " ".join([f"{v:<8}" for v in cm[i]]), flush=True)
    print(f"{'='*60}\n", flush=True)
    return (f1 + abn_f1) / 2

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--arch", type=str, default="cnn", choices=["cnn", "ast", "passt", "fusion"])
    parser.add_argument("--mode", type=str, default="baseline", choices=["train", "eval", "baseline"])
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch_size", type=int, default=None)
    parser.add_argument("--lr", type=float, default=3e-5)
    args = parser.parse_args()
    train(args.arch, args.epochs, args.batch_size, args.lr, args.mode)
