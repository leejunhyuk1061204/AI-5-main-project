# ai/scripts/audio/train_passt.py
"""
🎧 PaSST (Patchout fASt Spectrogram Transformer) — Multi-Task 2-Head 학습

[Architecture]
- Backbone: hear21passt (AudioSet pretrained)
- Head 1: abnormal_head (binary)
- Head 2: type_head (3-class, Gated)

[Usage]
  PaSST-N-S Baseline:    python -m ai.scripts.audio.train_passt --arch passt_s_p16_s16_128_ap468 --mode baseline
  PaSST-N-S Fine-tune:   python -m ai.scripts.audio.train_passt --arch passt_s_p16_s16_128_ap468 --mode finetune
  PaSST-S-SWA Baseline:  python -m ai.scripts.audio.train_passt --arch passt_s_swa_p16_128_ap476 --mode baseline
  PaSST-S-SWA Fine-tune: python -m ai.scripts.audio.train_passt --arch passt_s_swa_p16_128_ap476 --mode finetune
"""
import os, argparse
import torch
import torch.nn as nn
import torchaudio
import numpy as np
from sklearn.metrics import (
    precision_recall_fscore_support, accuracy_score,
    confusion_matrix, balanced_accuracy_score, classification_report
)

from ai.scripts.audio.config import (
    set_seed, save_metrics, measure_latency, EarlyStopping,
    TYPE_LABELS, type2id, ABNORMAL_LABELS, OTHER_THRESHOLD,
    COMMON_CONFIG, DEVICE, SAVE_ROOT, NUM_TYPE_CLASSES
)
from ai.scripts.audio.data_loader import create_dataloaders

set_seed(42)


# =============================================================================
# 1. 모델 정의
# =============================================================================

class PaSSTMultiTask(nn.Module):
    """PaSST backbone + Multi-Task Dual Heads"""
    def __init__(self, arch="passt_s_p16_s16_128_ap468"):
        super().__init__()
        from hear21passt.models.passt import get_model as get_model_passt
        from hear21passt.models.preprocess import AugmentMelSTFT
        self.arch = arch

        # arch별 stride 설정 (s16 모델은 반드시 stride 16 필요)
        if "s16" in arch:
            fstride, tstride = 16, 16
        else:
            fstride, tstride = 10, 10

        # PaSST transformer 직접 로드 (stride 명시)
        self.passt_net = get_model_passt(arch=arch, pretrained=True, fstride=fstride, tstride=tstride)
        # Mel 전처리기 (32kHz 기준, PaSST 공식 설정)
        self.passt_mel = AugmentMelSTFT(
            n_mels=128, sr=32000, win_length=800, hopsize=320,
            n_fft=1024, freqm=48, timem=192,
            htk=False, fmin=0.0, fmax=None, norm=1,
            fmin_aug_range=10, fmax_aug_range=2000
        )
        feat_dim = getattr(self.passt_net, 'embed_dim', 768)
        self.type_head = nn.Linear(feat_dim, NUM_TYPE_CLASSES)
        self.abnormal_head = nn.Linear(feat_dim, 1)

    def forward(self, waveform):
        """waveform: (B, T) raw audio at 16kHz → logits"""
        # Resample 16kHz → 32kHz (passt_mel expects 32kHz)
        waveform_32k = torchaudio.functional.resample(waveform, orig_freq=16000, new_freq=32000)
        # Wrapper's mel: raw 32kHz → log-mel spectrogram (B, 128, T')
        mel = self.passt_mel(waveform_32k)
        mel = mel.unsqueeze(1)                    # (B, 1, 128, T') — PaSST expects this
        x, features = self.passt_net(mel)         # x: (B, 527) logits, features: (B, 768)
        type_logits = self.type_head(features)
        abnormal_logits = self.abnormal_head(features).squeeze(-1)
        return type_logits, abnormal_logits

    def get_features(self, waveform):
        waveform_32k = torchaudio.functional.resample(waveform, orig_freq=16000, new_freq=32000)
        mel = self.passt_mel(waveform_32k)
        mel = mel.unsqueeze(1)
        _, features = self.passt_net(mel)
        return features


# =============================================================================
# 2. 평가 함수
# =============================================================================

