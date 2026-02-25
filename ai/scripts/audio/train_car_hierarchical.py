# ai/scripts/audio/train_car_hierarchical.py
"""
[계층적 파이프라인] Multi-Model Hierarchical Car Domain & Diagnostic MoE
- Stage 1: Domain Filter (Binary: Car Sound vs Non-Car OOD)
- Stage 2: Diagnostic MoE (Binary: Normal vs Abnormal with Domain Experts)
- Support Backbones: AST, CNN14 (PANNs), PaSST
- Optimizations: Entropy Loss, Temperature Scaling, Balanced Sampler, Weight Inheritance, Freezing
"""
import os
import sys
import argparse
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler
from transformers import ASTModel, ASTFeatureExtractor
import numpy as np
from sklearn.metrics import classification_report, f1_score
from pathlib import Path
from peft import LoraConfig, get_peft_model
from collections import Counter
import librosa
import torchaudio


# 프로젝트 루트 추가
project_root = str(Path(__file__).resolve().parent.parent.parent.parent)
if project_root not in sys.path:
    sys.path.append(project_root)


from ai.scripts.audio.config import (
    COMMON_CONFIG, DEVICE, set_seed, EarlyStopping
)


set_seed(42)


# Path Constants
CAR_DATASET_ROOT = os.path.join(project_root, "ai/data/car_dataset_cls")
OOD_NOISE_DIR = os.path.join(project_root, "ai/data/audio/noises")
DEFAULT_AST_MODEL = "MIT/ast-finetuned-audioset-10-10-0.4593"
DEFAULT_PASST_MODEL = "passt_s_p16_s16_128_ap468"


# =============================================================================
# 0. 데이터셋 정의
# =============================================================================


class HierarchicalDS(Dataset):
    def __init__(self, data_list, model_type="ast"):
        self.data = data_list
        self.model_type = model_type
        if model_type == "ast":
            self.fe = ASTFeatureExtractor.from_pretrained(DEFAULT_AST_MODEL)
            self.sr = 16000
        elif model_type == "passt":
            self.sr = 32000 # PaSST usually uses 32k
        else: # cnn14
            self.sr = 16000


    def __len__(self):
        return len(self.data)


    def __getitem__(self, idx):
        item = self.data[idx]
        wav, _ = librosa.load(item["path"], sr=self.sr)
        target_samples = self.sr * 5
       
        if len(wav) > target_samples:
            start = np.random.randint(0, len(wav) - target_samples)
            wav = wav[start:start+target_samples]
        elif len(wav) < target_samples:
            wav = np.pad(wav, (0, target_samples - len(wav)))
           
        if self.model_type == "ast":
            inputs = self.fe(wav, sampling_rate=16000, return_tensors="pt")
            x = inputs["input_values"].squeeze(0)
        else:
            x = torch.tensor(wav, dtype=torch.float32)
       
        return {
            "input": x,
            "label": torch.tensor(item["label"], dtype=torch.long),
            "domain": torch.tensor(item.get("domain", -1), dtype=torch.long)
        }


def get_hierarchical_data(stage, split="train"):
    """
    ai/data/car_dataset_cls/{split}/{domain}/{label-folder} 구조에서 데이터 로드
    split: 'train', 'val', 'test' 중 하나
    """
    data = []
    split_root = os.path.join(CAR_DATASET_ROOT, split)
    
    if stage == 1:
        # 1단계용 로직: 현재는 OOD 데이터가 car_dataset_cls 내부에 없으므로 
        # Car 클래스는 car_dataset_cls/{split} 전체에서 가져오고 OOD는 기존 노이즈 폴더 사용
        if os.path.exists(split_root):
            for root, _, files in os.walk(split_root):
                for f in files:
                    if f.endswith(".wav"):
                        data.append({"path": os.path.join(root, f), "label": 0}) # 0: Car
       
        if os.path.exists(OOD_NOISE_DIR):
            for root, _, files in os.walk(OOD_NOISE_DIR):
                for f in files:
                    if f.endswith(".wav"):
                        data.append({"path": os.path.join(root, f), "label": 1}) # 1: Non-Car
    else:
        # 2단계용 로직: Normal(0) vs Abnormal(1)
        mapping = {
            "startup state": 0, # Starter
            "idle state": 1,    # Engine
            "braking state": 2  # Brake
        }
        for state_dir, domain_id in mapping.items():
            state_path = os.path.join(split_root, state_dir)
            if not os.path.exists(state_path): continue
           
            for label_name, label_id in [("normal", 0), ("abnormal", 1)]:
                full_path = os.path.join(state_path, label_name)
                if not os.path.exists(full_path): continue
                
                for f in os.listdir(full_path):
                    if f.endswith(".wav"):
                        data.append({
                            "path": os.path.join(full_path, f),
                            "label": label_id,
                            "domain": domain_id
                        })
    return data


