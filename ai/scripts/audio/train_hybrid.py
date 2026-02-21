# ai/scripts/audio/train_hybrid.py
"""
[파일 용도] Hybrid Fusion (CNN14 + Transformer) 모델 학습

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
    ABNORMAL_THRESHOLD, COMMON_CONFIG, DEVICE, SAVE_ROOT, NUM_TYPE_CLASSES
)
from ai.scripts.audio.data_loader import create_dataloaders
from ai.scripts.audio.advanced_metrics import calculate_fpr_at_recall, calculate_trr, calculate_nrs, calculate_divergence

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
        # [Strict v3.7] Purified Two-Head Structure
        self.fc = nn.Sequential(
            nn.Linear(fused_dim, 512),
            nn.ReLU(),
            nn.Dropout(0.3),
        )
        
        # Head A: Binary (Normal, Abnormal)
        self.binary_head = nn.Linear(512, 2)
        # Head B: Multi-class (Starter, Engine, Brake, Other)
        self.type_head = nn.Linear(512, 4)

    def forward(self, cnn_feat, transformer_feat):
        fused = torch.cat([cnn_feat, transformer_feat], dim=-1)  # (B, 1792)
        x = self.fc(fused)
        
        # [Strict v3.7] Always calculate both heads (No conditional forward)
        logits_bin = self.binary_head(x)
        logits_type = self.type_head(x)
        return logits_type, logits_bin


class HybridModel(nn.Module):
    """CNN14(❄) + Transformer(AST/PaSST) + FusionHead"""
    def __init__(self, teacher="ast"):
        super().__init__()
        self.teacher_type = teacher

        # CNN14 (frozen by default, but partial unfreeze for v3.8)
        self.cnn = CNN14MultiTask()
        for p in self.cnn.parameters():
            p.requires_grad = False  # Freeze all first
            
        # [v3.8] Partial Unfreeze: Last ConvBlock (index 4)
        for p in self.cnn.conv_blocks[4].parameters():
            p.requires_grad = True
        print("🔒 Hybrid Backbone (CNN14) FROZEN (Except last block)", flush=True)

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

    def get_fused_features(self, mel_input=None, ast_input=None, raw_audio=None):
        """지표 계산을 위한 융합 feature (512-dim) 추출"""
        with torch.no_grad():
            cnn_feat = self.cnn.get_features(mel_input)
            
            if self.teacher_type == "ast":
                outputs = self.transformer(ast_input)
                trans_feat = outputs.last_hidden_state[:, 0, :]
            else:
                waveform_32k = torchaudio.functional.resample(raw_audio, orig_freq=16000, new_freq=32000)
                target_len = 32000 * 10
                if waveform_32k.shape[-1] < target_len:
                    waveform_32k = F.pad(waveform_32k, (0, target_len - waveform_32k.shape[-1]))
                elif waveform_32k.shape[-1] > target_len:
                    waveform_32k = waveform_32k[:, :target_len]
                mel = self.passt_mel(waveform_32k)
                mel = mel.unsqueeze(1)
                _, trans_feat = self.transformer(mel)
            
            fused = torch.cat([cnn_feat, trans_feat], dim=-1)
            return self.fusion.fc(fused)




    def load_cnn_weights(self, path):
        """학원에서 학습한 CNN14 Fine-tune 가중치 로딩"""
        if os.path.exists(path):
            state_dict = torch.load(path, map_location="cpu", weights_only=False)
            # [Strict v3.7] Filter out incompatible heads from CNN14 checkpoint
            state_dict = {k: v for k, v in state_dict.items() if not k.startswith("type_head") and not k.startswith("binary_head") and not k.startswith("abnormal_head")}
            self.cnn.load_state_dict(state_dict, strict=False)
            print(f"[Hybrid] CNN14 weights loaded from {path} (strict=False, heads filtered)", flush=True)
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
            # [Revised v3.5] Resample 16kHz -> 32kHz and Pad to 10s (320,000 samples)
            waveform_32k = torchaudio.functional.resample(raw_audio, orig_freq=16000, new_freq=32000)
            target_len = 32000 * 10
            if waveform_32k.shape[-1] < target_len:
                waveform_32k = F.pad(waveform_32k, (0, target_len - waveform_32k.shape[-1]))
            elif waveform_32k.shape[-1] > target_len:
                waveform_32k = waveform_32k[:, :target_len]

            mel = self.passt_mel(waveform_32k)
            mel = mel.unsqueeze(1)
            _, trans_feat = self.transformer(mel)  # features: (B, 768)

        return self.fusion(cnn_feat, trans_feat)


# =============================================================================
# 2. 평가
# =============================================================================

def evaluate_model(model, loader, desc="Eval"):
    model.eval()
    all_tp, all_tl, all_ap, all_al = [], [], [], []

    with torch.no_grad():
        for batch in loader:
            a_lbl = batch["abnormal_label"].to(DEVICE)
            t_lbl = batch["type_label"].to(DEVICE)
            
            kwargs = {
                "mel_input": batch["mel_input"].to(DEVICE),
                "ast_input": batch["ast_input"].to(DEVICE) if model.teacher_type == "ast" else None,
                "raw_audio": batch["raw_audio"].to(DEVICE) if model.teacher_type != "ast" else None
            }
            t_log, b_log = model(**kwargs)

            # [Strict Hierarchical Inference v3.7 - Option A]
            # 1. Abnormal Detection (Binary Head: 2 outputs)
            b_pred = torch.argmax(b_log, dim=1) 
            
            # 2. Type Classification (All 4 classes: Starter, Engine, Brake, Other)
            t_probs = torch.softmax(t_log, dim=1) 
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

    return {
        "abnormal_f1": abn_f1, "abnormal_recall": abn_r, "abnormal_precision": abn_p,
        "type_macro_f1": t_f1, "type_macro_recall": t_r, "type_macro_precision": t_p,
        "type_acc": acc, "type_balanced_acc": balanced_acc,
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
            a_lbl = batch["abnormal_label"].to(DEVICE)
            
            kwargs = {
                "mel_input": batch["mel_input"].to(DEVICE),
                "ast_input": batch["ast_input"].to(DEVICE) if model.teacher_type == "ast" else None,
                "raw_audio": batch["raw_audio"].to(DEVICE) if model.teacher_type != "ast" else None
            }
            t_log, b_log = model(**kwargs)
            probs = torch.softmax(b_log, dim=1)[:, 1] # Abnormal probability
            
            feats = model.get_fused_features(**kwargs)
            
            all_scores.extend(probs.cpu().numpy())
            all_labels.extend(a_lbl.cpu().numpy())
            all_features.append(feats.cpu().numpy())
            
    return np.array(all_labels), np.array(all_scores), np.concatenate(all_features, axis=0)

# =============================================================================
# 3. 학습
# =============================================================================

def train(teacher, epochs=None, batch_size=None, lr=None):
    teacher_short = (
        teacher.replace("passt_s_p16_s16_128_ap468", "passt_n_s")
               .replace("passt_s_swa_p16_128_ap476", "passt_s_swa")
               .replace(DEFAULT_AST_MODEL, "ast")
    )
    model_name = teacher_short
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

    transformer_lr = 3e-5
    head_lr = 1e-3
    optimizer = torch.optim.AdamW([
        {"params": model.transformer.parameters(), "lr": transformer_lr},
        {"params": model.fusion.parameters(), "lr": head_lr},
    ])
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(f"📐 Trainable: {trainable:,} / {total:,} ({trainable/total*100:.1f}%)", flush=True)

    # ── Data ──
    arch_for_loader = "fusion" if teacher == "ast" else "passt"
    fe = ASTFeatureExtractor.from_pretrained(DEFAULT_AST_MODEL) if teacher == "ast" else None
    train_loader, val_loader, val_loader_balanced, test_loader, test_loader_balanced, type_weights = create_dataloaders(arch_for_loader, feature_extractor=fe, batch_size=batch_size)

    criterion_type = nn.CrossEntropyLoss(weight=type_weights, ignore_index=-100)
    criterion_bin = nn.CrossEntropyLoss()
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

                t_log, b_log = model(**kwargs)

                # [Strict v3.7] Loss calculation
                # 1. Binary Loss
                loss_bin = criterion_bin(b_log, a_lbl)
                
                # 2. Type Loss
                abn_mask = (a_lbl == 1)
                if abn_mask.sum() > 0:
                    loss_type = criterion_type(t_log[abn_mask], t_lbl[abn_mask])
                else:
                    loss_type = torch.tensor(0.0).to(DEVICE)
                
                loss = (loss_bin + COMMON_CONFIG["lambda_type"] * loss_type) / grad_accum

            scaler.scale(loss).backward()
            if (i + 1) % grad_accum == 0:
                # [Fix] Gradient Clipping
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), COMMON_CONFIG["max_grad_norm"])
                
                scaler.step(optimizer); scaler.update(); optimizer.zero_grad()
            total_loss += loss.item() * grad_accum
            if (i + 1) % 10 == 0 or (i + 1) == len(train_loader):
                print(f"[{i+1}/{len(train_loader)}]", end=" ", flush=True)

        print(f"\n⏳ Validating...", flush=True)
        metrics, _ = evaluate_model(model, val_loader, f"Epoch {epoch+1} Valid")
        combined_score = (metrics["abnormal_f1"] + metrics["type_macro_f1"] + metrics["type_acc"]) / 3
        print(f"📈 Epoch {epoch+1}/{epochs} | Abn F1: {metrics['abnormal_f1']:.4f} | Type F1: {metrics['type_macro_f1']:.4f} | Type Acc: {metrics['type_acc']:.4f} | Score: {combined_score:.4f}", flush=True)
        scheduler.step()

        if combined_score > best_f1:
            best_f1 = combined_score
            torch.save(model.state_dict(), os.path.join(save_dir, "best_model.pt"))
            print(f"💾 Best @ {best_f1:.4f}", flush=True)

        if early_stop.step(combined_score, epoch):
            break

    # ── Test Evaluation ──
    # ── [V3.1] Dual Evaluation Strategy — Comparative Report ──
    print(f"\n{'='*80}", flush=True)
    print(f"🏁 DUAL TEST EVALUATION — Original vs Balanced Subset", flush=True)
    print(f"{'='*80}", flush=True)

    best_path = os.path.join(save_dir, "best_model.pt")
    if os.path.exists(best_path):
        model.load_state_dict(torch.load(best_path, map_location=DEVICE, weights_only=False), strict=False)
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
    print(f"⚡ Measuring latency...", flush=True)
    dummy_mel = torch.randn(1, 128, 501).to(DEVICE)
    dummy_ast = torch.randn(1, 1024, 128).to(DEVICE) if teacher == "ast" else None
    dummy_raw = torch.randn(1, 16000 * 5).to(DEVICE)

    class LatencyWrapper(torch.nn.Module):
        def __init__(self, m, t, mel, ast, raw):
            super().__init__()
            self.m, self.t, self.mel, self.ast, self.raw = m, t, mel, ast, raw
        def forward(self, x):
            return self.m(mel_input=self.mel, ast_input=self.ast if self.t=="ast" else None, raw_audio=self.raw)

    wrapper = LatencyWrapper(model, teacher, dummy_mel, dummy_ast, dummy_raw)
    latency = measure_latency(wrapper, torch.zeros(1).to(DEVICE), DEVICE)

    model_size = os.path.getsize(best_path) / (1024**2) if os.path.exists(best_path) else 0

    # ── Save Metrics ──
    final = {
        "model": model_name, "mode": "hybrid", 
        **test_metrics, 
        **fpr_metrics,
        "trr": round(trr, 4), "nrs": round(nrs, 4), "divergence": round(div, 4),
        "balanced_type_macro_f1": balanced_metrics["type_macro_f1"],
        "balanced_type_acc": balanced_metrics["type_acc"],
        "latency_ms": round(latency, 1), 
        "model_size_mb": round(model_size, 1)
    }
    save_metrics(model_name, "hybrid", final)
    print(f"\n✅ Hybrid [{teacher_short}+CNN14] complete!\n", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--teacher", required=True, help="ast, passt_s_p16_s16_128_ap468, or passt_s_swa")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch_size", type=int, default=None)
    args = parser.parse_args()
    train(args.teacher, args.epochs, args.batch_size)
