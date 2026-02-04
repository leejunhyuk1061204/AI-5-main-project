# ai/scripts/audio/train_audio_hybrid.py
"""
AST + CNN14 Hybrid Ensemble 학습 도구

[아키텍처]
1. AST (Audio Spectrogram Transformer): Global Context 학습
2. CNN14 (from PANNs): Local Texture 학습
3. Late Fusion: 두 모델의 예측을 가중 앙상블

[장점]
- AST가 놓치는 Local 패턴을 CNN이 보완
- CNN이 놓치는 Global Context를 AST가 보완
- Abnormal Recall이 크게 향상되는 경우 많음

[사용법]
python ai/scripts/audio/train_audio_hybrid.py --mode all --epochs 10
"""
import argparse
import os
import sys
from pathlib import Path
import requests

project_root = str(Path(__file__).parents[3])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
import librosa
import concurrent.futures
from functools import partial
from collections import Counter
from transformers import ASTForAudioClassification, ASTFeatureExtractor, Trainer, TrainingArguments
from datasets import Dataset
from sklearn.metrics import precision_recall_fscore_support, accuracy_score, confusion_matrix
from sklearn.model_selection import train_test_split

from ai.app.services.audio.audio_preprocessing import (
    trim_silence_rms, apply_bandpass_filter, calculate_speech_ratio,
    apply_speech_soft_masking, apply_spectral_gating
)

# =============================================================================
# [설정]
# =============================================================================
MODEL_NAME = "MIT/ast-finetuned-audioset-10-10-0.4593"
OUTPUT_DIR = "./ai/runs/audio_hybrid"
SAVE_PATH_AST = "./ai/weights/audio/hybrid_ast"
SAVE_PATH_CNN = "./ai/weights/audio/hybrid_cnn14"
SAVE_PATH_ENSEMBLE = "./ai/weights/audio/hybrid_ensemble"

TRAIN_DATA_DIR = "./ai/data/audio/train"
TEST_DATA_DIR = "./ai/data/audio/test"

LABEL_LIST = ["normal", "engine", "brake", "starter"]
label2id = {label: i for i, label in enumerate(LABEL_LIST)}
id2label = {i: label for i, label in enumerate(LABEL_LIST)}

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
feature_extractor = None

# =============================================================================
# 1. CNN14 모델 정의 (PANNs 스타일 간소화 버전)
# =============================================================================
class ConvBlock(nn.Module):
    def __init__(self, in_channels, out_channels):
        super().__init__()
        self.conv1 = nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1)
        self.conv2 = nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1)
        self.bn1 = nn.BatchNorm2d(out_channels)
        self.bn2 = nn.BatchNorm2d(out_channels)
        self.pool = nn.AvgPool2d(kernel_size=2, stride=2)
        
    def forward(self, x):
        x = F.relu(self.bn1(self.conv1(x)))
        x = F.relu(self.bn2(self.conv2(x)))
        x = self.pool(x)
        return x