def get_external_test_data(new_only=False):
    """로드: ai/data/audio/train/abnormal/* 및 ai/data/audio/test/normal,abnormal/*"""
    data = []
    
    # 1. 경로 설정 (Abnormal, Normal)
    abnormal_dirs = []
    normal_dirs = []
    
    if not new_only:
        abnormal_dirs.append(os.path.join(project_root, "ai/data/audio/train/abnormal"))
    
    abnormal_dirs.append(os.path.join(project_root, "ai/data/audio/test/abnormal"))
    normal_dirs.append(os.path.join(project_root, "ai/data/audio/test/normal"))
   
    mapping = {"starter": 0, "engine": 1, "brake": 2}
   
    # 2. Abnormal 로드 (Label 1)
    for base_path in abnormal_dirs:
        if not os.path.exists(base_path): continue
        for sub, domain_id in mapping.items():
            full_p = os.path.join(base_path, sub)
            if not os.path.exists(full_p): continue
            for f in os.listdir(full_p):
                if f.endswith(".wav"):
                    data.append({
                        "path": os.path.join(full_p, f),
                        "label": 1,
                        "domain": domain_id,
                        "type": "abnormal"
                    })
                    
    # 3. Normal 로드 (Label 0)
    for base_path in normal_dirs:
        if not os.path.exists(base_path): continue
        for sub, domain_id in mapping.items():
            full_p = os.path.join(base_path, sub)
            if not os.path.exists(full_p): continue
            for f in os.listdir(full_p):
                if f.endswith(".wav"):
                    data.append({
                        "path": os.path.join(full_p, f),
                        "label": 0,
                        "domain": domain_id,
                        "type": "normal"
                    })
                    
    return data


# =============================================================================
# 1. 모델 아키텍처
# =============================================================================


class DiagnosticExpert(nn.Module):
    def __init__(self, input_dim, expert_id):
        super().__init__()
        hidden_dim = [192, 256, 320][expert_id]
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.BatchNorm1d(hidden_dim),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim, 2)
        )
        with torch.no_grad():
            self.net[-1].weight.data += expert_id * 0.1


    def forward(self, x):
        return self.net(x)


