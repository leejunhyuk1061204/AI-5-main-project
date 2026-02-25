# ai/scripts/audio/train_cnn_moe_sequential.py
"""
[실험용] CNN14-based Sequential MoE Pipeline
- Stage 1: Binary classification (Normal vs Abnormal)
- Stage 2: Domain classification with Mixture of Experts (Starter, Engine, Brake)
- Backbone: CNN14 (PANNs)
"""
import os
import sys
import argparse
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset
import numpy as np
from sklearn.metrics import classification_report, f1_score
from pathlib import Path

# 프로젝트 루트 추가
project_root = str(Path(__file__).resolve().parent.parent.parent.parent)
if project_root not in sys.path:
    sys.path.append(project_root)

from ai.scripts.audio.config import (
    TYPE_LABELS, type2id, id2type, COMMON_CONFIG, DEVICE, 
    set_seed, save_metrics, EarlyStopping
)
from ai.scripts.audio.data_loader import create_dataloaders

set_seed(42)
torch.backends.cudnn.benchmark = True

DEFAULT_AST_MODEL = "MIT/ast-finetuned-audioset-10-10-0.4593"
EXP_LABELS = ["starter", "engine", "brake"]
exp2id = {l: i for i, l in enumerate(EXP_LABELS)}

# =============================================================================
# 0. 커스텀 데이터셋 정의 (Top-level)
# =============================================================================

class DefectDS(Dataset):
    def __init__(self, data):
        self.data = data
    def __len__(self):
        return len(self.data)
    def __getitem__(self, idx):
        item = self.data[idx]
        return {
            "input": torch.tensor(item["mel"], dtype=torch.float32), 
            "label": torch.tensor(item["label"], dtype=torch.long)
        }

# =============================================================================
# 1. 모델 정의 — CNN14 + MoE
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

class ExpertHead(nn.Module):
    def __init__(self, input_dim, hidden_dim=256, output_dim=3):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim, output_dim)
        )
    def forward(self, x):
        return self.net(x)