class CNN14(nn.Module):
    """
    CNN14 from PANNs (Pretrained Audio Neural Networks)
    Local texture 학습에 강함
    """
    def __init__(self, num_classes=4, in_channels=1):
        super().__init__()
        
        self.conv_blocks = nn.Sequential(
            ConvBlock(in_channels, 64),
            ConvBlock(64, 128),
            ConvBlock(128, 256),
            ConvBlock(256, 512),
            ConvBlock(512, 1024),
            ConvBlock(1024, 2048),
        )
        
        self.fc1 = nn.Linear(2048, 512)
        self.fc2 = nn.Linear(512, num_classes)
        self.dropout = nn.Dropout(0.3)
        
    def forward(self, x):
        # x: (batch, freq, time) -> (batch, 1, freq, time)
        if len(x.shape) == 3:
            x = x.unsqueeze(1)
        
        x = self.conv_blocks(x)
        
        # Global Average Pooling
        x = torch.mean(x, dim=(2, 3))  # (batch, 2048)
        
        x = self.dropout(F.relu(self.fc1(x)))
        x = self.fc2(x)
        return x
    
    def get_features(self, x):
        """앙상블용 feature 추출"""
        if len(x.shape) == 3:
            x = x.unsqueeze(1)
        x = self.conv_blocks(x)
        x = torch.mean(x, dim=(2, 3))
        return x

    def load_pretrained_weights(self):
        """PANNs Cnn14 Pretrained Weights 로드 (Zenodo)"""
        url = "https://zenodo.org/record/3987831/files/Cnn14_16k_mAP%3D0.438.pth?download=1"
        path = Path("ai/weights/audio/Cnn14_16k_mAP=0.438.pth")
        
        if not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)

        if not path.exists():
            print(f"[CNN14] Downloading pretrained weights from {url}...")
            try:
                response = requests.get(url, timeout=30)
                path.write_bytes(response.content)
                print("[CNN14] Download complete.")
            except Exception as e:
                print(f"[CNN14] Download failed: {e}. Starting with random weights.")
                return False

        try:
            print(f"[CNN14] Loading weights from {path}...")
            # PANNs 모델의 레이어 이름과 현재 모델의 레이어 이름이 동일한지 확인
            # 만약 다르면 수동 매핑이나 strict=False 사용
            pretrained_dict = torch.load(path, map_location="cpu")
            if 'model' in pretrained_dict:
                pretrained_dict = pretrained_dict['model']
                
            model_dict = self.state_dict()
            
            # 1. 필터링: 현재 모델에 존재하는 키만 선택 + 출력층(fc2) 제외
            filtered_dict = {
                k: v for k, v in pretrained_dict.items() 
                if k in model_dict and "fc2" not in k and v.shape == model_dict[k].shape
            }
            
            # 2. 업데이트
            model_dict.update(filtered_dict)
            self.load_state_dict(model_dict)
            print(f"[CNN14] Successfully loaded {len(filtered_dict)} layers from pretrained model.")
            return True
        except Exception as e:
            print(f"[CNN14] Weight loading error: {e}. Starting with random weights.")
            return False

# =============================================================================
# 2. Hybrid Ensemble 모델 및 Fusion Head
# =============================================================================
class FusionHead(nn.Module):
    def __init__(self, num_classes=4):
        super().__init__()
        self.head = nn.Sequential(
            nn.LayerNorm(num_classes * 2),
            nn.Dropout(0.3),
            nn.Linear(num_classes * 2, num_classes)
        )

    def forward(self, ast_logits, cnn_logits):
        x = torch.cat([ast_logits, cnn_logits], dim=-1)
        return self.head(x)

class HybridEnsemble(nn.Module):
    """
    AST + CNN14 Fusion Ensemble
    """
    def __init__(self, ast_model, cnn_model, num_classes=4):
        super().__init__()
        self.ast_model = ast_model
        self.cnn_model = cnn_model
        self.fusion_head = FusionHead(num_classes)
        
    def forward(self, ast_input, cnn_input):
        # 1. AST 예측 (Freeze 상태여도 연산은 수행)
        ast_logits = self.ast_model(ast_input).logits
        
        # 2. CNN 예측
        cnn_logits = self.cnn_model(cnn_input)
        
        # 3. Fusion Head를 통한 최종 결정
        return self.fusion_head(ast_logits, cnn_logits)

# =============================================================================
# 3. 데이터 로딩
# =============================================================================
def load_data_from_dir(base_dir):
    data_list = []
    
    normal_dir = os.path.join(base_dir, "normal")
    if os.path.exists(normal_dir):
        for f in os.listdir(normal_dir):
            if f.endswith('.wav'):
                data_list.append({"audio": os.path.join(normal_dir, f), "label": "normal"})
    
    abnormal_dir = os.path.join(base_dir, "abnormal")
    if os.path.exists(abnormal_dir):
        for cls in ["engine", "brake", "starter"]:
            cls_dir = os.path.join(abnormal_dir, cls)
            if os.path.exists(cls_dir):
                for f in os.listdir(cls_dir):
                    if f.endswith(".wav"):
                        data_list.append({"audio": os.path.join(cls_dir, f), "label": cls})
    
    return data_list

