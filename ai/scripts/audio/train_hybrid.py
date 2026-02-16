# ai/scripts/audio/train_hybrid.py
"""
🔗 Hybrid Fusion (CNN14 ❄ + Transformer) — Multi-Task 2-Head 학습

[Architecture]
- CNN14 Fine-tuned (FROZEN ❄) → Local texture features (1024-dim)
- Transformer (AST or PaSST, TRAINABLE) → Global context features (768-dim)
- FusionHead (TRAINABLE) → Concatenated features (1792) → Dual heads

[Usage]
  AST+CNN14:       python -m ai.scripts.audio.train_hybrid --teacher ast --epochs 20
  PaSST-N-S+CNN14: python -m ai.scripts.audio.train_hybrid --teacher passt_s_p16_s16_128_ap468 --epochs 20
  PaSST-SWA+CNN14: python -m ai.scripts.audio.train_hybrid --teacher passt_s_swa --epochs 20
"""
import os, argparse
import torch
import torch.nn as nn
import torch.nn.functional as F
import torchaudio
import numpy as np
from transformers import ASTModel, ASTFeatureExtractor
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

# CNN14 모델 정의 재사용
from ai.scripts.audio.train_cnn14 import CNN14MultiTask, ConvBlock

set_seed(42)

DEFAULT_AST_MODEL = "MIT/ast-finetuned-audioset-10-10-0.4593"


# =============================================================================
# 1. 모델 정의
# =============================================================================

class FusionHead(nn.Module):
    """CNN (1024) + Transformer (768) → Dual Heads"""
    def __init__(self, cnn_dim=1024, transformer_dim=768):
        super().__init__()
        fused_dim = cnn_dim + transformer_dim  # 1792
        self.fc = nn.Sequential(
            nn.Linear(fused_dim, 512),
            nn.ReLU(),
            nn.Dropout(0.3),
        )
        self.type_head = nn.Linear(512, NUM_TYPE_CLASSES)
        self.abnormal_head = nn.Linear(512, 1)

    def forward(self, cnn_feat, transformer_feat):
        fused = torch.cat([cnn_feat, transformer_feat], dim=-1)  # (B, 1792)
        x = self.fc(fused)
        type_logits = self.type_head(x)
        abnormal_logits = self.abnormal_head(x).squeeze(-1)
        return type_logits, abnormal_logits


class HybridModel(nn.Module):
    """CNN14(❄) + Transformer(AST/PaSST) + FusionHead"""
    def __init__(self, teacher="ast"):
        super().__init__()
        self.teacher_type = teacher

        # CNN14 (frozen)
        self.cnn = CNN14MultiTask()
        for p in self.cnn.parameters():
            p.requires_grad = False  # ❄

        # Transformer
        if teacher == "ast":
            self.transformer = ASTModel.from_pretrained(DEFAULT_AST_MODEL)
            self.transformer_dim = 768
        else:
            from hear21passt.models.passt import get_model as get_model_passt
            from hear21passt.models.preprocess import AugmentMelSTFT
            arch = "passt_s_swa_p16_128_ap476" if "swa" in teacher else "passt_s_p16_s16_128_ap468"
            
            # arch별 stride 설정
            fstride, tstride = (16, 16) if "s16" in arch else (10, 10)
            
            # PaSST transformer 직접 로드
            self.transformer = get_model_passt(arch=arch, pretrained=True, fstride=fstride, tstride=tstride)
            self.transformer_dim = getattr(self.transformer, 'embed_dim', 768)
            
            # Mel 전처리기 (32kHz 기준)
            self.passt_mel = AugmentMelSTFT(
                n_mels=128, sr=32000, win_length=800, hopsize=320,
                n_fft=1024, freqm=48, timem=192,
                htk=False, fmin=0.0, fmax=None, norm=1,
                fmin_aug_range=10, fmax_aug_range=2000
            )

        # Fusion Head
        self.fusion = FusionHead(cnn_dim=1024, transformer_dim=self.transformer_dim)

    def load_cnn_weights(self, path):
        """학원에서 학습한 CNN14 Fine-tune 가중치 로딩"""
        if os.path.exists(path):
            self.cnn.load_state_dict(torch.load(path, map_location="cpu", weights_only=False))
            print(f"[Hybrid] CNN14 weights loaded from {path}", flush=True)
        else:
            print(f"⚠️  CNN14 weights not found: {path}. Using pretrained.", flush=True)
            self.cnn.load_pretrained_weights()

    def forward(self, mel_input=None, ast_input=None, raw_audio=None):
        # CNN features (frozen)
        with torch.no_grad():
            cnn_feat = self.cnn.get_features(mel_input)  # (B, 1024)

        # Transformer features
        if self.teacher_type == "ast":
            outputs = self.transformer(ast_input)
            trans_feat = outputs.last_hidden_state[:, 0, :]  # (B, 768)
        else:
            # Resample 16kHz → 32kHz for PaSST
            waveform_32k = torchaudio.functional.resample(raw_audio, orig_freq=16000, new_freq=32000)
            mel = self.passt_mel(waveform_32k)
            mel = mel.unsqueeze(1)
            _, trans_feat = self.transformer(mel)  # features: (B, 768)

        return self.fusion(cnn_feat, trans_feat)