def evaluate_model(model, loader, desc="Eval"):
    model.eval()
    all_tp, all_tl, all_ap, all_al = [], [], [], []

    with torch.no_grad():
        for batch in loader:
            raw = batch["raw_audio"].to(DEVICE)
            t_log, a_log = model(raw)

            a_pred = (torch.sigmoid(a_log) > 0.5).cpu().numpy().astype(int)
            a_label = batch["abnormal_label"].numpy().astype(int)

            # Type prediction with Decision Layer Simulation
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

    all_al_np, all_ap_np = np.array(all_al), np.array(all_ap)
    abn_p, abn_r, abn_f1, _ = precision_recall_fscore_support(all_al_np, all_ap_np, average='binary', zero_division=0)

    all_tl_np, all_tp_np = np.array(all_tl), np.array(all_tp)
    mask = (all_tl_np != -100)
    hier_tl, hier_tp = all_tl_np[mask], all_tp_np[mask]

    if len(hier_tl) > 0:
        valid_mask = (hier_tp != 3)
        balanced_acc = balanced_accuracy_score(hier_tl[valid_mask], hier_tp[valid_mask]) if valid_mask.any() else 0.0
        acc = accuracy_score(hier_tl, hier_tp)
        t_p, t_r, t_f1, _ = precision_recall_fscore_support(hier_tl, hier_tp, labels=[0, 1, 2], average='macro', zero_division=0)
    else:
        acc = balanced_acc = t_p = t_r = t_f1 = 0.0

    # ── Step 3: Uncertain (LLM Fallback) Rate ──
    uncertain_pct = (all_tp_np == 3).mean() * 100

    print(f"\n{'='*60}", flush=True)
    print(f"📊 [{desc}]", flush=True)
    print(f"  1️⃣  Abnormal: P={abn_p:.4f} R={abn_r:.4f} F1={abn_f1:.4f}", flush=True)
    print(f"  2️⃣  Type: Acc={acc:.4f} BAcc={balanced_acc:.4f} F1={t_f1:.4f} | Uncert={uncertain_pct:.1f}%", flush=True)
    if len(hier_tl) > 0:
        report = classification_report(hier_tl, hier_tp, labels=[0, 1, 2], target_names=TYPE_LABELS, zero_division=0, output_dict=True)
        print(classification_report(hier_tl, hier_tp, labels=[0, 1, 2], target_names=TYPE_LABELS, zero_division=0), flush=True)
        starter_f1 = report["starter"]["f1-score"]
        engine_f1 = report["engine"]["f1-score"]
        brake_f1 = report["brake"]["f1-score"]
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

