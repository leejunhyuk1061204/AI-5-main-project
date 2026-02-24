# ai/scripts/audio/train_ast.py
"""
[파일 용도] AST (Audio Spectrogram Transformer) 모델 학습
AudioSpectrogramTransformer를 사용하여 오디오 데이터를 학습시키는 메인 스크립트입니다.
ImageNet/AudioSet 사전 학습된 가중치를 기반으로 Fine-tuning을 수행하며, Method A(계층적 분류) 구조를 따릅니다.
  Baseline:  python -m ai.scripts.audio.train_ast --mode baseline
  Fine-tune: python -m ai.scripts.audio.train_ast --mode finetune
"""
import os, argparse
import torch
import torch.nn as nn
import numpy as np
from transformers import ASTModel, ASTFeatureExtractor
from sklearn.metrics import (
    precision_recall_fscore_support, accuracy_score,
    confusion_matrix, balanced_accuracy_score, classification_report,
    f1_score
)
from peft import LoraConfig, get_peft_model, TaskType

from ai.scripts.audio.config import (
    set_seed, save_metrics, measure_latency, EarlyStopping,
    TYPE_LABELS, type2id, ABNORMAL_LABELS, OTHER_THRESHOLD,
    ABNORMAL_THRESHOLD, COMMON_CONFIG, DEVICE, SAVE_ROOT, NUM_TYPE_CLASSES
)
from ai.scripts.audio.data_loader import create_dataloaders
from ai.scripts.audio.advanced_metrics import calculate_fpr_at_recall, calculate_trr, calculate_nrs, calculate_divergence

set_seed(42)

DEFAULT_AST_MODEL = "MIT/ast-finetuned-audioset-10-10-0.4593"


# =============================================================================
# 1. 모델 정의
# =============================================================================

class ASTMultiTask(nn.Module):
    """AST backbone + Multi-Task Dual Heads"""
    def __init__(self, model_id=DEFAULT_AST_MODEL):
        super().__init__()
        self.ast = ASTModel.from_pretrained(model_id)
        feat_dim = 768
        
        # Head A: Binary (Normal, Abnormal)
        self.binary_head = nn.Linear(feat_dim, 2)
        # Head B: Multi-class (Starter, Engine, Brake, Other)
        self.type_head = nn.Linear(feat_dim, 4)

    def freeze_backbone(self):
        # Freeze all parameters first
        for p in self.ast.parameters():
            p.requires_grad = False
            
        # [v4.8] Strict Baseline: Fully Frozen (No partial unfreeze)
        # for p in self.ast.encoder.layer[-1].parameters():
        #     p.requires_grad = True
            
        print("🔒 Backbone (AST) FULLY FROZEN (Strict Baseline)", flush=True)

    def unfreeze_backbone(self, mode="finetune"):
        """[v4.0] LoRA-based Fine-tuning for AST"""
        if mode == "finetune":
            print(f"🧬 [PEFT/LoRA] Applying LoRA to AST backbone (Lightweight r=4)...", flush=True)
            config = LoraConfig(
                r=4,
                lora_alpha=8,
                target_modules=["query", "value"], # [v4.8] Lightweight Focus
                lora_dropout=0.05,
                bias="none",
                task_type=None,
                use_rslora=True
            )
            self.ast = get_peft_model(self.ast, config)
            self.ast.print_trainable_parameters()
        else:
            for p in self.ast.parameters():
                p.requires_grad = True
            print("🔓 Backbone (AST) UNFROZEN (Manual)", flush=True)

    def forward(self, input_values):
        outputs = self.ast(input_values)
        pooled = outputs.last_hidden_state[:, 0, :]  # CLS token → (B, 768)
        
        # Always calculate both heads
        logits_bin = self.binary_head(pooled)
        logits_type = self.type_head(pooled)
        return logits_type, logits_bin

    def get_features(self, input_values):
        """Hybrid Fusion용 feature 추출"""
        outputs = self.ast(input_values)
        return outputs.last_hidden_state[:, 0, :]


# =============================================================================
# 2. 평가 함수
# =============================================================================