class CNN14Block(nn.Module):
    def __init__(self, in_c, out_c):
        super().__init__()
        self.conv1 = nn.Conv2d(in_c, out_c, kernel_size=3, padding=1, bias=False)
        self.conv2 = nn.Conv2d(out_c, out_c, kernel_size=3, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(out_c)
        self.bn2 = nn.BatchNorm2d(out_c)


    def forward(self, x):
        x = F.relu(self.bn1(self.conv1(x)))
        x = F.relu(self.bn2(self.conv2(x)))
        x = F.avg_pool2d(x, kernel_size=2, stride=2)
        return x


class CNN14Backbone(nn.Module):
    """PANNs CNN14 Architecture (16k)"""
    def __init__(self):
        super().__init__()
        self.conv_blocks = nn.Sequential(
            CNN14Block(1, 64),
            CNN14Block(64, 128),
            CNN14Block(128, 256),
            CNN14Block(256, 512),
            CNN14Block(512, 1024),
            CNN14Block(1024, 2048) # Correct PANNs has 6 blocks, but often 5 is used for 16k
        )
        self.fc_feat = nn.Linear(2048, 2048)
        self.mel = torchaudio.transforms.MelSpectrogram(
            sample_rate=16000, n_fft=1024, win_length=1024, hop_length=400, n_mels=64
        )
        self.amplitude_to_db = torchaudio.transforms.AmplitudeToDB()


    def forward(self, x):
        if x.dim() == 2: x = x.unsqueeze(1) # [B, 1, T]
        m = self.mel(x) # [B, 1, 64, T']
        # Numerical Stability: log scaling instead of AmplitudeToDB
        m = torch.log(m + 1e-6)
        x = self.conv_blocks(m)
        x = torch.mean(x, dim=(2, 3)) # GAP -> [B, 2048]
        x = F.relu(self.fc_feat(x))
        # NaN Guard
        if torch.isnan(x).any():
            x = torch.where(torch.isnan(x), torch.zeros_like(x), x)
        return x


    def load_pretrained_weights(self):
        import requests
        url = "https://zenodo.org/record/3987831/files/Cnn14_16k_mAP%3D0.438.pth?download=1"
        path = Path("ai/weights/audio/Cnn14_16k_mAP=0.438.pth")
        if not path.parent.exists(): path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            print(f"📥 [CNN14] Downloading pretrained weights to {path}...", flush=True)
            try:
                r = requests.get(url, timeout=120)
                path.write_bytes(r.content)
            except Exception as e:
                print(f"❌ Download failed: {e}")
                return False
       
        try:
            ckpt = torch.load(path, map_location="cpu", weights_only=False)
            state_dict = ckpt['model'] if 'model' in ckpt else ckpt
            model_dict = self.state_dict()
            mapped = {}
            for k, v in state_dict.items():
                new_k = k
                # PANNs: conv_block1.conv1.weight -> conv_blocks.0.conv1.weight
                if k.startswith("conv_block"):
                    try:
                        num = int(k.split(".")[0].replace("conv_block", ""))
                        new_k = k.replace(f"conv_block{num}", f"conv_blocks.{num-1}")
                    except: pass
                # Map fc1 to fc_feat
                if k == "fc1.weight": new_k = "fc_feat.weight"
                if k == "fc1.bias": new_k = "fc_feat.bias"
               
                if new_k in model_dict and v.shape == model_dict[new_k].shape:
                    mapped[new_k] = v
            model_dict.update(mapped)
            self.load_state_dict(model_dict)
            print(f"✅ [CNN14] Pretrained Weights Loaded ({len(mapped)} layers)")
            return True
        except Exception as e:
            print(f"❌ Weight loading error: {e}")
            return False


class PaSSTBackbone(nn.Module):
    def __init__(self, arch=DEFAULT_PASST_MODEL, use_lora=True):
        super().__init__()
        from hear21passt.models.passt import get_model
        from hear21passt.models.preprocess import AugmentMelSTFT
        # hear21passt library explicit stride requirements for default architecture
        self.passt = get_model(arch=arch, pretrained=True, fstride=16, tstride=16)
        self.passt.head = nn.Identity()
        self.mel = AugmentMelSTFT(n_mels=128, sr=32000, win_length=800, hopsize=320, n_fft=1024)
       
        if use_lora:
            print(f"🧬 Applying LoRA (r=8, qkv) to PaSST ({arch})...")
            config = LoraConfig(
                r=8, lora_alpha=16,
                target_modules=["qkv"], # PaSST uses combined qkv
                lora_dropout=0.1, bias="none"
            )
            self.passt = get_peft_model(self.passt, config)


    def forward(self, x):
        if x.dim() == 1: x = x.unsqueeze(0)
        m = self.mel(x).unsqueeze(1)
        # PaSST with head=Identity returns (logits, features) where both are features
        _, f = self.passt(m)
        return f


class HierarchicalMoEPipeline(nn.Module):
    def __init__(self, model_type="ast"):
        super().__init__()
        self.model_type = model_type
        if model_type == "ast":
            self.backbone = ASTModel.from_pretrained(DEFAULT_AST_MODEL)
            feat_dim = 768
            # LoRA
            config = LoraConfig(r=8, lora_alpha=32, target_modules=["query", "key", "value"])
            self.backbone = get_peft_model(self.backbone, config)
        elif model_type == "passt":
            self.backbone = PaSSTBackbone()
            feat_dim = 768
        else: # cnn14
            self.backbone = CNN14Backbone()
            self.backbone.load_pretrained_weights()
            feat_dim = 2048


        self.domain_head = nn.Linear(feat_dim, 2)
        # Stage 1: Explicit initialization to break 0.5/0.5 prediction deadlock
        nn.init.xavier_uniform_(self.domain_head.weight)
        nn.init.constant_(self.domain_head.bias, 0.0)
        
        self.stage2_proj = nn.Sequential(nn.Linear(feat_dim, 512), nn.LayerNorm(512), nn.ReLU())
        self.router = nn.Linear(512, 3)
        self.experts = nn.ModuleList([DiagnosticExpert(512, i) for i in range(3)])


    def forward(self, x, stage=1):
        pooled = self.backbone(x)
        if hasattr(pooled, "last_hidden_state"): # AST specific
            pooled = pooled.last_hidden_state[:, 0, :]
           
        if stage == 1:
            return self.domain_head(pooled)
        else:
            pooled = self.stage2_proj(pooled)
            gate_logits = self.router(pooled) / 1.5
            gate_weights = F.softmax(gate_logits, dim=-1)
            expert_outputs = torch.stack([exp(pooled) for exp in self.experts], dim=1)
            final_output = torch.einsum('be,bec->bc', gate_weights, expert_outputs)
            return final_output, gate_weights, gate_logits


# =============================================================================
# 2. 학습 및 평가
# =============================================================================


def train_hierarchical(model_type, stage, epochs=10, batch_size=8, eval_only=False):
    model = HierarchicalMoEPipeline(model_type).to(DEVICE)
    
    # Pre-split 데이터 로드
    train_list = get_hierarchical_data(stage, split="train")
    val_list = get_hierarchical_data(stage, split="val")
    test_list = get_hierarchical_data(stage, split="test")
    
    if not train_list: return print(f"❌ No training data found at {CAR_DATASET_ROOT}")
   
    # Balanced Sampler (Train에만 적용)
    counts = Counter([x['label'] for x in train_list])
    w = [ (1.0/max(1, counts[x['label']])) for x in train_list ]
    train_loader = DataLoader(HierarchicalDS(train_list, model_type), batch_size=batch_size, sampler=WeightedRandomSampler(w, len(w)))
    val_loader = DataLoader(HierarchicalDS(val_list, model_type), batch_size=batch_size)
    test_loader = DataLoader(HierarchicalDS(test_list, model_type), batch_size=batch_size)


    # inheritance & freezing
    s1_path = f"hier_s1_{model_type}.pt"
    if stage == 2 and not eval_only and os.path.exists(s1_path):
        model.load_state_dict(torch.load(s1_path, map_location=DEVICE), strict=False)
        print(f"✅ Loaded Stage 1 ({model_type})")
        for p in model.domain_head.parameters(): p.requires_grad = False
        for n, p in model.backbone.named_parameters():
            if "lora" in n or model_type != "ast": p.requires_grad = False
        print("🔒 Frozen Stage 1")

    # CNN14 Fix: Stage 1 requires FULL backbone unfreeze for representation shift
    if model_type == "cnn14":
        if stage == 1:
            for p in model.backbone.parameters():
                p.requires_grad = True
            print("🟡 [Stage 1 CNN14] FULL Backbone Unfrozen for representation shift")
        else:
            unfrozen_layers = []
            for name, p in model.backbone.named_parameters():
                if any(k in name for k in ["conv_blocks.4", "conv_blocks.5", "fc_feat"]):
                    p.requires_grad = True
                    unfrozen_layers.append(name)
                else:
                    p.requires_grad = False
            print(f"🟡 [Stage 2 CNN14] Unfrozen layers: {len(unfrozen_layers)} (blocks 4, 5, fc)")

    if eval_only:
        path = f"hier_s{stage}_{model_type}.pt"
        if os.path.exists(path): model.load_state_dict(torch.load(path, map_location=DEVICE))
        else: return

    # Unified Optimizer per user instruction
    lr_val = 1e-4 if model_type == "cnn14" else 3e-5
    trainable_params = [p for p in model.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW(trainable_params, lr=lr_val)
    print(f"🚀 Optimizer Configured (LR={lr_val}, Trainable Params: {len(trainable_params)})")
    
    # Class Weight Calculation for CrossEntropy
    if stage == 1:
        criterion = nn.CrossEntropyLoss()
    else:
        # Calculate dynamic class weights for Stage 2 (Normal vs Abnormal)
        counts = Counter([x['label'] for x in train_list])
        total = sum(counts.values())
        if total > 0 and len(counts) == 2:
            wt_0 = total / (2.0 * counts[0])
            wt_1 = total / (2.0 * counts[1])
            class_weights = torch.tensor([wt_0, wt_1], dtype=torch.float32).to(DEVICE)
            criterion = nn.CrossEntropyLoss(weight=class_weights)
            print(f"⚖️ Applied Stage 2 Class Weights: Normal={wt_0:.2f}, Abnormal={wt_1:.2f}")
        else:
            criterion = nn.CrossEntropyLoss()
            
    scaler = torch.amp.GradScaler('cuda')
   
    best_f1 = 0
    for epoch in range(epochs):
        if eval_only: break
        model.train()
        total_loss = 0
        for batch_idx, batch in enumerate(train_loader):
            x, y, d = batch["input"].to(DEVICE), batch["label"].to(DEVICE), batch["domain"].to(DEVICE)
            optimizer.zero_grad()
            with torch.amp.autocast('cuda'):
                res = model(x, stage=stage)
                
                if epoch == 0 and batch_idx == 0:
                    logits_debug = res[0] if stage == 2 else res
                    print(f"🔍 [Debug] logits mean: {logits_debug.mean().item():.4f}, std: {logits_debug.std().item():.4f}")
                
                if stage == 2:
                    logits, gate_weights, gate_logits = res
                    # 1. Diagnosis Loss
                    loss = criterion(logits, y)
                    # 2. Supervised Router Loss (force router to pick right expert)
                    if (d != -1).any():
                        loss += 0.5 * F.cross_entropy(gate_logits[d != -1], d[d != -1])
                    # 3. Entropy Regularization
                    loss += 0.01 * (-torch.sum(gate_weights * torch.log(gate_weights + 1e-8), dim=1).mean())
                else:
                    loss = criterion(res, y)
           
            if torch.isnan(loss):
                print("⚠️ [NaN Detected] Skipping batch and resetting gradients.")
                optimizer.zero_grad()
                continue


            scaler.scale(loss).backward()
            # Gradient Clipping
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
           
            scaler.step(optimizer); scaler.update()
            total_loss += loss.item()
       
        model.eval()
        preds, labels = [], []
        with torch.no_grad():
            for batch in val_loader:
                x, y = batch["input"].to(DEVICE), batch["label"].to(DEVICE)
                res = model(x, stage=stage)
                logits = res[0] if stage == 2 else res
                preds.extend(torch.argmax(logits, dim=1).cpu().numpy())
                labels.extend(y.cpu().numpy())
        micro_f1 = f1_score(labels, preds, average='micro', zero_division=0)
        print(f"Epoch {epoch+1}/{epochs} Loss: {total_loss/len(train_loader):.4f} Val Micro Average (Accuracy): {micro_f1:.4f}")
        if micro_f1 > best_f1:
            best_f1 = micro_f1
            torch.save(model.state_dict(), f"hier_s{stage}_{model_type}.pt")
            print(f"💾 Saved Best (Micro Avg Focus: {model_type})")


    # Final Test
    print(f"\n🎯 [FINAL TEST - {model_type}]")
    model.eval()
    preds, labels, domains = [], [], []
    with torch.no_grad():
        for batch in test_loader:
            x, y, d = batch["input"].to(DEVICE), batch["label"].to(DEVICE), batch["domain"].to(DEVICE)
            res = model(x, stage=stage)
            logits = res[0] if stage == 2 else res
            preds.extend(torch.argmax(logits, dim=1).cpu().numpy())
            labels.extend(y.cpu().numpy())
            domains.extend(d.cpu().numpy())
   
    if stage == 1:
        rep = classification_report(labels, preds, target_names=["Car", "OOD"], digits=4, output_dict=True)
        print(classification_report(labels, preds, target_names=["Car", "OOD"], digits=4))
        print(f"📌 Micro Average (Overall Accuracy): {rep['accuracy']:.4f}")
    else:
        print("\n📢 [Overall Diagnostic Report]")
        rep = classification_report(labels, preds, target_names=["Normal", "Abnormal"], digits=4, output_dict=True)
        print(classification_report(labels, preds, target_names=["Normal", "Abnormal"], digits=4))
        print(f"📌 Micro Average (Overall Accuracy): {rep['accuracy']:.4f}")
       
        # Per-Domain Breakdown
        domain_names = ["Starter (Startup)", "Engine (Idle)", "Brake (Braking)"]
        for d_idx, d_name in enumerate(domain_names):
            mask = (np.array(domains) == d_idx)
            if np.any(mask):
                print(f"\n📊 [{d_name}] Diagnostic Report:")
                d_labels = np.array(labels)[mask]
                d_preds = np.array(preds)[mask]
                d_rep = classification_report(d_labels, d_preds, target_names=["Normal", "Abnormal"], digits=4, zero_division=0, output_dict=True)
                print(classification_report(d_labels, d_preds, target_names=["Normal", "Abnormal"], digits=4, zero_division=0))
                print(f"   ∟ Micro Average (Hit Rate): {d_rep['accuracy']:.4f}")


def run_external_test(model_type, use_stage1=False):
    """외부 유튜브/신규 데이터셋 전용 테스트 로직 (Stage 1 필터링 옵션 포함)"""
    model = HierarchicalMoEPipeline(model_type).to(DEVICE)
    s2_path = f"hier_s2_{model_type}.pt"
   
    if not os.path.exists(s2_path):
        return print(f"❌ '{s2_path}' 가중치 파일이 없습니다. 먼저 2단계 학습을 완료하세요.")
   
    model.load_state_dict(torch.load(s2_path, map_location=DEVICE))
    model.eval()
   
    data = get_external_test_data(new_only=True)
    if not data:
        return print("❌ 외부 테스트 데이터를 찾을 수 없습니다. (ai/data/audio/test/abnormal/ 하위 확인)")
   
    loader = DataLoader(HierarchicalDS(data, model_type), batch_size=4)
    print(f"\n🚀 [EXTERNAL TEST - {model_type}] 외부 수집 데이터 검증 시작 {'(Stage 1 필터링 적용)' if use_stage1 else ''}")
    print(f"   (로드된 데이터: {len(data)}개)")
   
    results = []
    with torch.no_grad():
        for batch in loader:
            x, y, d = batch["input"].to(DEVICE), batch["label"].to(DEVICE), batch["domain"].to(DEVICE)
           
            # 1. Stage 1 Filter (옵션)
            s1_passed = [True] * len(y)
            if use_stage1:
                s1_logits = model(x, stage=1)
                s1_preds = torch.argmax(s1_logits, dim=1)
                s1_passed = (s1_preds == 0).cpu().numpy() # 0: Car
           
            # 2. Stage 2 Diagnostic & Router
            s2_logits, gate_weights, gate_logits = model(x, stage=2)
            s2_preds = torch.argmax(s2_logits, dim=1).cpu().numpy()
            gate_preds = torch.argmax(gate_weights, dim=1).cpu().numpy()
            y_np = y.cpu().numpy()
            d_np = d.cpu().numpy()
           
            for i in range(len(y)):
                results.append({
                    "domain": d_np[i],
                    "s1_passed": s1_passed[i],
                    "router_correct": (gate_preds[i] == d_np[i]),
                    "s2_correct": (s2_preds[i] == y_np[i]),
                    "y_true": y_np[i],
                    "y_pred": s2_preds[i]
                })
           
    # 3. 지표 계산 함수
    def calc_metrics(tp, fp, fn):
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)
              if (precision + recall) > 0 else 0.0)
        return precision, recall, f1

    # 결과 요약 (Abnormal 감지율 위주)
    domain_names = ["Starter", "Engine", "Brake"]
    print(f"\n📊 [외부 데이터셋(정상+결함) 검증 상세 결과]")
    print("-" * 50)
   
    total_samples = len(results)
    total_passed_s1 = sum([r["s1_passed"] for r in results])
    print(f"✅ 전체 1단계 통과 (차량 소리 인식): {total_passed_s1}/{total_samples} ({(total_passed_s1/total_samples*100):.1f}%)")
   
    from collections import defaultdict
    stats = defaultdict(lambda: {"TP": 0, "FP": 0, "FN": 0, "TN": 0})
    
    for d_idx, d_name in enumerate(domain_names):
        d_results = [r for r in results if r["domain"] == d_idx]
        if d_results:
            d_total = len(d_results)
            d_passed_s1 = sum([r["s1_passed"] for r in d_results])
           
            # S1을 통과한 것들 중에서만 Router와 S2 체크
            passed_results = [r for r in d_results if r["s1_passed"]]
            router_hit = sum([r["router_correct"] for r in passed_results])
            
            # (2) 결과 누적 (router 통과 후 기준)
            for r in passed_results:
                true_label = r["y_true"]
                pred_label = r["y_pred"]
                
                if true_label == 1 and pred_label == 1:
                    stats[d_idx]["TP"] += 1
                elif true_label == 0 and pred_label == 1:
                    stats[d_idx]["FP"] += 1
                elif true_label == 1 and pred_label == 0:
                    stats[d_idx]["FN"] += 1
                elif true_label == 0 and pred_label == 0:
                    stats[d_idx]["TN"] += 1
            
            # (4) 출력부 (도메인별)
            tp = stats[d_idx]["TP"]
            fp = stats[d_idx]["FP"]
            fn = stats[d_idx]["FN"]
            tn = stats[d_idx]["TN"]
            
            p, r, f1 = calc_metrics(tp, fp, fn)
            
            print(f"\n🔥 {d_name} (총 {d_total}개 중 {d_passed_s1}개 통과)")
            if d_passed_s1 > 0:
                print(f"   ∟ 라우터 정타 지수 (Router Hit Rate): {router_hit}/{d_passed_s1} ({(router_hit/d_passed_s1*100):.1f}%)")
                print(f"   ∟ 오탐(False Positive): {fp}건 (정상 소리를 결함이라 잘못 판단함)")
                print(f"   Precision: {p:.3f}")
                print(f"   Recall:    {r:.3f}")
                print(f"   F1-score:  {f1:.3f}")
            else:
                print(f"   ⚠️ 1단계를 통과한 0건으로 평가 불가")