def process_audio_for_hybrid(item):
    """AST와 CNN 둘 다를 위한 feature 추출"""
    try:
        y, sr = librosa.load(item["audio"], sr=16000)
        
        # 전처리
        y = trim_silence_rms(y, sr, top_db=50)
        y = apply_bandpass_filter(y, sr)
        speech_ratio, vad_mask = calculate_speech_ratio(y, sr)
        if item["label"] == "normal" and speech_ratio > 0.05:
            y = apply_speech_soft_masking(y, sr, vad_mask)
        y = apply_spectral_gating(y, sr, min_gain=0.2 if item["label"] == "normal" else 0.5)
        
        # RMS Norm
        target_rms = 0.1
        current_rms = np.sqrt(np.mean(y**2)) + 1e-8
        y = y * (target_rms / current_rms)
        
        # CNN용: Mel Spectrogram
        mel_spec = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=128, fmax=8000)
        mel_spec_db = librosa.power_to_db(mel_spec, ref=np.max)
        
        return {
            "audio_array": y,
            "mel_spec": mel_spec_db,
            "label": item["label"],
            "path": item["audio"]
        }
    except Exception as e:
        return {"error": str(e), "path": item["audio"]}

def prepare_hybrid_datasets(data_list, desc="Data"):
    global feature_extractor
    if feature_extractor is None:
        feature_extractor = ASTFeatureExtractor.from_pretrained(MODEL_NAME)
    
    print(f"[Info] {desc} 하이브리드 전처리 중 (총 {len(data_list)}개)...")
    results = []
    
    num_workers = min(os.cpu_count(), 4)
    with concurrent.futures.ProcessPoolExecutor(max_workers=num_workers) as executor:
        futures = list(executor.map(process_audio_for_hybrid, data_list))
        
        for i, res in enumerate(futures):
            if "error" in res:
                print(f"[Error] Failed to process {res.get('path', 'unknown')}: {res['error']}")
                continue
            
            # AST features
            ast_input = feature_extractor(
                res["audio_array"], sampling_rate=16000,
                return_tensors="pt", padding="longest", truncation=True, max_length=1024
            )["input_values"].squeeze(0).numpy()
            
            # CNN features (mel spec)
            mel_spec = res["mel_spec"]
            # 패딩/자르기로 고정 크기 (128, 256)
            target_len = 256
            if mel_spec.shape[1] < target_len:
                mel_spec = np.pad(mel_spec, ((0, 0), (0, target_len - mel_spec.shape[1])))
            else:
                mel_spec = mel_spec[:, :target_len]
            
            results.append({
                "ast_input": ast_input,
                "cnn_input": mel_spec.astype(np.float32),
                "labels": label2id[res["label"]]
            })
            
            if (i + 1) % 100 == 0:
                print(f"  > {desc}: {i+1}/{len(data_list)}")
    
    return results