def evaluate_model(model, loader, desc="Eval"):
    model.eval()
    all_tp, all_tl, all_ap, all_al = [], [], [], []

    with torch.no_grad():
        for batch in loader:
            ast_in = batch["ast_input"].to(DEVICE)
            t_lbl = batch["type_label"].to(DEVICE)
            a_lbl = batch["abnormal_label"].to(DEVICE)
            t_log, b_log = model(ast_in)

            b_pred = torch.argmax(b_log, dim=1) 
            t_probs = torch.softmax(t_log[:, :3], dim=1) 
            max_p, t_preds = torch.max(t_probs, dim=1) 
            
            final_preds = torch.zeros_like(b_pred)
            is_abn_pred = (b_pred == 1)
            is_other = is_abn_pred & (max_p < OTHER_THRESHOLD)
            is_typed = is_abn_pred & (~is_other)
            
            final_preds[is_other] = 4
            final_preds[is_typed] = t_preds[is_typed] + 1
            
            gt_5class = torch.zeros_like(a_lbl)
            is_abn_gt = (a_lbl == 1)
            gt_5class[is_abn_gt] = t_lbl[is_abn_gt] + 1
            
            all_tp.extend(final_preds.cpu().numpy())
            all_tl.extend(gt_5class.cpu().numpy())
            all_ap.extend(b_pred.cpu().numpy())
            all_al.extend(a_lbl.cpu().numpy())

    all_al_np, all_ap_np = np.array(all_al), np.array(all_ap)
    abn_p, abn_r, abn_f1, _ = precision_recall_fscore_support(all_al_np, all_ap_np, average='binary', zero_division=0)
    all_tl_np, all_tp_np = np.array(all_tl), np.array(all_tp)
    
    if len(all_tl_np) > 0:
        balanced_acc = balanced_accuracy_score(all_tl_np, all_tp_np)
        acc = accuracy_score(all_tl_np, all_tp_np)
        t_p, t_r, t_f1, _ = precision_recall_fscore_support(all_tl_np, all_tp_np, labels=[0, 1, 2, 3, 4], average='macro', zero_division=0)
    else:
        acc = balanced_acc = t_p = t_r = t_f1 = 0.0

    uncertain_pct = (all_tp_np == 4).mean() * 100
    starter_f1 = engine_f1 = brake_f1 = 0.0

    print(f"\n{'='*60}")
    print(f"📊 [{desc}] Hierarchical Report")
    print(f"{'='*60}")
    print(f"  1️⃣  Abnormal Detection: P={abn_p:.4f} R={abn_r:.4f} F1={abn_f1:.4f}")
    print(f"  2️⃣  System Type (5-Class): Acc={acc:.4f} BAcc={balanced_acc:.4f} F1={t_f1:.4f} | Uncert={uncertain_pct:.1f}%")
    
    if len(all_tl_np) > 0:
        DISP = ["normal"] + TYPE_LABELS
        report = classification_report(all_tl_np, all_tp_np, labels=[0, 1, 2, 3, 4], target_names=DISP, zero_division=0, output_dict=True)
        cm = confusion_matrix(all_tl_np, all_tp_np, labels=[0, 1, 2, 3, 4])
        print(f"\n   [Confusion Matrix (5-class Hierarchical)]")
        head_str = " " * 15
        for d in DISP: head_str += f"{d:>9}"
        print(head_str)
        for i, row in enumerate(cm):
            row_str = f"{DISP[i]:>13} | "
            for val in row: row_str += f"{val:>9}"
            print(row_str)
        starter_f1 = report["starter"]["f1-score"]
        engine_f1 = report["engine"]["f1-score"]
        brake_f1 = report["brake"]["f1-score"]

    return {
        "abnormal_f1": abn_f1, "abnormal_recall": abn_r, "abnormal_precision": abn_p,
        "type_macro_f1": t_f1, "type_macro_recall": t_r, "type_macro_precision": t_p,
        "type_acc": acc, "type_balanced_acc": balanced_acc,
        "starter_f1": starter_f1, "engine_f1": engine_f1, "brake_f1": brake_f1,
        "uncertain_pct": round(uncertain_pct, 2)
    }, (all_al_np, all_ap_np)

def get_scores_and_features(model, loader):
    """지표 계산을 위한 예측 점수와 feature(Normal 위주) 추출"""
    model.eval()
    all_scores = []
    all_labels = []
    all_features = []
    
    with torch.no_grad():
        for batch in loader:
            ast_in = batch["ast_input"].to(DEVICE)
            a_lbl = batch["abnormal_label"].to(DEVICE)
            
            # Forward for logits
            t_log, b_log = model(ast_in)
            probs = torch.softmax(b_log, dim=1)[:, 1] # Abnormal probability
            
            # Features (Normal only for NRS/Divergence)
            feats = model.get_features(ast_in)
            
            all_scores.extend(probs.cpu().numpy())
            all_labels.extend(a_lbl.cpu().numpy())
            all_features.append(feats.cpu().numpy())
            
    return np.array(all_labels), np.array(all_scores), np.concatenate(all_features, axis=0)


# =============================================================================
# 3. 학습 함수
# =============================================================================

