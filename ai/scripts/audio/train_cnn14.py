# ai/scripts/audio/train_cnn14.py
"""
🏭 CNN14 (PANNs Cnn14_16k) — Multi-Task 2-Head 학습

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
    COMMON_CONFIG, DEVICE, SAVE_ROOT, NUM_TYPE_CLASSES
)
from ai.scripts.audio.data_loader import create_dataloaders

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

        # Dual heads
        self.fc1 = nn.Linear(1024, 512)
        self.dropout = nn.Dropout(0.3)
        self.type_head = nn.Linear(512, NUM_TYPE_CLASSES)      # 3-class
        self.abnormal_head = nn.Linear(512, 1)                  # binary

    def forward(self, x):
        if x.dim() == 3:
            x = x.unsqueeze(1)  # (B, freq, time) → (B, 1, freq, time)
        x = self.conv_blocks(x)
        x = torch.mean(x, dim=(2, 3))  # Global Average Pooling → (B, 1024)
        x = self.dropout(F.relu(self.fc1(x)))  # (B, 512)
        type_logits = self.type_head(x)         # (B, 3)
        abnormal_logits = self.abnormal_head(x).squeeze(-1)  # (B,)
        return type_logits, abnormal_logits

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
            t_log, a_log = model(mel)

            # Abnormal prediction
            a_pred = (torch.sigmoid(a_log) > 0.5).cpu().numpy().astype(int)
            a_label = batch["abnormal_label"].numpy().astype(int)

            # Type prediction with Decision Layer Simulation
            # Service triggers LLM if confidence < 0.6 (T_LOW)
            t_probs = torch.softmax(t_log, dim=1)
            max_p, preds = torch.max(t_probs, dim=1)
            preds_with_other = preds.clone()
            
            # Decision Layer Simulation (Gate 3/4 Trigger):
            # If confidence < 0.6, it marks as 'other' for Uncertain % calculation
            preds_with_other[max_p < 0.6] = 3  # T_LOW from audio_llm_fallback.py
            
            all_tp.extend(preds_with_other.cpu().numpy())
            all_tl.extend(batch["type_label"].numpy())
            all_ap.extend(a_pred)
            all_al.extend(a_label)

    # ── Step 1: Abnormal Detection (전체 샘플) ──
    all_al_np = np.array(all_al)
    all_ap_np = np.array(all_ap)
    abn_p, abn_r, abn_f1, _ = precision_recall_fscore_support(all_al_np, all_ap_np, average='binary', zero_division=0)

    # ── Step 2: Sound Type Classification (GT-Abnormal only) ──
    all_tl_np = np.array(all_tl)
    all_tp_np = np.array(all_tp)
    mask = (all_tl_np != -100)
    hier_tl, hier_tp = all_tl_np[mask], all_tp_np[mask]

    if len(hier_tl) > 0:
        valid_mask = (hier_tp != 3)
        if valid_mask.any():
            balanced_acc = balanced_accuracy_score(hier_tl[valid_mask], hier_tp[valid_mask])
        else:
            balanced_acc = 0.0
        acc = accuracy_score(hier_tl, hier_tp)
        t_p, t_r, t_f1, _ = precision_recall_fscore_support(hier_tl, hier_tp, labels=[0, 1, 2], average='macro', zero_division=0)
    else:
        acc = balanced_acc = t_p = t_r = t_f1 = 0.0

    # ── Step 3: Uncertain (LLM Fallback) Rate ──
    uncertain_pct = (all_tp_np == 3).mean() * 100

    # ── Report ──
    print(f"\n{'='*60}", flush=True)
    print(f"📊 [{desc}] Evaluation Report", flush=True)
    print(f"{'='*60}", flush=True)
    print(f"\n## 1️⃣  Abnormal Detection (Primary)", flush=True)
    print(f"   Precision: {abn_p:.4f} | Recall: {abn_r:.4f} | F1: {abn_f1:.4f}", flush=True)
    print(f"\n## 2️⃣  Sound Type Classification (Abnormal subset, Secondary)", flush=True)
    print(f"   Accuracy: {acc:.4f} | Balanced Acc: {balanced_acc:.4f} | Uncertain: {uncertain_pct:.1f}%", flush=True)
    print(f"   Macro P: {t_p:.4f} | Macro R: {t_r:.4f} | Macro F1: {t_f1:.4f}", flush=True)

    if len(hier_tl) > 0:
        print(f"\n   [Per-class Report]", flush=True)
        report = classification_report(hier_tl, hier_tp, labels=[0, 1, 2], target_names=TYPE_LABELS, zero_division=0, output_dict=True)
        print(classification_report(hier_tl, hier_tp, labels=[0, 1, 2], target_names=TYPE_LABELS, zero_division=0), flush=True)
        
        starter_f1 = report["starter"]["f1-score"]
        engine_f1 = report["engine"]["f1-score"]
        brake_f1 = report["brake"]["f1-score"]

        DISP = TYPE_LABELS + ["other"]
        cm = confusion_matrix(hier_tl, hier_tp, labels=[0, 1, 2, 3])
        print(f"   [Confusion Matrix (including 'other')]", flush=True)
        print(f"   {'':>10} " + " ".join([f"{l:>8}" for l in DISP]), flush=True)
        for i in range(len(TYPE_LABELS)):
            print(f"   {TYPE_LABELS[i]:>10} | " + " ".join([f"{v:>8}" for v in cm[i]]), flush=True)
    else:
        starter_f1 = engine_f1 = brake_f1 = 0.0

    print(f"{'='*60}\n", flush=True)

    return {
        "abnormal_f1": abn_f1, "abnormal_recall": abn_r, "abnormal_precision": abn_p,
        "type_macro_f1": t_f1, "type_macro_recall": t_r, "type_macro_precision": t_p,
        "type_acc": acc, "type_balanced_acc": balanced_acc,
        "starter_f1": starter_f1, "engine_f1": engine_f1, "brake_f1": brake_f1,
        "uncertain_pct": round(uncertain_pct, 2)
    }


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

    # ── Freeze Logic ──
    if mode == "baseline":
        print("🔒 Backbone FROZEN (conv_blocks) — heads only", flush=True)
        for name, p in model.named_parameters():
            if "type_head" in name or "abnormal_head" in name or "fc1" in name:
                p.requires_grad = True
            else:
                p.requires_grad = False
    else:
        print("🔓 ALL parameters UNFROZEN — full fine-tune", flush=True)
        for p in model.parameters():
            p.requires_grad = True

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(f"📐 Trainable: {trainable:,} / {total:,} ({trainable/total*100:.1f}%)", flush=True)

    # ── Data ──
    train_loader, val_loader, test_loader, type_weights = create_dataloaders("cnn", batch_size=batch_size)

    # ── Optimizer ──
    if mode == "baseline":
        optimizer = torch.optim.AdamW(filter(lambda p: p.requires_grad, model.parameters()), lr=lr)
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='max', factor=0.5, patience=2, verbose=True)
    else:
        optimizer = torch.optim.AdamW(model.parameters(), lr=lr)
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    criterion_type = nn.CrossEntropyLoss(weight=type_weights, ignore_index=-100)
    criterion_abn = nn.BCEWithLogitsLoss()
    scaler = torch.amp.GradScaler('cuda', enabled=fp16)

    # ── Training Loop ──
    save_dir = os.path.join(SAVE_ROOT, f"cnn14_{mode}")
    os.makedirs(save_dir, exist_ok=True)
    best_f1 = 0
    early_stop = EarlyStopping(patience=COMMON_CONFIG["early_stop_patience"], min_epochs=COMMON_CONFIG["early_stop_min_epochs"])

    print(f"\n🔔 Starting Training Loop ({epochs} epochs)...\n", flush=True)

    for epoch in range(epochs):
        model.train()
        total_loss = 0
        optimizer.zero_grad()
        print(f"📁 [Epoch {epoch+1}/{epochs}]", end=" ", flush=True)

        for i, batch in enumerate(train_loader):
            with torch.amp.autocast('cuda', enabled=fp16):
                mel = batch["mel_input"].to(DEVICE)
                t_lbl = batch["type_label"].to(DEVICE)
                a_lbl = batch["abnormal_label"].to(DEVICE)

                t_log, a_log = model(mel)

                # Gated Type Loss — GT-Abnormal only
                is_abn = (a_lbl == 1)
                if is_abn.any():
                    loss_t = criterion_type(t_log[is_abn], t_lbl[is_abn])
                else:
                    loss_t = 0.0

                loss = (loss_t + criterion_abn(a_log, a_lbl)) / grad_accum

            scaler.scale(loss).backward()
            if (i + 1) % grad_accum == 0:
                scaler.step(optimizer)
                scaler.update()
                optimizer.zero_grad()

            total_loss += loss.item() * grad_accum
            if (i + 1) % 10 == 0 or (i + 1) == len(train_loader):
                print(f"[{i+1}/{len(train_loader)}]", end=" ", flush=True)

        # ── Validation ──
        print(f"\n⏳ Validating...", flush=True)
        metrics = evaluate_model(model, val_loader, f"Epoch {epoch+1} Valid")
        avg_loss = total_loss / len(train_loader)

        # Combined metric for model selection
        combined_f1 = (metrics["abnormal_f1"] + metrics["type_macro_f1"]) / 2
        print(f"📈 Epoch {epoch+1}/{epochs} | Loss: {avg_loss:.4f} | Abn Recall: {metrics['abnormal_recall']:.4f} | Abn F1: {metrics['abnormal_f1']:.4f} | Type F1: {metrics['type_macro_f1']:.4f} | Combined: {combined_f1:.4f}", flush=True)

        # ── Scheduler ──
        if mode == "baseline":
            scheduler.step(combined_f1)
        else:
            scheduler.step()

        # ── Save Best ──
        if combined_f1 > best_f1:
            best_f1 = combined_f1
            torch.save(model.state_dict(), os.path.join(save_dir, "best_model.pt"))
            print(f"💾 Best model saved (F1={best_f1:.4f})", flush=True)

        # ── Early Stopping ──
        if early_stop.step(combined_f1, epoch):
            break

    # ── Test Evaluation ──
    print(f"\n{'='*60}", flush=True)
    print(f"🏁 FINAL TEST EVALUATION — CNN14 {mode.upper()}", flush=True)
    print(f"{'='*60}", flush=True)

    best_path = os.path.join(save_dir, "best_model.pt")
    if os.path.exists(best_path):
        model.load_state_dict(torch.load(best_path, map_location=DEVICE, weights_only=True))
    model = model.to(DEVICE)

    test_metrics = evaluate_model(model, test_loader, "FINAL TEST")

    # ── Latency 측정 ──
    dummy_mel = torch.randn(1, 128, 501).to(DEVICE)  # 5초 @ 16kHz mel
    latency = measure_latency(model, dummy_mel, DEVICE)

    # ── Model Size ──
    model_size_mb = os.path.getsize(best_path) / (1024 * 1024) if os.path.exists(best_path) else 0

    # ── Save Metrics ──
    final_metrics = {
        "model": "cnn14",
        "mode": mode,
        **test_metrics,
        "latency_ms": round(latency, 1),
        "model_size_mb": round(model_size_mb, 1),
    }
    save_metrics("cnn14", mode, final_metrics)
    print(f"\n✅ CNN14 {mode.upper()} training complete!\n", flush=True)
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
