# ai/scripts/audio/train_ast_moe_sequential.py
"""
[실험용] Sequential MoE Pipeline (RTX 3050 Optimized)
- Stage 1: Binary classification (Normal vs Abnormal)
- Stage 2: Domain classification with Mixture of Experts (Starter, Engine, Brake)
- Memory Optimization: Batch Size 4/8, AMP, LoRA, Gradient Checkpointing
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
# RTX 3050 Optimization
torch.backends.cudnn.benchmark = True
if torch.cuda.is_available() and torch.cuda.get_device_properties(0).total_memory < 8e9:
    print("📉 [Hardware] RTX 3050 detected (<8GB VRAM). Enabling extreme memory optimization.")

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
            "input": item["ast_input"],
            "label": torch.tensor(item["label"], dtype=torch.long)
        }

# =============================================================================
# 1. MoE 컴포넌트 정의
# =============================================================================

class ExpertHead(nn.Module):
    def __init__(self, input_dim, expert_id, output_dim=3):
        super().__init__()
        # 4️⃣ Expert별 inductive bias (S:얕고 빠름, E:중간, B:깊고 넓음)
        hidden_dim = [192, 256, 320][expert_id]
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.BatchNorm1d(hidden_dim),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim, output_dim)
        )
        # Unique initialization
        with torch.no_grad():
            self.net[-1].weight.data += expert_id * 0.1

    def forward(self, x):
        return self.net(x)

class ASTMoESequential(nn.Module):
    def __init__(self, model_id=DEFAULT_AST_MODEL, use_lora=True):
        super().__init__()
        self.ast = ASTModel.from_pretrained(model_id)
        feat_dim = 768
        
        if use_lora:
            print("🚀 Applying Expanded LoRA (r=16, qkv) to AST Backbone...")
            # 5️⃣ LoRA target 확장 및 Rank 증가
            lora_config = LoraConfig(
                r=8, lora_alpha=32, target_modules=["query", "key", "value"],
                lora_dropout=0.1, bias="none"
            )
            self.ast = get_peft_model(self.ast, lora_config)
            self.ast.gradient_checkpointing_enable()

        # Stage 1 Head: Binary
        self.binary_head = nn.Linear(feat_dim, 2)
        
        # 6️⃣ Stage 2 전용 projection (Domain 정렬 시프트)
        self.stage2_proj = nn.Sequential(
            nn.Linear(feat_dim, 512),
            nn.LayerNorm(512),
            nn.ReLU()
        )
        
        # Stage 2 MoE: 3 Experts + 1 Router
        self.num_experts = 3
        self.experts = nn.ModuleList([ExpertHead(512, i) for i in range(self.num_experts)])
        self.router = nn.Linear(512, self.num_experts)

    def forward(self, input_values, stage=1):
        outputs = self.ast(input_values)
        pooled = outputs.last_hidden_state[:, 0, :]  # CLS token
        
        if stage == 1:
            return self.binary_head(pooled)
        else:
            # Stage 2 Projection
            pooled = self.stage2_proj(pooled)
            
            # Stage 2: MoE Inference with Temperature Scaling
            # 2️⃣ Router temperature 조절 (1.5)
            gate_logits = self.router(pooled) / 1.5
            gate_weights = F.softmax(gate_logits, dim=-1) # [B, 3]
            
            expert_outputs = torch.stack([expert(pooled) for expert in self.experts], dim=1) # [B, 3, 3]
            final_output = torch.einsum('be,bec->bc', gate_weights, expert_outputs)
            return final_output, gate_weights

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
            x = (batch["ast_input"] if stage == 1 else batch["input"]).to(DEVICE)
            y = (batch["abnormal_label"] if stage == 1 else batch["label"]).to(DEVICE)
            
            if stage == 2 and (y < 0).any(): continue
            
            res = model(x, stage=stage)
            if stage == 2:
                logits, gate_weights = res
                if len(all_preds) == 0: # Print only for first batch to avoid clutter
                    print(f"   [Eval Check] Gate Weights (Avg): {gate_weights.mean(0).cpu().numpy()}")
            else:
                logits = res
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

def train_stage(stage, epochs=10, batch_size=8, eval_only=False):
    fe = ASTFeatureExtractor.from_pretrained(DEFAULT_AST_MODEL)
    loaders = create_dataloaders("ast", feature_extractor=fe, batch_size=batch_size)
    train_loader_orig, val_loader, val_loader_bal, test_loader, _, _ = loaders

    model = ASTMoESequential().to(DEVICE)
    
    if eval_only:
        weight_path = f"moe_stage{stage}_best.pt"
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

    print(f"🔥 Starting Stage {stage} Training (RTX 3050 Optimized)...")
    optimizer = torch.optim.AdamW(model.parameters(), lr=5e-5 if stage==1 else 3e-5)
    
    # [Inheritance] Stage 1 가중치 계승 (Stage 2 시작 시)
    if stage == 2 and not eval_only:
        stage1_path = "moe_stage1_best.pt"
        if os.path.exists(stage1_path):
            try:
                # strict=False: 다른 헤드(binary vs moe)는 무시하고 shared backbone만 로드
                model.load_state_dict(torch.load(stage1_path, map_location=DEVICE), strict=False)
                print(f"✅ Stage 2 Training: Loaded Stage 1 knowledge from {stage1_path}")
                
                # [Option A] Stage 1 지식 고정 (Freezing)
                # 1. Binary Head 고정
                for p in model.binary_head.parameters():
                    p.requires_grad = False
                
                # 2. LoRA Backbone 고정: Stage 1의 '이상 감지' 공간을 보존
                for name, param in model.named_parameters():
                    if "lora" in name:
                        param.requires_grad = False
                
                print("🔒 Frozen Stage 1 components (Backbone-LoRA & Binary Head). Training MoE only.")
            except Exception as e:
                print(f"⚠️ Stage 1 weight load failed: {e}")
    
    if stage == 1:
        criterion = nn.CrossEntropyLoss()
    else:
        # 2️⃣ Class Weight 조정 (완화 및 균형)
        class_weights = torch.tensor([1.2, 1.0, 1.3]).to(DEVICE)
        criterion = nn.CrossEntropyLoss(weight=class_weights)

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
        
        # 3️⃣ Stage 2 전용 class-balanced sampler
        counts = Counter([x['label'] for x in defect_train])
        # labels might not include all indices if data is sparse, but exp2id has 0,1,2
        label_weights = {lbl: 1.0/cnt for lbl, cnt in counts.items()}
        weights = [label_weights[x['label']] for x in defect_train]
        sampler = WeightedRandomSampler(weights, len(weights))
        
        train_loader = DataLoader(DefectDS(defect_train), batch_size=batch_size, sampler=sampler)
        
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
            x = (batch["ast_input"] if stage == 1 else batch["input"]).to(DEVICE)
            y = (batch["abnormal_label"] if stage == 1 else batch["label"]).to(DEVICE)
            
            optimizer.zero_grad()
            with torch.amp.autocast('cuda'):
                res = model(x, stage=stage)
                
                if stage == 2:
                    # 1️⃣ Router entropy regularization
                    logits, gate_weights = res
                    ce_loss = criterion(logits, y)
                    entropy = -torch.sum(gate_weights * torch.log(gate_weights + 1e-8), dim=1).mean()
                    loss = ce_loss + 0.01 * entropy
                    
                    if epoch == 0 and total_loss == 0:
                        print(f"   [Train Check] Gate Weights (Avg): {gate_weights.mean(0).detach().cpu().numpy()}")
                else:
                    logits = res
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
            torch.save(model.state_dict(), f"moe_stage{stage}_best.pt")
            print(f"💾 Best Model Saved (F1: {best_f1:.4f})")
            
        if early_stop.step(val_f1, epoch): break

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", type=int, choices=[1, 2], required=True)
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch_size", type=int, default=8)
    parser.add_argument("--eval", action="store_true", help="Run evaluation only")
    args = parser.parse_args()
    train_stage(args.stage, args.epochs, args.batch_size, eval_only=args.eval)
