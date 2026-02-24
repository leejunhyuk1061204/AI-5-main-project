# ai/scripts/audio/train_cnn14.py
"""
[파일 용도] CNN14 (PANNs Cnn14_16k) 모델 학습

[Architecture]
- Backbone: CNN14Lite (PANNs pretrained)
- Head 1: abnormal_head (binary) → Abnormal Detection
- Head 2: type_head (3-class) → Sound Type Classification (Gated: GT-Abnormal only)

[Usage]
  Baseline:  python -m ai.scripts.audio.train_cnn14 --mode baseline
  Fine-tune: python -m ai.scripts.audio.train_cnn14 --mode finetune
"""
import os, sys, argparse, json
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from pathlib import Path
from collections import Counter
from sklearn.metrics import (
    precision_recall_fscore_support, accuracy_score,
    confusion_matrix, balanced_accuracy_score, classification_report
)

from ai.scripts.audio.config import (
    set_seed, save_metrics, measure_latency, EarlyStopping,
    TYPE_LABELS, type2id, id2type, ABNORMAL_LABELS, OTHER_THRESHOLD,
    ABNORMAL_THRESHOLD, COMMON_CONFIG, DEVICE, SAVE_ROOT, NUM_TYPE_CLASSES
)
from ai.scripts.audio.data_loader import create_dataloaders
from ai.scripts.audio.advanced_metrics import calculate_fpr_at_recall, calculate_trr, calculate_nrs, calculate_divergence

set_seed(42)


# =============================================================================
# 1. 모델 정의 — CNN14Lite + Multi-Task Heads
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


class CNN14MultiTask(nn.Module):
    """CNN14 Lite + Multi-Task Dual Heads"""
    def __init__(self):
        super().__init__()
        self.conv_blocks = nn.Sequential(
            ConvBlock(1, 64),
            ConvBlock(64, 128),
            ConvBlock(128, 256),
            ConvBlock(256, 512),
            ConvBlock(512, 1024),
        )

        # [Strict v3.7] Purified Two-Head Structure
        self.fc1 = nn.Linear(1024, 512)
        self.dropout = nn.Dropout(0.3)
        
        # Head A: Binary (Normal, Abnormal)
        self.binary_head = nn.Linear(512, 2)
        # Head B: Multi-class (Starter, Engine, Brake, Other)
        self.type_head = nn.Linear(512, 4)

    def freeze_backbone(self):
        # Freeze all backbone
        for p in self.conv_blocks.parameters(): p.requires_grad = False
        for p in self.fc1.parameters(): p.requires_grad = False
        
        # [v3.8] Partial Unfreeze: Last ConvBlock + FC1
        # conv_blocks has 5 layers (indices 0~4)
        for p in self.conv_blocks[4].parameters(): p.requires_grad = True
        for p in self.fc1.parameters(): p.requires_grad = True
        
        print("🔒 Backbone (CNN14) FROZEN (Except last block & fc1)", flush=True)

    def unfreeze_backbone(self):
        for p in self.conv_blocks.parameters(): p.requires_grad = True
        for p in self.fc1.parameters(): p.requires_grad = True
        print("🔓 Backbone (CNN14) UNFROZEN", flush=True)

    def forward(self, x):
        if x.dim() == 3:
            x = x.unsqueeze(1)  # (B, freq, time) → (B, 1, freq, time)
        x = self.conv_blocks(x)
        x = torch.mean(x, dim=(2, 3))  # Global Average Pooling → (B, 1024)
        x = self.dropout(F.relu(self.fc1(x)))  # (B, 512)
        
        # [Strict v3.7] Always calculate both heads (No conditional forward)
        logits_bin = self.binary_head(x)
        logits_type = self.type_head(x)
        return logits_type, logits_bin

    def get_features(self, x):
        """Hybrid Fusion용 feature 추출"""
        if x.dim() == 3:
            x = x.unsqueeze(1)
        x = self.conv_blocks(x)
        x = torch.mean(x, dim=(2, 3))
        return x  # (B, 1024)

    def load_pretrained_weights(self):
        """PANNs Cnn14_16k pretrained weights 로드"""
        import requests
        url = "https://zenodo.org/record/3987831/files/Cnn14_16k_mAP%3D0.438.pth?download=1"
        path = Path("ai/weights/audio/Cnn14_16k_mAP=0.438.pth")

        if not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)

        if not path.exists():
            print("[CNN14] Downloading pretrained weights...", flush=True)
            try:
                response = requests.get(url, timeout=120)
                path.write_bytes(response.content)
                print("[CNN14] Download complete.", flush=True)
            except Exception as e:
                print(f"[CNN14] Download failed: {e}. Random init.", flush=True)
                return False

        try:
            print(f"[CNN14] Loading weights from {path}...", flush=True)
            pretrained_dict = torch.load(path, map_location="cpu", weights_only=False)
            if 'model' in pretrained_dict:
                pretrained_dict = pretrained_dict['model']

            model_dict = self.state_dict()
            mapped_dict = {}
            for k, v in pretrained_dict.items():
                new_k = k
                if k.startswith("conv_block"):
                    try:
                        num = int(k.split(".")[0].replace("conv_block", ""))
                        new_k = k.replace(f"conv_block{num}", f"conv_blocks.{num-1}")
                    except:
                        pass
                if new_k in model_dict and v.shape == model_dict[new_k].shape:
                    mapped_dict[new_k] = v

            model_dict.update(mapped_dict)
            self.load_state_dict(model_dict)
            print(f"[CNN14] Loaded {len(mapped_dict)}/{len(model_dict)} layers.", flush=True)
            return True
        except Exception as e:
            print(f"[CNN14] Weight loading error: {e}", flush=True)
            return False