class CNNMoESequential(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv_blocks = nn.Sequential(
            ConvBlock(1, 64),
            ConvBlock(64, 128),
            ConvBlock(128, 256),
            ConvBlock(256, 512),
            ConvBlock(512, 1024),
        )
        feat_dim = 1024
        
        # Stage 1 Head: Binary
        self.binary_head = nn.Linear(feat_dim, 2)
        
        # Stage 2 MoE: 3 Experts + 1 Router
        self.num_experts = 3
        self.experts = nn.ModuleList([ExpertHead(feat_dim) for _ in range(self.num_experts)])
        self.router = nn.Linear(feat_dim, self.num_experts)

    def forward(self, x, stage=1):
        if x.dim() == 3:
            x = x.unsqueeze(1) # (B, 1, H, W)
            
        x = self.conv_blocks(x)
        pooled = torch.mean(x, dim=(2, 3)) # Global Average Pooling
        
        if stage == 1:
            return self.binary_head(pooled)
        else:
            gate_logits = self.router(pooled)
            gate_weights = F.softmax(gate_logits, dim=-1)
            
            expert_outputs = torch.stack([expert(pooled) for expert in self.experts], dim=1)
            final_output = torch.einsum('be,bec->bc', gate_weights, expert_outputs)
            return final_output

    def load_panns_weights(self):
        path = Path("ai/weights/audio/Cnn14_16k_mAP=0.438.pth")
        if not path.exists():
            print("[CNN14] Pretrained weights not found. Using random init.")
            return False
        try:
            state_dict = torch.load(path, map_location="cpu", weights_only=False)
            if 'model' in state_dict: state_dict = state_dict['model']
            
            model_dict = self.state_dict()
            mapped_dict = {}
            for k, v in state_dict.items():
                if k.startswith("conv_block"):
                    try:
                        num = int(k.split(".")[0].replace("conv_block", ""))
                        new_k = k.replace(f"conv_block{num}", f"conv_blocks.{num-1}")
                        if new_k in model_dict and v.shape == model_dict[new_k].shape:
                            mapped_dict[new_k] = v
                    except: pass
            model_dict.update(mapped_dict)
            self.load_state_dict(model_dict)
            print(f"✅ Loaded {len(mapped_dict)} layers from PANNs.")
            return True
        except Exception as e:
            print(f"❌ Failed to load PANNs: {e}")
            return False

# =============================================================================
# 2. 평가 함수
# =============================================================================

def evaluate_moe(model, loader, stage=1):
    model.eval()
    all_preds = []
    all_labels = []
    
    print(f"🔬 Running Stage {stage} Evaluation...", flush=True)
    with torch.no_grad():
        for batch in loader:
            x = (batch["mel_input"] if stage == 1 else batch["input"]).to(DEVICE)
            y = (batch["abnormal_label"] if stage == 1 else batch["label"]).to(DEVICE)
            
            if stage == 2 and (y < 0).any(): continue
            
            logits = model(x, stage=stage)
            preds = torch.argmax(logits, dim=1)
            
            all_preds.extend(preds.cpu().numpy())
            all_labels.extend(y.cpu().numpy())

    if len(all_labels) == 0:
        print("⚠️ No labels found for evaluation.")
        return 0.0

    target_names = ["Normal", "Abnormal"] if stage == 1 else EXP_LABELS
    report = classification_report(all_labels, all_preds, target_names=target_names, digits=4, zero_division=0)
    print(f"\n📊 [Stage {stage}] Classification Report:\n{report}")
    
    f1 = f1_score(all_labels, all_preds, average='macro', zero_division=0)
    return f1

# =============================================================================
# 3. 학습 함수
# =============================================================================

def train_stage(stage, epochs=10, batch_size=16, eval_only=False):
    loaders = create_dataloaders("cnn", batch_size=batch_size)
    train_loader_orig, val_loader, val_loader_bal, test_loader, _, _ = loaders

    model = CNNMoESequential().to(DEVICE)
    model.load_panns_weights()
    
    if eval_only:
        weight_path = f"cnn_moe_stage{stage}_best.pt"
        if os.path.exists(weight_path):
            model.load_state_dict(torch.load(weight_path, map_location=DEVICE))
            print(f"✅ Loaded weights from {weight_path}")
        else:
            print(f"❌ Weight file not found: {weight_path}")
            return

        if stage == 1:
            evaluate_moe(model, test_loader, stage=1)
        else:
            defect_test = []
            for item in test_loader.dataset.data:
                if item['abnormal'] == 1 and item['type'] in exp2id:
                    new_item = item.copy()
                    new_item['label'] = exp2id[item['type']]
                    defect_test.append(new_item)
            test_loader_moe = DataLoader(DefectDS(defect_test), batch_size=batch_size)
            evaluate_moe(model, test_loader_moe, stage=2)
        return

    print(f"🔥 Starting CNN14 Stage {stage} Training (RTX 3050 Optimized)...")
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3 if stage==1 else 1e-4) # CNN usually needs higher LR than AST
    criterion = nn.CrossEntropyLoss()
    scaler = torch.amp.GradScaler('cuda')
    early_stop = EarlyStopping(patience=5, min_epochs=3)

    if stage == 1:
        train_loader = train_loader_orig
        eval_loader_moe = val_loader_bal
    else:
        defect_train = []
        for item in train_loader_orig.dataset.data:
            if item['abnormal'] == 1 and item['type'] in exp2id:
                new_item = item.copy()
                new_item['label'] = exp2id[item['type']]
                defect_train.append(new_item)
        train_loader = DataLoader(DefectDS(defect_train), batch_size=batch_size, shuffle=True)
        
        defect_val = []
        for item in val_loader_bal.dataset.data:
            if item['abnormal'] == 1 and item['type'] in exp2id:
                new_item = item.copy()
                new_item['label'] = exp2id[item['type']]
                defect_val.append(new_item)
        eval_loader_moe = DataLoader(DefectDS(defect_val), batch_size=batch_size)

    best_f1 = 0
    for epoch in range(epochs):
        model.train()
        total_loss = 0
        
        for batch in train_loader:
            x = (batch["mel_input"] if stage == 1 else batch["input"]).to(DEVICE)
            y = (batch["abnormal_label"] if stage == 1 else batch["label"]).to(DEVICE)
            
            optimizer.zero_grad()
            with torch.amp.autocast('cuda'):
                logits = model(x, stage=stage)
                loss = criterion(logits, y)
            
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            total_loss += loss.item()

        avg_loss = total_loss / len(train_loader)
        print(f"Epoch {epoch+1}/{epochs} Loss: {avg_loss:.4f}")
        
        val_f1 = evaluate_moe(model, eval_loader_moe, stage=stage)
        if val_f1 > best_f1:
            best_f1 = val_f1
            torch.save(model.state_dict(), f"cnn_moe_stage{stage}_best.pt")
            print(f"💾 Best Model Saved (F1: {best_f1:.4f})")
            
        if early_stop.step(val_f1, epoch): break

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", type=int, choices=[1, 2], required=True)
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch_size", type=int, default=32)
    parser.add_argument("--eval", action="store_true", help="Run evaluation only")
    args = parser.parse_args()
    train_stage(args.stage, args.epochs, args.batch_size, eval_only=args.eval)