def train(mode, epochs=None, batch_size=None, lr=None):
    print(f"\n🚀 AST Multi-Task Training — Mode: {mode.upper()}\n", flush=True)

    if mode == "baseline":
        epochs = epochs or COMMON_CONFIG["baseline_epochs"]
        lr = lr or COMMON_CONFIG["lr_baseline"]
    else:
        epochs = epochs or COMMON_CONFIG["finetune_epochs"]
        lr = lr or COMMON_CONFIG["lr_lora_head"] # Using head LR as base for finetune

    batch_size = batch_size or (32 if DEVICE.type == "cuda" and torch.cuda.get_device_properties(0).total_memory > 16e9 else COMMON_CONFIG["batch_size"])
    grad_accum = COMMON_CONFIG["grad_accum"]
    fp16 = torch.cuda.is_available()

    # ── Model ──
    fe = ASTFeatureExtractor.from_pretrained(DEFAULT_AST_MODEL)
    model = ASTMultiTask().to(DEVICE)

    if mode == "baseline":
        model.freeze_backbone()
        for p in model.binary_head.parameters(): p.requires_grad = True
        for p in model.type_head.parameters(): p.requires_grad = True
        
        print(f"🔒 Baseline Optimization: Fixed LR={lr}, Weight Decay=0.1, No Scheduler", flush=True)
        optimizer = torch.optim.AdamW(filter(lambda p: p.requires_grad, model.parameters()), lr=lr, weight_decay=0.1)
        scheduler = None # [v4.8] No scheduler
    else:
        # [v4.8] Load Baseline Weights for Fine-tune (CRITICAL FIX)
        baseline_path = os.path.join(SAVE_ROOT, "ast_baseline", "best_model.pt")
        if os.path.exists(baseline_path):
            print(f"📥 Loading Baseline Weights from {baseline_path}...", flush=True)
            # Load Weights (Strict=False allows LoRA mismatch if applied later)
            state_dict = torch.load(baseline_path, map_location=DEVICE, weights_only=False)
            model.load_state_dict(state_dict, strict=False)
        else:
            print(f"⚠️  Baseline weights not found at {baseline_path}! Training from scratch intent?", flush=True)

        backbone_lr = COMMON_CONFIG["lr_lora_backbone"]
        head_lr = COMMON_CONFIG["lr_lora_head"]
        
        print(f"🔓 LoRA Fine-tune: Backbone (LoRA) LR={backbone_lr:.1e}, Head LR={head_lr:.1e}", flush=True)
        model.unfreeze_backbone(mode="finetune")
        
        optimizer = torch.optim.AdamW([
            {"params": model.ast.parameters(), "lr": backbone_lr},
            {"params": model.type_head.parameters(), "lr": head_lr},
            {"params": model.binary_head.parameters(), "lr": head_lr},
        ])
        
        # ── Cosine Scheduler with 10% Linear Warmup ──
        # Data loader needed to calculate steps
        train_loader, _, _, _, _, _ = create_dataloaders("ast", feature_extractor=fe, batch_size=batch_size)
        total_steps = epochs * len(train_loader)
        warmup_steps = int(total_steps * 0.1)
        
        def lr_lambda(current_step):
            if current_step < warmup_steps:
                return float(current_step) / float(max(1, warmup_steps))
            progress = float(current_step - warmup_steps) / float(max(1, total_steps - warmup_steps))
            return 0.5 * (1.0 + np.cos(np.pi * progress))
            
        scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda=lr_lambda)
        print(f"📈 Scheduler: Cosine with {warmup_steps} warmup steps", flush=True)

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(f"📐 Trainable: {trainable:,} / {total:,} ({trainable/total*100:.1f}%)", flush=True)

    # Re-call create_dataloaders to get all loaders
    train_loader, val_loader, val_loader_balanced, test_loader, test_loader_balanced, type_weights = create_dataloaders("ast", feature_extractor=fe, batch_size=batch_size)

    criterion_type = nn.CrossEntropyLoss(weight=type_weights[:3], ignore_index=-100)
    criterion_bin = nn.CrossEntropyLoss()
    scaler = torch.amp.GradScaler('cuda', enabled=fp16)

    save_dir = os.path.join(SAVE_ROOT, f"ast_{mode}")
    os.makedirs(save_dir, exist_ok=True)
    best_f1 = 0
    early_stop = EarlyStopping(patience=COMMON_CONFIG["early_stop_patience"], min_epochs=COMMON_CONFIG["early_stop_min_epochs"])

    for epoch in range(epochs):
        model.train()
        total_loss = 0
        optimizer.zero_grad()
        print(f"📁 [Epoch {epoch+1}/{epochs}]", end=" ", flush=True)

        for i, batch in enumerate(train_loader):
            with torch.amp.autocast('cuda', enabled=fp16):
                ast_in = batch["ast_input"].to(DEVICE)
                t_lbl = batch["type_label"].to(DEVICE)
                a_lbl = batch["abnormal_label"].to(DEVICE)
                t_log, b_log = model(ast_in)

                loss_bin = criterion_bin(b_log, a_lbl)
                abn_mask = (a_lbl == 1)
                if abn_mask.sum() > 0:
                    loss_type = criterion_type(t_log[abn_mask][:, :3], t_lbl[abn_mask])
                else:
                    loss_type = torch.tensor(0.0).to(DEVICE)
                
                loss = (loss_bin + COMMON_CONFIG["lambda_type"] * loss_type) / grad_accum

            if not torch.isnan(loss):
                scaler.scale(loss).backward()
            if (i + 1) % grad_accum == 0:
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), COMMON_CONFIG["max_grad_norm"])
                scaler.step(optimizer); scaler.update(); optimizer.zero_grad()
                if mode != "baseline": scheduler.step()
            total_loss += loss.item() * grad_accum
            if (i + 1) % 10 == 0 or (i + 1) == len(train_loader):
                print(f"[{i+1}/{len(train_loader)}]", end=" ", flush=True)

        print(f"\n⏳ Validating...", flush=True)
        metrics, _ = evaluate_model(model, val_loader, f"Epoch {epoch+1} Valid")
        combined_score = (metrics["abnormal_f1"] + metrics["type_macro_f1"] + metrics["type_acc"]) / 3
        print(f"📈 Epoch {epoch+1}/{epochs} | Score: {combined_score:.4f}")
        
        # [v4.8] No epoch-level scheduler step needed for Baseline (Fixed LR) or Fine-tune (Per-batch)
        # if mode == "baseline": scheduler.step(combined_score)

        if combined_score > best_f1:
            best_f1 = combined_score
            torch.save(model.state_dict(), os.path.join(save_dir, "best_model.pt"))
            print(f"💾 Best @ {best_f1:.4f}")

        if early_stop.step(combined_score, epoch):
            break

    # ── Test ──
    print(f"\n{'='*80}\n🏁 FINAL TEST EVALUATION")
    best_path = os.path.join(save_dir, "best_model.pt")
    if os.path.exists(best_path):
        model.load_state_dict(torch.load(best_path, map_location=DEVICE, weights_only=False))
    
    test_metrics, _ = evaluate_model(model, test_loader, desc="FINAL TEST (ORIGINAL)")
    balanced_metrics, _ = evaluate_model(model, test_loader_balanced, desc="FINAL TEST (BALANCED SUBSET)")

    # ── Advanced Metrics (Operational) ──
    print(f"🧪 Calculating Advanced Metrics (FPR@P99x, TRR, NRS, Div)...", flush=True)
    # 1. Test Scores/Feats
    test_labels, test_scores, test_feats = get_scores_and_features(model, test_loader)
    
    # 2. Train Feats (Normal only, for Divergence) - use a subset for speed
    train_subset_loader = torch.utils.data.DataLoader(
        train_loader.dataset, batch_size=batch_size, shuffle=False, num_workers=0
    )
    # Limit train feature extraction to first 500 samples for efficiency
    max_train_feats = 500
    train_labels, _, train_feats = get_scores_and_features(model, train_subset_loader)
    train_feats_normal = train_feats[train_labels == 0][:max_train_feats]
    
    test_feats_normal = test_feats[test_labels == 0]
    test_scores_normal = test_scores[test_labels == 0]

    fpr_metrics = calculate_fpr_at_recall(test_labels, test_scores)
    trr = calculate_trr(test_scores_normal)
    nrs = calculate_nrs(test_feats_normal)
    div = calculate_divergence(train_feats_normal, test_feats_normal)

    dummy = torch.randn(1, 1024, 128).to(DEVICE)
    latency = measure_latency(model, dummy, DEVICE)
    model_size = os.path.getsize(best_path) / (1024**2) if os.path.exists(best_path) else 0
    
    final = {
        "model": "ast", "mode": mode, 
        **test_metrics, 
        **fpr_metrics,
        "trr": round(trr, 4), "nrs": round(nrs, 4), "divergence": round(div, 4),
        "balanced_macro_f1": balanced_metrics["type_macro_f1"],
        "latency_ms": round(latency, 1), 
        "model_size_mb": round(model_size, 1)
    }
    save_metrics("ast", mode, final)
    print(f"\n✅ AST {mode.upper()} complete!\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["baseline", "finetune"], required=True)
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--batch_size", type=int, default=None)
    parser.add_argument("--lr", type=float, default=None)
    args = parser.parse_args()
    train(args.mode, args.epochs, args.batch_size, args.lr)