# =============================================================================
# 2. 평가 함수 — Multi-Task 2-Head
# =============================================================================

def evaluate_model(model, loader, desc="Eval"):
    model.eval()
    all_tp, all_tl, all_ap, all_al = [], [], [], []

    with torch.no_grad():
        for batch in loader:
            mel = batch["mel_input"].to(DEVICE)
            t_lbl = batch["type_label"].to(DEVICE)
            a_lbl = batch["abnormal_label"].to(DEVICE)
            t_log, b_log = model(mel)

            # [Strict Hierarchical Inference v3.7 - Option A]
            # 1. Abnormal Detection (Binary Head: 2 outputs)
            b_pred = torch.argmax(b_log, dim=1) 
            
            # 2. Type Classification (Only index 0, 1, 2 for confidence check)
            t_probs = torch.softmax(t_log[:, :3], dim=1) 
            max_p, t_preds = torch.max(t_probs, dim=1) 
            
            # Initialize as Normal (0)
            final_preds = torch.zeros_like(b_pred)
            
            # Mask for Abnormal predictions
            is_abn_pred = (b_pred == 1)
            is_other = is_abn_pred & (max_p < OTHER_THRESHOLD)
            is_typed = is_abn_pred & (~is_other)
            
            final_preds[is_other] = 4 # Other (Global ID)
            final_preds[is_typed] = t_preds[is_typed] + 1 # 1:Starter, 2:Engine, 3:Brake
            
            # GT Mapping
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

    print(f"\n{'='*60}", flush=True)
    print(f"📊 [{desc}] Hierarchical Report", flush=True)
    print(f"{'='*60}", flush=True)
    print(f"  1️⃣  Abnormal Detection: P={abn_p:.4f} R={abn_r:.4f} F1={abn_f1:.4f}", flush=True)
    print(f"  2️⃣  System Type (5-Class): Acc={acc:.4f} BAcc={balanced_acc:.4f} F1={t_f1:.4f} | Uncert={uncertain_pct:.1f}%", flush=True)
    
    if len(all_tl_np) > 0:
        DISP = ["normal"] + TYPE_LABELS
        print(f"\n   [Classification Report (Method A)]", flush=True)
        print(classification_report(all_tl_np, all_tp_np, labels=[0, 1, 2, 3, 4], target_names=DISP, zero_division=0), flush=True)
        
        report = classification_report(all_tl_np, all_tp_np, labels=[0, 1, 2, 3, 4], target_names=DISP, zero_division=0, output_dict=True)
        starter_f1 = report["starter"]["f1-score"]
        engine_f1 = report["engine"]["f1-score"]
        brake_f1 = report["brake"]["f1-score"]
        cm = confusion_matrix(all_tl_np, all_tp_np, labels=[0, 1, 2, 3, 4])
        print(f"\n   [Confusion Matrix (5-class Hierarchical)]", flush=True)
        head_str = " " * 15
        for d in DISP: head_str += f"{d:>9}"
        print(head_str, flush=True)
        for i, row in enumerate(cm):
            row_str = f"{DISP[i]:>13} | "
            for val in row: row_str += f"{val:>9}"
            print(row_str, flush=True)
        print(f"{'='*60}\n", flush=True)
    else:
        starter_f1 = engine_f1 = brake_f1 = 0.0

    return {
        "abnormal_f1": abn_f1, "abnormal_recall": abn_r, "abnormal_precision": abn_p,
        "type_macro_f1": t_f1, "type_macro_recall": t_r, "type_macro_precision": t_p,
        "type_acc": acc, "type_balanced_acc": balanced_acc,
        "starter_f1": starter_f1, "engine_f1": engine_f1, "brake_f1": brake_f1,
        "uncertain_pct": round(uncertain_pct, 2)
    }, (all_al_np, all_ap_np)