# =============================================================================
# 4. 학습 함수들
# =============================================================================
def train_cnn14(train_data, test_data, epochs=10):
    """CNN14 독립 학습"""
    print("\n" + "="*60)
    print("[CNN14] Local Texture 모델 학습")
    print("="*60)
    
    t_data, v_data = train_test_split(train_data, test_size=0.1, 
        stratify=[x['label'] for x in train_data], random_state=42)
    
    train_results = prepare_hybrid_datasets(t_data, "Train(CNN)")
    val_results = prepare_hybrid_datasets(v_data, "Valid(CNN)")
    test_results = prepare_hybrid_datasets(test_data, "Test(CNN)")
    
    # DataLoader 생성
    train_cnn = [(torch.tensor(r["cnn_input"]), r["labels"]) for r in train_results]
    val_cnn = [(torch.tensor(r["cnn_input"]), r["labels"]) for r in val_results]
    test_cnn = [(torch.tensor(r["cnn_input"]), r["labels"]) for r in test_results]
    
    train_loader = torch.utils.data.DataLoader(train_cnn, batch_size=16, shuffle=True)
    val_loader = torch.utils.data.DataLoader(val_cnn, batch_size=16)
    test_loader = torch.utils.data.DataLoader(test_cnn, batch_size=16)
    
    # 모델
    model = CNN14(num_classes=len(LABEL_LIST)).to(device)
    
    # Pretrained Weights 로드 시도
    model.load_pretrained_weights()
    
    # 클래스 가중치
    labels = [x['label'] for x in train_data]
    counts = [labels.count(l) for l in LABEL_LIST]
    weights = torch.tensor([sum(counts) / (len(LABEL_LIST) * c + 1e-8) for c in counts], 
                          dtype=torch.float).to(device)
    
    criterion = nn.CrossEntropyLoss(weight=weights)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    
    best_f1 = 0
    for epoch in range(epochs):
        model.train()
        total_loss = 0
        for batch_x, batch_y in train_loader:
            batch_x, batch_y = batch_x.to(device), torch.tensor(batch_y).to(device)
            
            optimizer.zero_grad()
            outputs = model(batch_x)
            loss = criterion(outputs, batch_y)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
        
        scheduler.step()
        
        # Validation
        model.eval()
        all_preds, all_labels = [], []
        with torch.no_grad():
            for batch_x, batch_y in val_loader:
                batch_x = batch_x.to(device)
                outputs = model(batch_x)
                preds = torch.argmax(outputs, dim=-1).cpu().numpy()
                all_preds.extend(preds)
                all_labels.extend(batch_y)
        
        _, _, f1, _ = precision_recall_fscore_support(all_labels, all_preds, average='macro')
        print(f"[Epoch {epoch+1}/{epochs}] Loss: {total_loss/len(train_loader):.4f}, Val F1: {f1:.4f}")
        
        if f1 > best_f1:
            best_f1 = f1
            os.makedirs(SAVE_PATH_CNN, exist_ok=True)
            torch.save(model.state_dict(), os.path.join(SAVE_PATH_CNN, "cnn14.pt"))
    
    # Test 평가
    model.load_state_dict(torch.load(os.path.join(SAVE_PATH_CNN, "cnn14.pt")))
    model.eval()
    all_preds, all_labels = [], []
    with torch.no_grad():
        for batch_x, batch_y in test_loader:
            batch_x = batch_x.to(device)
            outputs = model(batch_x)
            preds = torch.argmax(outputs, dim=-1).cpu().numpy()
            all_preds.extend(preds)
            all_labels.extend(batch_y)
    
    print(f"\n📊 CNN14 Test 결과:")
    print(f" - Accuracy: {accuracy_score(all_labels, all_preds):.4f}")
    p, r, f1, _ = precision_recall_fscore_support(all_labels, all_preds, average='macro')
    print(f" - Macro F1: {f1:.4f}, Recall: {r:.4f}")
    
    return model