def run_full_pipeline_test(model_type):
    """[Full Flow] Stage 1 (Filter) -> Stage 2 (Diagnostic) 통합 테스트"""
    model_s1 = HierarchicalMoEPipeline(model_type).to(DEVICE)
    model_s2 = HierarchicalMoEPipeline(model_type).to(DEVICE)
    s1_path = f"hier_s1_{model_type}.pt"
    s2_path = f"hier_s2_{model_type}.pt"
   
    if not (os.path.exists(s1_path) and os.path.exists(s2_path)):
        return print(f"❌ 가중치 파일({s1_path} 또는 {s2_path})이 없습니다. 1, 2단계를 모두 학습하세요.")
   
    # 독립적인 가중치 로드
    model_s1.load_state_dict(torch.load(s1_path, map_location=DEVICE))
    model_s1.eval()
    
    model_s2.load_state_dict(torch.load(s2_path, map_location=DEVICE))
    model_s2.eval()
   
    # 테스트 데이터 준비 (이미 나누어진 test 폴더 사용)
    ood_data = get_hierarchical_data(stage=1, split="test") # 여기서 Label 1이 OOD
    ood_samples = [x for x in ood_data if x['label'] == 1]
    
    car_samples = get_hierarchical_data(stage=2, split="test") # Normal(0), Abnormal(1)
   
    combined = ood_samples + car_samples
    np.random.shuffle(combined)
    loader = DataLoader(HierarchicalDS(combined, model_type), batch_size=4, num_workers=0)
   
    print(f"\n🌊 [FULL PIPELINE TEST - {model_type}] 전체 워크플로우 시뮬레이션")
    print(f"   (총 테스트 샘플: {len(combined)}개 | 자동차: {len(car_samples)}, OOD: {len(ood_samples)})")
   
    correct_rejection = 0
    correct_diagnosis = 0
    false_alarm = 0
    miss = 0
   
    with torch.no_grad():
        for batch in loader:
            x, y, d = batch["input"].to(DEVICE), batch["label"].to(DEVICE), batch["domain"].to(DEVICE)
           
            s1_logits = model_s1(x, stage=1)
            s1_preds = torch.argmax(s1_logits, dim=1)
           
            s2_logits, _, _ = model_s2(x, stage=2)
            s2_preds = torch.argmax(s2_logits, dim=1)
           
            for i in range(len(y)):
                true_is_ood = (d[i] == -1)
                pred_is_ood = (s1_preds[i] == 1)
               
                if true_is_ood:
                    if pred_is_ood: correct_rejection += 1
                    else: miss += 1
                else:
                    if pred_is_ood: false_alarm += 1
                    else:
                        if s2_preds[i] == y[i].item(): correct_diagnosis += 1
   
    total_samples = len(combined)
    total_correct = correct_rejection + correct_diagnosis
    print(f"\n📊 [통합 적중률 리포트]")
    print(f"✅ OOD 필터링 성공: {correct_rejection}/{len(ood_samples)}")
    print(f"✅ 정상/결함 진단 성공: {correct_diagnosis}/{len(car_samples)}")
    print(f"❌ 필터링 실패 (Miss): {miss}")
    print(f"❌ 오탐지 (False Alarm): {false_alarm}")
    print(f"\n🏆 최종 시스템 적중률 (Micro Average): {total_correct/total_samples*100:.2f}%")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_type", choices=["ast", "cnn14", "passt"], default="ast")
    parser.add_argument("--stage", type=int, choices=[1, 2], required=False)
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch_size", type=int, default=8)
    parser.add_argument("--eval", action="store_true")
    parser.add_argument("--test_external", action="store_true", help="외부/신규 데이터셋 추가 테스트")
    parser.add_argument("--stage1", action="store_true", help="test_external 시 Stage 1 필터 적용 여부")
    parser.add_argument("--test_full", action="store_true", help="전체 파이프라인 통합 테스트")
    args = parser.parse_args()
   
    if args.test_full:
        run_full_pipeline_test(args.model_type)
    elif args.test_external:
        run_external_test(args.model_type, use_stage1=args.stage1)
    else:
        if args.stage is None:
            print("❌ --stage [1|2], --test_external, --test_full 중 하나를 지정해야 합니다.")
        else:
            train_hierarchical(args.model_type, args.stage, args.epochs, args.batch_size, eval_only=args.eval)