# =============================================================================
# 2. 평가
# =============================================================================

def evaluate_model(model, loader, teacher, desc="Eval"):
    model.eval()
    all_tp, all_tl, all_ap, all_al = [], [], [], []

    with torch.no_grad():
        for batch in loader:
            mel = batch["mel_input"].to(DEVICE)
            kwargs = {"mel_input": mel}
            if teacher == "ast":
                kwargs["ast_input"] = batch["ast_input"].to(DEVICE)
            else:
                kwargs["raw_audio"] = batch["raw_audio"].to(DEVICE)

            t_log, a_log = model(**kwargs)

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
# 3. 학습
# =============================================================================

def train(teacher, epochs=None, batch_size=None, lr=None):
    teacher_short = teacher.replace("passt_s_swa_p16_128_ap476", "passt_s_swa")
    model_name = f"hybrid_{teacher_short}_cnn14"
    print(f"\n🚀 Hybrid [{teacher_short}+CNN14] Training\n", flush=True)

    epochs = epochs or 20
    batch_size = batch_size or (32 if DEVICE.type == "cuda" and torch.cuda.get_device_properties(0).total_memory > 16e9 else COMMON_CONFIG["batch_size"])
    grad_accum = COMMON_CONFIG["grad_accum"]
    fp16 = torch.cuda.is_available()

    # ── Model ──
    model = HybridModel(teacher=teacher).to(DEVICE)

    # Load CNN14 Fine-tuned weights
    cnn_weight_path = os.path.join(SAVE_ROOT, "cnn14_finetune", "best_model.pt")
    model.load_cnn_weights(cnn_weight_path)

    # ── Optimizer (CNN14 frozen, Transformer + Fusion trainable) ──
    # Verify no overlap
    trans_params = set(id(p) for p in model.transformer.parameters())
    fusion_params = set(id(p) for p in model.fusion.parameters())
    assert len(trans_params & fusion_params) == 0, "Parameter overlap detected!"

    optimizer = torch.optim.AdamW([
        {"params": model.transformer.parameters(), "lr": 3e-5},
        {"params": model.fusion.parameters(), "lr": 1e-3},
    ])
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(f"📐 Trainable: {trainable:,} / {total:,} ({trainable/total*100:.1f}%)", flush=True)

    # ── Data ──
    arch_for_loader = "fusion" if teacher == "ast" else "passt"
    fe = ASTFeatureExtractor.from_pretrained(DEFAULT_AST_MODEL) if teacher == "ast" else None
    train_loader, val_loader, test_loader, type_weights = create_dataloaders(arch_for_loader, feature_extractor=fe, batch_size=batch_size)

    criterion_type = nn.CrossEntropyLoss(weight=type_weights, ignore_index=-100)
    criterion_abn = nn.BCEWithLogitsLoss()
    scaler = torch.amp.GradScaler('cuda', enabled=fp16)

    save_dir = os.path.join(SAVE_ROOT, model_name)
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
                mel = batch["mel_input"].to(DEVICE)
                t_lbl = batch["type_label"].to(DEVICE)
                a_lbl = batch["abnormal_label"].to(DEVICE)

                kwargs = {"mel_input": mel}
                if teacher == "ast":
                    kwargs["ast_input"] = batch["ast_input"].to(DEVICE)
                else:
                    kwargs["raw_audio"] = batch["raw_audio"].to(DEVICE)

                t_log, a_log = model(**kwargs)

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
        metrics = evaluate_model(model, val_loader, teacher, f"Epoch {epoch+1}")
        combined_f1 = (metrics["abnormal_f1"] + metrics["type_macro_f1"]) / 2
        print(f"📈 Epoch {epoch+1}/{epochs} | Abn Recall: {metrics['abnormal_recall']:.4f} | Abn F1: {metrics['abnormal_f1']:.4f} | Type F1: {metrics['type_macro_f1']:.4f} | Combined: {combined_f1:.4f}", flush=True)
        scheduler.step()

        if combined_f1 > best_f1:
            best_f1 = combined_f1
            torch.save(model.state_dict(), os.path.join(save_dir, "best_model.pt"))
            print(f"💾 Best @ {best_f1:.4f}", flush=True)

        if early_stop.step(combined_f1, epoch):
            break

    # ── Test ──
    print(f"\n🏁 FINAL TEST — Hybrid [{teacher_short}+CNN14]", flush=True)
    best_path = os.path.join(save_dir, "best_model.pt")
    if os.path.exists(best_path):
        model.load_state_dict(torch.load(best_path, map_location=DEVICE, weights_only=False))
    model = model.to(DEVICE)
    test_metrics = evaluate_model(model, test_loader, teacher, "FINAL TEST")

    model_size = os.path.getsize(best_path) / (1024**2) if os.path.exists(best_path) else 0
    final = {"model": model_name, "mode": "hybrid", **test_metrics, "latency_ms": 0, "model_size_mb": round(model_size, 1)}
    save_metrics(model_name, "hybrid", final)
    print(f"\n✅ Hybrid [{teacher_short}+CNN14] complete!\n", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--teacher", required=True, help="ast, passt_s_p16_s16_128_ap468, or passt_s_swa")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch_size", type=int, default=None)
    args = parser.parse_args()
    train(args.teacher, args.epochs, args.batch_size)