def train_ast(train_data, test_data, epochs=10):
    """AST 독립 학습 (기존 로직 재사용)"""
    print("\n" + "="*60)
    print("[AST] Global Context 모델 학습")
    print("="*60)
    
    global feature_extractor
    if feature_extractor is None:
        feature_extractor = ASTFeatureExtractor.from_pretrained(MODEL_NAME)
    
    t_data, v_data = train_test_split(train_data, test_size=0.1,
        stratify=[x['label'] for x in train_data], random_state=42)
    
    hybrid_train = prepare_hybrid_datasets(t_data, "Train(AST)")
    hybrid_val = prepare_hybrid_datasets(v_data, "Valid(AST)")
    hybrid_test = prepare_hybrid_datasets(test_data, "Test(AST)")
    
    # AST용 Dataset
    train_ds = Dataset.from_list([{"input_values": r["ast_input"], "labels": r["labels"]} for r in hybrid_train])
    val_ds = Dataset.from_list([{"input_values": r["ast_input"], "labels": r["labels"]} for r in hybrid_val])
    test_ds = Dataset.from_list([{"input_values": r["ast_input"], "labels": r["labels"]} for r in hybrid_test])
    
    for ds in [train_ds, val_ds, test_ds]:
        ds.set_format(type="torch", columns=["input_values", "labels"])
    
    # 클래스 가중치
    labels = [x['label'] for x in train_data]
    counts = [labels.count(l) for l in LABEL_LIST]
    weights = torch.tensor([sum(counts) / (len(LABEL_LIST) * c + 1e-8) for c in counts], dtype=torch.float)
    
    model = ASTForAudioClassification.from_pretrained(
        MODEL_NAME, num_labels=len(LABEL_LIST),
        label2id=label2id, id2label=id2label,
        ignore_mismatched_sizes=True
    ).to(device)
    
    class WeightedTrainer(Trainer):
        def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
            labels = inputs.get("labels")
            outputs = model(**inputs)
            loss_fct = nn.CrossEntropyLoss(weight=weights.to(model.device))
            loss = loss_fct(outputs.logits.view(-1, len(LABEL_LIST)), labels.view(-1))
            return (loss, outputs) if return_outputs else loss
    
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        per_device_train_batch_size=8,
        num_train_epochs=epochs,
        learning_rate=3e-5,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="recall",
        greater_is_better=True,
        fp16=torch.cuda.is_available(),
    )
    
    def compute_metrics(eval_pred):
        preds = np.argmax(eval_pred.predictions, axis=-1)
        labels = eval_pred.label_ids
        p, r, f1, _ = precision_recall_fscore_support(labels, preds, average='macro')
        return {"accuracy": accuracy_score(labels, preds), "f1": f1, "precision": p, "recall": r}
    
    trainer = WeightedTrainer(model=model, args=training_args, train_dataset=train_ds, 
                              eval_dataset=val_ds, compute_metrics=compute_metrics)
    trainer.train()
    
    os.makedirs(SAVE_PATH_AST, exist_ok=True)
    model.save_pretrained(SAVE_PATH_AST)
    feature_extractor.save_pretrained(SAVE_PATH_AST)
    
    # Test
    results = trainer.predict(test_ds)
    preds = np.argmax(results.predictions, axis=-1)
    labels = results.label_ids
    
    print(f"\n📊 AST Test 결과:")
    print(f" - Accuracy: {accuracy_score(labels, preds):.4f}")
    p, r, f1, _ = precision_recall_fscore_support(labels, preds, average='macro')
    print(f" - Macro F1: {f1:.4f}, Recall: {r:.4f}")
    
    return model