def get_scores_and_features(model, loader):
    """지표 계산을 위한 예측 점수와 feature 추출"""
    model.eval()
    all_scores = []
    all_labels = []
    all_features = []
    
    with torch.no_grad():
        for batch in loader:
            mel = batch["mel_input"].to(DEVICE)
            a_lbl = batch["abnormal_label"].to(DEVICE)
            
            t_log, b_log = model(mel)
            probs = torch.softmax(b_log, dim=1)[:, 1] # Abnormal probability
            
            feats = model.get_features(mel)
            
            all_scores.extend(probs.cpu().numpy())
            all_labels.extend(a_lbl.cpu().numpy())
            all_features.append(feats.cpu().numpy())
            
    return np.array(all_labels), np.array(all_scores), np.concatenate(all_features, axis=0)


# =============================================================================
# 3. 학습 함수
# =============================================================================

def train(mode, epochs=None, batch_size=None, lr=None):
    print(f"\n{'='*60}", flush=True)
    print(f"🚀 CNN14 Multi-Task Training — Mode: {mode.upper()}", flush=True)
    print(f"{'='*60}\n", flush=True)

    # ── Config ──
    if mode == "baseline":
        epochs = epochs or COMMON_CONFIG["baseline_epochs"]
        lr = lr or COMMON_CONFIG["lr_baseline"]
    else:
        epochs = epochs or COMMON_CONFIG["finetune_epochs"]
        lr = lr or COMMON_CONFIG["lr_finetune"]

    batch_size = batch_size or (32 if DEVICE.type == "cuda" and torch.cuda.get_device_properties(0).total_memory > 16e9 else COMMON_CONFIG["batch_size"])
    grad_accum = COMMON_CONFIG["grad_accum"]
    fp16 = torch.cuda.is_available()

    print(f"⚙️  epochs={epochs}, lr={lr}, batch={batch_size}, fp16={fp16}", flush=True)

    # ── Model ──
    model = CNN14MultiTask()
    model.load_pretrained_weights()
    model = model.to(DEVICE)

    # ── Freeze / Load Logic ──
    if mode == "baseline":
        print("🔒 Backbone FROZEN (Except last block) — heads only", flush=True)
        # Apply partial unfreeze
        model.freeze_backbone()
        
        # Ensure heads are trainable
        for p in model.binary_head.parameters(): p.requires_grad = True
        for p in model.type_head.parameters(): p.requires_grad = True
    else:
        # Fine-tune Mode: Load Baseline Best Weights first (Warm-up)
        baseline_path = os.path.join(SAVE_ROOT, "cnn14_baseline", "best_model.pt")
        if os.path.exists(baseline_path):
            print(f"🔥 Fine-tune: Loading Baseline weights from {baseline_path} (strict=False for v3.7 trans)", flush=True)
            state_dict = torch.load(baseline_path, map_location=DEVICE, weights_only=False)
            # [Strict v3.7] Filter out incompatible heads
            state_dict = {k: v for k, v in state_dict.items() if not k.startswith("type_head") and not k.startswith("binary_head") and not k.startswith("abnormal_head")}
            model.load_state_dict(state_dict, strict=False)
        else:
            print("⚠️  Baseline weights not found. Fine-tuning from pretrained.", flush=True)
            
        print("🔓 ALL parameters UNFROZEN — full fine-tune with differential LR", flush=True)
        for p in model.parameters():
            p.requires_grad = True

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(f"📐 Trainable: {trainable:,} / {total:,} ({trainable/total*100:.1f}%)", flush=True)

    # ── Data ──
    train_loader, val_loader, val_loader_balanced, test_loader, test_loader_balanced, type_weights = create_dataloaders("cnn", batch_size=batch_size)

    # ── Optimizer ──
    if mode == "baseline":
        optimizer = torch.optim.AdamW(filter(lambda p: p.requires_grad, model.parameters()), lr=lr)
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='max', factor=0.5, patience=2)
    else:
        # Differential LR: Backbone (1e-6) vs Head (1e-4) — default lr is typically fine-tune lr (3e-5)
        # We use proportional scaling based on the passed 'lr'
        head_lr = lr * 3  # ~1e-4
        backbone_lr = lr / 10  # ~3e-6
        
        optimizer = torch.optim.AdamW([
            {"params": model.conv_blocks.parameters(), "lr": backbone_lr},
            {"params": model.fc1.parameters(), "lr": head_lr},
            {"params": model.type_head.parameters(), "lr": head_lr},
            {"params": model.binary_head.parameters(), "lr": head_lr},
        ])
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    criterion_type = nn.CrossEntropyLoss(weight=type_weights[:3], ignore_index=-100)
    criterion_bin = nn.CrossEntropyLoss()
    scaler = torch.amp.GradScaler('cuda', enabled=fp16)

    # ── Training Loop ──
    save_dir = os.path.join(SAVE_ROOT, f"cnn14_{mode}")
    os.makedirs(save_dir, exist_ok=True)
    best_f1 = 0
    early_stop = EarlyStopping(patience=COMMON_CONFIG["early_stop_patience"], min_epochs=COMMON_CONFIG["early_stop_min_epochs"])

    print(f"\n🔔 Starting Training Loop ({epochs} epochs)...\n", flush=True)

    for epoch in range(epochs):
        # [Fix] Two-stage Training: Head Stabilization Phase
        if mode == "finetune":
            if epoch < 3:
                model.freeze_backbone()
            elif epoch == 3:
                model.unfreeze_backbone()

        model.train()
        total_loss = 0
        optimizer.zero_grad()
        print(f"📁 [Epoch {epoch+1}/{epochs}]", end=" ", flush=True)

        for i, batch in enumerate(train_loader):
            with torch.amp.autocast('cuda', enabled=fp16):
                mel = batch["mel_input"].to(DEVICE)
                t_lbl = batch["type_label"].to(DEVICE)
                a_lbl = batch["abnormal_label"].to(DEVICE)
                t_log, b_log = model(mel)

                # [Strict v3.7] Loss calculation
                # 1. Binary Loss
                loss_bin = criterion_bin(b_log, a_lbl)
                
                # 2. Type Loss
                abn_mask = (a_lbl == 1)
                if abn_mask.sum() > 0:
                    loss_type = criterion_type(t_log[abn_mask][:, :3], t_lbl[abn_mask])
                else:
                    loss_type = torch.tensor(0.0).to(DEVICE)
                
                loss = (loss_bin + COMMON_CONFIG["lambda_type"] * loss_type) / grad_accum

            if not torch.isnan(loss):
                scaler.scale(loss).backward()
            if (i + 1) % grad_accum == 0:
                # [Fix] Gradient Clipping
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), COMMON_CONFIG["max_grad_norm"])
                
                scaler.step(optimizer); scaler.update(); optimizer.zero_grad()

            total_loss += loss.item() * grad_accum
            if (i + 1) % 10 == 0 or (i + 1) == len(train_loader):
                print(f"[{i+1}/{len(train_loader)}]", end=" ", flush=True)

        # ── Validation ──
        print(f"\n⏳ Validating...", flush=True)
        metrics, _ = evaluate_model(model, val_loader, f"Epoch {epoch+1} Valid")
        avg_loss = total_loss / len(train_loader)

        # Combined metric for model selection (Balanced)
        combined_score = (metrics["abnormal_f1"] + metrics["type_macro_f1"] + metrics["type_acc"]) / 3
        print(f"📈 Epoch {epoch+1}/{epochs} | Loss: {avg_loss:.4f} | Abn Recall: {metrics['abnormal_recall']:.4f} | Abn F1: {metrics['abnormal_f1']:.4f} | Type F1: {metrics['type_macro_f1']:.4f} | Type Acc: {metrics['type_acc']:.4f} | Score: {combined_score:.4f}", flush=True)

        # ── Scheduler ──
        if mode == "baseline":
            scheduler.step(combined_score)
        else:
            scheduler.step()

        # ── Save Best ──
        if combined_score > best_f1:
            best_f1 = combined_score
            torch.save(model.state_dict(), os.path.join(save_dir, "best_model.pt"))
            print(f"💾 Best model saved (Score={best_f1:.4f})", flush=True)

        # ── Early Stopping ──
        if early_stop.step(combined_score, epoch):
            break

    # ── [V3.1] Dual Evaluation Strategy — Comparative Report ──
    print(f"\n{'='*80}", flush=True)
    print(f"🏁 DUAL TEST EVALUATION — Original vs Balanced Subset", flush=True)
    print(f"{'='*80}", flush=True)

    best_path = os.path.join(save_dir, "best_model.pt")
    if os.path.exists(best_path):
        model.load_state_dict(torch.load(best_path, map_location=DEVICE, weights_only=True))
    model = model.to(DEVICE)

    # 1. Original Distribution Test
    test_metrics, _ = evaluate_model(model, test_loader, desc="FINAL TEST (ORIGINAL)")
    
    # 2. Balanced Subset Evaluation (Fair Comparison)
    balanced_metrics, _ = evaluate_model(model, test_loader_balanced, desc="FINAL TEST (BALANCED SUBSET)")

    # ── Advanced Metrics (Operational) ──
    print(f"🧪 Calculating Advanced Metrics (FPR@P99x, TRR, NRS, Div)...", flush=True)
    test_labels, test_scores, test_feats = get_scores_and_features(model, test_loader)
    
    train_subset_loader = torch.utils.data.DataLoader(
        train_loader.dataset, batch_size=batch_size, shuffle=False, num_workers=0
    )
    max_train_feats = 500
    train_labels, _, train_feats = get_scores_and_features(model, train_subset_loader)
    train_feats_normal = train_feats[train_labels == 0][:max_train_feats]
    
    test_feats_normal = test_feats[test_labels == 0]
    test_scores_normal = test_scores[test_labels == 0]

    fpr_metrics = calculate_fpr_at_recall(test_labels, test_scores)
    trr = calculate_trr(test_scores_normal)
    nrs = calculate_nrs(test_feats_normal)
    div = calculate_divergence(train_feats_normal, test_feats_normal)

    print(f"\n📊 COMPARATIVE PERFORMANCE REPORT (Test Set)", flush=True)
    print(f"{'-'*80}", flush=True)
    print(f"{'Metric':<25} | {'Original Dist':<15} | {'Balanced Subset':<15} | {'Diff':<10}", flush=True)
    print(f"{'-'*80}", flush=True)
    
    metrics_to_comp = [
        ("Accuracy", "type_acc"),
        ("Balanced Acc", "type_balanced_acc"),
        ("Macro F1", "type_macro_f1"),
        ("Starter F1", "starter_f1"),
        ("Engine F1", "engine_f1"),
        ("Brake F1", "brake_f1"),
    ]
    
    for label, key in metrics_to_comp:
        orig = test_metrics.get(key, 0)
        bal = balanced_metrics.get(key, 0)
        diff = bal - orig
        diff_str = f"{diff:+.4f}" if abs(diff) > 1e-6 else "0.0000"
        print(f"{label:<25} | {orig:<15.4f} | {bal:<15.4f} | {diff_str:<10}", flush=True)
    print(f"{'='*80}\n", flush=True)

    # ── Latency 측정 ──
    dummy_mel = torch.randn(1, 128, 501).to(DEVICE) 
    latency = measure_latency(model, dummy_mel, DEVICE)

    # ── Model Size ──
    model_size_mb = os.path.getsize(best_path) / (1024 * 1024) if os.path.exists(best_path) else 0

    # ── Save Metrics ──
    final_metrics = {
        "model": "cnn14", "mode": mode, 
        **test_metrics, 
        **fpr_metrics,
        "trr": round(trr, 4), "nrs": round(nrs, 4), "divergence": round(div, 4),
        "balanced_type_macro_f1": balanced_metrics["type_macro_f1"],
        "balanced_type_acc": balanced_metrics["type_acc"],
        "latency_ms": round(latency, 1), 
        "model_size_mb": round(model_size_mb, 1)
    }
    save_metrics("cnn14", mode, final_metrics)
    print(f"\n✅ CNN14 {mode.upper()} training complete!\n", flush=True)
    return final_metrics
    return final_metrics


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CNN14 Multi-Task Training")
    parser.add_argument("--mode", choices=["baseline", "finetune"], required=True)
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--batch_size", type=int, default=None)
    parser.add_argument("--lr", type=float, default=None)
    args = parser.parse_args()

    train(args.mode, args.epochs, args.batch_size, args.lr)