def train(arch, mode, epochs=None, batch_size=None, lr=None):
    arch_short = arch.replace("passt_s_swa_p16_128_ap476", "passt_s_swa").replace("passt_s_p16_s16_128_ap468", "passt_n_s")
    print(f"\n🚀 PaSST [{arch_short}] Multi-Task — Mode: {mode.upper()}\n", flush=True)

    if mode == "baseline":
        epochs = epochs or COMMON_CONFIG["baseline_epochs"]
        lr = lr or COMMON_CONFIG["lr_baseline"]
    else:
        epochs = epochs or COMMON_CONFIG["finetune_epochs"]
        lr = lr or COMMON_CONFIG["lr_finetune"]

    batch_size = batch_size or (32 if DEVICE.type == "cuda" and torch.cuda.get_device_properties(0).total_memory > 16e9 else COMMON_CONFIG["batch_size"])
    grad_accum = COMMON_CONFIG["grad_accum"]
    fp16 = torch.cuda.is_available()

    model = PaSSTMultiTask(arch=arch).to(DEVICE)

    # ── Freeze Logic ──
    if mode == "baseline":
        print("🔒 PaSST backbone FROZEN (norm/pos_embed open)", flush=True)
        for p in model.passt_net.parameters():
            p.requires_grad = False
        for p in model.type_head.parameters():
            p.requires_grad = True
        for p in model.abnormal_head.parameters():
            p.requires_grad = True
        # LayerNorm + pos_embed 열기 (domain shift 적응)
        for name, p in model.passt_net.named_parameters():
            if "norm" in name.lower() or "pos_embed" in name.lower():
                p.requires_grad = True
    else:
        print("🔓 ALL parameters UNFROZEN", flush=True)
        for p in model.parameters():
            p.requires_grad = True

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(f"📐 Trainable: {trainable:,} / {total:,} ({trainable/total*100:.1f}%)", flush=True)

    # PaSST uses raw_audio → mel internally, so arch="passt" for data_loader
    train_loader, val_loader, test_loader, type_weights = create_dataloaders("passt", batch_size=batch_size)

    if mode == "baseline":
        optimizer = torch.optim.AdamW(filter(lambda p: p.requires_grad, model.parameters()), lr=lr)
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='max', factor=0.5, patience=2, verbose=True)
    else:
        optimizer = torch.optim.AdamW(model.parameters(), lr=lr)
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    criterion_type = nn.CrossEntropyLoss(weight=type_weights, ignore_index=-100)
    criterion_abn = nn.BCEWithLogitsLoss()
    scaler = torch.amp.GradScaler('cuda', enabled=fp16)

    save_dir = os.path.join(SAVE_ROOT, f"{arch_short}_{mode}")
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
                raw = batch["raw_audio"].to(DEVICE)
                t_lbl = batch["type_label"].to(DEVICE)
                a_lbl = batch["abnormal_label"].to(DEVICE)
                t_log, a_log = model(raw)

                is_abn = (a_lbl == 1)
                loss_t = criterion_type(t_log[is_abn], t_lbl[is_abn]) if is_abn.any() else 0.0
                loss = (loss_t + criterion_abn(a_log, a_lbl)) / grad_accum

            scaler.scale(loss).backward()
            if (i + 1) % grad_accum == 0:
                scaler.step(optimizer); scaler.update(); optimizer.zero_grad()
            total_loss += loss.item() * grad_accum
            if (i + 1) % 10 == 0 or (i + 1) == len(train_loader):
                print(f"[{i+1}/{len(train_loader)}]", end=" ", flush=True)

        print(f"\n⏳ Validating...", flush=True)
        metrics = evaluate_model(model, val_loader, f"Epoch {epoch+1}")
        combined_f1 = (metrics["abnormal_f1"] + metrics["type_macro_f1"]) / 2
        print(f"📈 Epoch {epoch+1}/{epochs} | Abn Recall: {metrics['abnormal_recall']:.4f} | Abn F1: {metrics['abnormal_f1']:.4f} | Type F1: {metrics['type_macro_f1']:.4f} | Combined: {combined_f1:.4f}", flush=True)

        if mode == "baseline":
            scheduler.step(combined_f1)
        else:
            scheduler.step()

        if combined_f1 > best_f1:
            best_f1 = combined_f1
            torch.save(model.state_dict(), os.path.join(save_dir, "best_model.pt"))
            print(f"💾 Best @ {best_f1:.4f}", flush=True)

        if early_stop.step(combined_f1, epoch):
            break

    # ── Test ──
    print(f"\n🏁 FINAL TEST — PaSST [{arch_short}] {mode.upper()}", flush=True)
    best_path = os.path.join(save_dir, "best_model.pt")
    if os.path.exists(best_path):
        model.load_state_dict(torch.load(best_path, map_location=DEVICE, weights_only=False))
    model = model.to(DEVICE)
    test_metrics = evaluate_model(model, test_loader, "FINAL TEST")

    dummy = torch.randn(1, 16000 * 5).to(DEVICE)
    latency = measure_latency(model, dummy, DEVICE)
    model_size = os.path.getsize(best_path) / (1024**2) if os.path.exists(best_path) else 0
    final = {"model": arch_short, "mode": mode, **test_metrics, "latency_ms": round(latency, 1), "model_size_mb": round(model_size, 1)}
    save_metrics(arch_short, mode, final)
    print(f"\n✅ PaSST [{arch_short}] {mode.upper()} complete!\n", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--arch", default="passt_s_p16_s16_128_ap468", help="passt_s_p16_s16_128_ap468 or passt_s_swa_p16_128_ap476")
    parser.add_argument("--mode", choices=["baseline", "finetune"], required=True)
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--batch_size", type=int, default=None)
    parser.add_argument("--lr", type=float, default=None)
    args = parser.parse_args()
    train(args.arch, args.mode, args.epochs, args.batch_size, args.lr)