def train_fusion(train_data, test_data, epochs=10):
    """Fusion Head만 집중 학습 (Backbones Frozen)"""
    print("\n" + "="*60)
    print("[Fusion] Fusion Head 학습 (AST/CNN Frozen)")
    print("="*60)
    
    # 1. 모델 로드 및 Freeze
    ast_model = ASTForAudioClassification.from_pretrained(SAVE_PATH_AST).to(device)
    cnn_model = CNN14(num_classes=len(LABEL_LIST)).to(device)
    cnn_model.load_state_dict(torch.load(os.path.join(SAVE_PATH_CNN, "cnn14.pt")))
    
    for param in ast_model.parameters():
        param.requires_grad = False
    for param in cnn_model.parameters():
        param.requires_grad = False
        
    model = HybridEnsemble(ast_model, cnn_model, num_classes=len(LABEL_LIST)).to(device)
    
    # 2. 데이터 준비
    t_data, v_data = train_test_split(train_data, test_size=0.1, 
        stratify=[x['label'] for x in train_data], random_state=42)
    
    train_results = prepare_hybrid_datasets(t_data, "Train(Fusion)")
    val_results = prepare_hybrid_datasets(v_data, "Valid(Fusion)")
    test_results = prepare_hybrid_datasets(test_data, "Test(Fusion)")
    
    def create_loader(results, shuffle=False):
        data = [
            (torch.tensor(r["ast_input"]), torch.tensor(r["cnn_input"]), r["labels"]) 
            for r in results
        ]
        return torch.utils.data.DataLoader(data, batch_size=16, shuffle=shuffle)
    
    train_loader = create_loader(train_results, shuffle=True)
    val_loader = create_loader(val_results)
    test_loader = create_loader(test_results)
    
    # 3. 설정 (AdamW 1e-3, Weighted CrossEntropy)
    labels = [x['label'] for x in train_data]
    counts = [labels.count(l) for l in LABEL_LIST]
    weights = torch.tensor([sum(counts) / (len(LABEL_LIST) * c + 1e-8) for c in counts], 
                          dtype=torch.float).to(device)
    
    # [Tip] 혼동이 심한 Brake(2), Engine(1) 가중치 추가 보정
    weights[1] *= 1.2 
    weights[2] *= 1.5
    
    criterion = nn.CrossEntropyLoss(weight=weights)
    
    # [1단계] Fusion Head 집중 학습 (Frozen Backbones)
    print("\n>>> Stage 1: Training Fusion Head (Backbones Frozen)")
    optimizer = torch.optim.AdamW(model.fusion_head.parameters(), lr=1e-3)
    
    best_f1 = 0
    for epoch in range(epochs):
        model.train()
        total_loss = 0
        for b_ast, b_cnn, b_y in train_loader:
            b_ast, b_cnn, b_y = b_ast.to(device), b_cnn.to(device), b_y.to(device)
            
            optimizer.zero_grad()
            outputs = model(b_ast, b_cnn)
            loss = criterion(outputs, b_y)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
            
        # Eval
        model.eval()
        all_preds, all_labels = [], []
        with torch.no_grad():
            for b_ast, b_cnn, b_y in val_loader:
                outputs = model(b_ast.to(device), b_cnn.to(device))
                preds = torch.argmax(outputs, dim=-1).cpu().numpy()
                all_preds.extend(preds)
                all_labels.extend(b_y.numpy())
        
        _, _, f1, _ = precision_recall_fscore_support(all_labels, all_preds, average='macro')
        print(f"[Epoch {epoch+1}/{epochs}] Loss: {total_loss/len(train_loader):.4f}, Val F1: {f1:.4f}")
        
        if f1 > best_f1:
            best_f1 = f1
            os.makedirs(SAVE_PATH_ENSEMBLE, exist_ok=True)
            torch.save(model.state_dict(), os.path.join(SAVE_PATH_ENSEMBLE, "hybrid_fusion.pt"))

    # [2단계] 전체 모델 미세 조정 (Unfreeze Backbones)
    print("\n>>> Stage 2: Fine-tuning Full Model (Unfreezing Backbones)")
    for param in model.parameters():
        param.requires_grad = True
    
    # 훨씬 낮은 학습률로 조심스럽게 학습
    optimizer = torch.optim.AdamW(model.parameters(), lr=5e-6) 
    
    for epoch in range(5): # 추가 5에폭 미세조정
        model.train()
        total_loss = 0
        for b_ast, b_cnn, b_y in train_loader:
            b_ast, b_cnn, b_y = b_ast.to(device), b_cnn.to(device), b_y.to(device)
            optimizer.zero_grad()
            outputs = model(b_ast, b_cnn)
            loss = criterion(outputs, b_y)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
            
        model.eval()
        all_preds, all_labels = [], []
        with torch.no_grad():
            for b_ast, b_cnn, b_y in val_loader:
                outputs = model(b_ast.to(device), b_cnn.to(device))
                preds = torch.argmax(outputs, dim=-1).cpu().numpy()
                all_preds.extend(preds)
                all_labels.extend(b_y.numpy())
        
        _, _, f1, _ = precision_recall_fscore_support(all_labels, all_preds, average='macro', zero_division=0)
        print(f"[Fine-tune {epoch+1}/5] Loss: {total_loss/len(train_loader):.4f}, Val F1: {f1:.4f}")
        
        if f1 >= best_f1:
            best_f1 = f1
            torch.save(model.state_dict(), os.path.join(SAVE_PATH_ENSEMBLE, "hybrid_fusion_final.pt"))
            
    # 4. 최종 평가
    final_model_path = os.path.join(SAVE_PATH_ENSEMBLE, "hybrid_fusion_final.pt")
    if not os.path.exists(final_model_path): # 2단계에서 개선 안 된 경우 1단계 모델 사용
        final_model_path = os.path.join(SAVE_PATH_ENSEMBLE, "hybrid_fusion.pt")
        
    model.load_state_dict(torch.load(final_model_path))
    model.eval()
    all_preds, all_labels = [], []
    with torch.no_grad():
        for b_ast, b_cnn, b_y in test_loader:
            outputs = model(b_ast.to(device), b_cnn.to(device))
            preds = torch.argmax(outputs, dim=-1).cpu().numpy()
            all_preds.extend(preds)
            all_labels.extend(b_y.numpy())
            
    print(f"\n📊 Hybrid Fusion 최종 성적표:")
    print(f"{'-'*40}")
    print(f" - 전체 정확도 (Accuracy): {accuracy_score(all_labels, all_preds):.4f}")
    p, r, f1, _ = precision_recall_fscore_support(all_labels, all_preds, average='macro', zero_division=0)
    print(f" - 균형 지표 (Macro F1):  {f1:.4f}")
    print(f" - 검출 재현율 (Recall):  {r:.4f}")
    print(f"{'-'*40}")
    
    cm = confusion_matrix(all_labels, all_preds)
    print(f"\n🖼️ Confusion Matrix (행: 정답, 열: 예측):")
    print(f"{'':>10} | {'Normal':>8} {'Engine':>8} {'Brake':>8} {'Starter':>8}")
    print(f"{'-'*50}")
    for i, row in enumerate(cm):
        row_int = [int(val) for val in row]
        print(f"{LABEL_LIST[i]:>10} | {row_int[0]:>8} {row_int[1]:>8} {row_int[2]:>8} {row_int[3]:>8}")

def evaluate_ensemble(test_data):
    """앙상블 평가 (Fusion 모델 로드)"""
    print("\n" + "="*60)
    print("[Ensemble] Hybrid Fusion 모델 평가")
    print("="*60)
    
    # 모델 로드
    ast_model = ASTForAudioClassification.from_pretrained(SAVE_PATH_AST).to(device)
    cnn_model = CNN14(num_classes=len(LABEL_LIST)).to(device)
    cnn_model.load_state_dict(torch.load(os.path.join(SAVE_PATH_CNN, "cnn14.pt")))
    
    model = HybridEnsemble(ast_model, cnn_model, num_classes=len(LABEL_LIST)).to(device)
    model.load_state_dict(torch.load(os.path.join(SAVE_PATH_ENSEMBLE, "hybrid_fusion.pt")))
    model.eval()
    
    # 데이터 준비
    test_results = prepare_hybrid_datasets(test_data, "Test(Ensemble)")
    
    all_preds, all_labels = [], []
    
    with torch.no_grad():
        for r in test_results:
            ast_input = torch.tensor(r["ast_input"]).unsqueeze(0).to(device)
            cnn_input = torch.tensor(r["cnn_input"]).unsqueeze(0).to(device)
            
            outputs = model(ast_input, cnn_input)
            pred = torch.argmax(outputs, dim=-1).cpu().item()
            
            all_preds.append(pred)
            all_labels.append(r["labels"])
    
    print(f"\n🚀 앙상블 Test 결과:")
    print(f" - Accuracy: {accuracy_score(all_labels, all_preds):.4f}")
    p, r, f1, _ = precision_recall_fscore_support(all_labels, all_preds, average='macro')
    print(f" - Macro F1: {f1:.4f}")
    print(f" - Macro Recall: {r:.4f}")
    
    cm = confusion_matrix(all_labels, all_preds)
    print(f"\n🖼️ Confusion Matrix:")
    print(f"   Labels: {LABEL_LIST}")
    for i, row in enumerate(cm):
        print(f"   {LABEL_LIST[i]:>8}: {list(row)}")

# =============================================================================
# 5. Baseline 평가
# =============================================================================
def evaluate_baseline(test_data):
    """
    Pre-trained AST 모델의 Baseline 성능 평가
    """
    print("\n" + "="*60)
    print("[Baseline] Pre-trained AST 모델 평가 (Hybrid 관점)")
    print("="*60)
    print("""
[Baseline 정의]
1. Model: MIT/ast-finetuned-audioset (Pre-trained, No Fine-tuning)
2. Data: Test set only
3. Note: AudioSet에 engine/brake/starter가 없어 성능이 낮을 수 있음
""")
    
    global feature_extractor
    if feature_extractor is None:
        feature_extractor = ASTFeatureExtractor.from_pretrained(MODEL_NAME)
    
    test_results = prepare_hybrid_datasets(test_data, "Test(Baseline)")
    
    test_ds = Dataset.from_list([{"input_values": r["ast_input"], "labels": r["labels"]} for r in test_results])
    test_ds.set_format(type="torch", columns=["input_values", "labels"])
    
    model = ASTForAudioClassification.from_pretrained(
        MODEL_NAME, num_labels=len(LABEL_LIST),
        label2id=label2id, id2label=id2label,
        ignore_mismatched_sizes=True
    ).to(device)
    
    trainer = Trainer(model=model)
    results = trainer.predict(test_ds)
    preds = np.argmax(results.predictions, axis=-1)
    labels = results.label_ids
    
    print(f"\n📊 Baseline 결과 (4-class: normal/engine/brake/starter):")
    print(f" - Accuracy: {accuracy_score(labels, preds):.4f}")
    p, r, f1, _ = precision_recall_fscore_support(labels, preds, average='macro')
    print(f" - Macro F1: {f1:.4f}")
    print(f" - Macro Recall: {r:.4f}")
    
    cm = confusion_matrix(labels, preds)
    print(f"\n🖼️ Confusion Matrix:")
    print(f"   Labels: {LABEL_LIST}")
    for i, row in enumerate(cm):
        print(f"   {LABEL_LIST[i]:>8}: {list(row)}")
    
    print("\n[⚠️ 참고] Baseline이 낮으면 정상입니다. Fine-tuning 후 성능이 올라갑니다.")

# =============================================================================
# Main
# =============================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", type=str, default="all", choices=["baseline", "ast", "cnn", "fusion", "ensemble", "all"])
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--ast-weight", type=float, default=0.6, help="AST 가중치 (0~1)")
    args = parser.parse_args()
    
    print(f"[Info] 디바이스: {device}")
    
    train_data = load_data_from_dir(TRAIN_DATA_DIR)
    test_data = load_data_from_dir(TEST_DATA_DIR)
    
    print(f"[Sanity Check] Train: {dict(Counter([x['label'] for x in train_data]))}")
    print(f"[Sanity Check] Test: {dict(Counter([x['label'] for x in test_data]))}")
    
    if args.mode == "baseline":
        evaluate_baseline(test_data)
    elif args.mode == "ast":
        train_ast(train_data, test_data, args.epochs)
    elif args.mode == "cnn":
        train_cnn14(train_data, test_data, args.epochs)
    elif args.mode == "ensemble":
        evaluate_ensemble(test_data)
    elif args.mode == "fusion":
        train_fusion(train_data, test_data, args.epochs)
    elif args.mode == "all":
        train_ast(train_data, test_data, args.epochs)
        train_cnn14(train_data, test_data, args.epochs)
        train_fusion(train_data, test_data, args.epochs)
    
    print("\n✅ 완료!")
