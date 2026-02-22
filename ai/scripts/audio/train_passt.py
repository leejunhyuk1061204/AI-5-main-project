# ai/scripts/audio/train_passt.py
"""
[파일 용도] PaSST (Patchout fASt Spectrogram Transformer) 모델 학습

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
import torch.optim.swa_utils as swa_utils
import torchaudio
import numpy as np
from sklearn.metrics import (
    precision_recall_fscore_support, accuracy_score,
    confusion_matrix, balanced_accuracy_score, classification_report,
    f1_score
)
from peft import LoraConfig, get_peft_model, TaskType
import torch.nn.functional as F

# ──────────── Focal Loss ────────────
class FocalLoss(nn.Module):
    def __init__(self, alpha=None, gamma=2.0, reduction='mean', ignore_index=-100, label_smoothing=0.0):
        super(FocalLoss, self).__init__()
        self.alpha = alpha
        self.gamma = gamma
        self.reduction = reduction
        self.ignore_index = ignore_index
        self.label_smoothing = label_smoothing

    def forward(self, inputs, targets):
        ce_loss = F.cross_entropy(inputs, targets, reduction='none', ignore_index=self.ignore_index, weight=self.alpha, label_smoothing=self.label_smoothing)
        pt = torch.exp(-ce_loss)
        focal_loss = ((1 - pt) ** self.gamma) * ce_loss

        if self.reduction == 'mean':
            return focal_loss.mean()
        elif self.reduction == 'sum':
            return focal_loss.sum()
        else:
            return focal_loss

# ──────────── Mixup ────────────
def mixup_data(x, y_a, y_t, alpha=0.2, device='cuda'):
    '''Returns mixed inputs, pairs of targets, and lambda'''
    if alpha > 0:
        lam = np.random.beta(alpha, alpha)
    else:
        lam = 1

    batch_size = x.size(0)
    index = torch.randperm(batch_size).to(device)

    mixed_x = lam * x + (1 - lam) * x[index, :]
    y_a_a, y_a_b = y_a, y_a[index]
    y_t_a, y_t_b = y_t, y_t[index]
    return mixed_x, y_a_a, y_a_b, y_t_a, y_t_b, lam

from ai.scripts.audio.config import (
    set_seed, save_metrics, measure_latency, EarlyStopping,
    TYPE_LABELS, type2id, ABNORMAL_LABELS, OTHER_THRESHOLD,
    ABNORMAL_THRESHOLD, COMMON_CONFIG, DEVICE, SAVE_ROOT, NUM_TYPE_CLASSES
)
from ai.scripts.audio.data_loader import create_dataloaders
from ai.scripts.audio.advanced_metrics import calculate_fpr_at_recall, calculate_trr, calculate_nrs, calculate_divergence

set_seed(42)


# =============================================================================
# 1. 모델 정의
# =============================================================================

class PaSSTMultiTask(nn.Module):
    """PaSST backbone + Multi-Task Dual Heads"""
    def __init__(self, arch="passt_s_p16_s16_128_ap468", pretrained=True):
        super().__init__()
        from hear21passt.models.passt import get_model as get_model_passt
        from hear21passt.models.preprocess import AugmentMelSTFT
        self.arch = arch

        if "s16" in arch:
            fstride, tstride = 16, 16
        else:
            fstride, tstride = 10, 10

        self.passt_net = get_model_passt(arch=arch, pretrained=pretrained, fstride=fstride, tstride=tstride)
        # [Strict v3.7] Purify Backbone by removing AudioSet head
        self.passt_net.head = nn.Identity()
        
        self.passt_mel = AugmentMelSTFT(
            n_mels=128, sr=32000, win_length=800, hopsize=320,
            n_fft=1024, freqm=30, timem=50, # [v4.5] Stronger SpecAugment
            htk=False, fmin=0.0, fmax=None, norm=1,
            fmin_aug_range=10, fmax_aug_range=2000
        )
        feat_dim = getattr(self.passt_net, 'embed_dim', 768)
        
        # [Strict v3.7] Head A: Binary (Normal vs Abnormal)
        self.binary_head = nn.Linear(feat_dim, 2)
        # [Strict v3.7] Head B: Multi-class (Starter, Engine, Brake, Other)
        self.type_head = nn.Linear(feat_dim, 4)

    def freeze_backbone(self):
        # Freeze all backbone first
        for p in self.passt_net.parameters():
            p.requires_grad = False
            
        # [v4.8] Strict Baseline: Fully Frozen (No partial unfreeze)
        # if hasattr(self.passt_net, 'blocks'):
        #     for p in self.passt_net.blocks[-1].parameters():
        #         p.requires_grad = True
        
        # if hasattr(self.passt_net, 'norm'):
        #     for p in self.passt_net.norm.parameters():
        #         p.requires_grad = True
                
        print("🔒 Backbone (PaSST) FULLY FROZEN (Strict Baseline)", flush=True)

    def unfreeze_backbone(self, mode="finetune"):
        """[v4.0] LoRA-based Fine-tuning - Uses peft to wrap backbone"""
        if mode == "finetune":
            print(f"🧬 [PEFT/LoRA] Applying LoRA to {self.arch} backbone (Lightweight r=4)...", flush=True)
            # PaSST (hear21passt) follows ViT/DeiT structure. 
            # target_modules should match the internal names (query, key, value)
            config = LoraConfig(
                r=4,               # [v4.8] Lightweight LoRA
                lora_alpha=8,      # [v4.8] Stable alpha
                target_modules=["qkv"], # [Fix] PaSST uses combined qkv layer
                lora_dropout=0.05,
                bias="none",
                task_type=None, 
                use_rslora=True 
            )
            self.passt_net = get_peft_model(self.passt_net, config)
            self.passt_net.print_trainable_parameters()
        else:
            for p in self.passt_net.parameters():
                p.requires_grad = True
            print("🔓 Backbone (PaSST) UNFROZEN (Manual)", flush=True)

    def forward(self, waveform):
        waveform_32k = torchaudio.functional.resample(waveform, orig_freq=16000, new_freq=32000)
        target_len = 32000 * 5  # [v4.0] 5 seconds
        if waveform_32k.shape[-1] < target_len:
            waveform_32k = torch.nn.functional.pad(waveform_32k, (0, target_len - waveform_32k.shape[-1]))
        elif waveform_32k.shape[-1] > target_len:
            waveform_32k = waveform_32k[:, :target_len]
            
        mel = self.passt_mel(waveform_32k)
        mel = mel.unsqueeze(1)
        
        # features = self.passt_net(mel) returns (logits, features) 
        # Since head is Identity, features == logits
        _, features = self.passt_net(mel)
        
        # [Strict v3.7] Always calculate both heads (No conditional forward)
        logits_bin = self.binary_head(features)
        logits_type = self.type_head(features)
        return logits_type, logits_bin

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
            t_lbl = batch["type_label"].to(DEVICE)
            a_lbl = batch["abnormal_label"].to(DEVICE)
            t_log, b_log = model(raw)

            # [Strict Hierarchical Inference v3.7 - Option A]
            # 1. Abnormal Detection (Binary Head: 2 outputs)
            b_pred = torch.argmax(b_log, dim=1) 
            
            # 2. Type Classification (Type Head: 4 outputs, indices 0,1,2 are trained)
            # Only consider index 0,1,2 for confidence check
            t_probs = torch.softmax(t_log[:, :3], dim=1) 
            max_p, t_preds = torch.max(t_probs, dim=1) 
            
            # Initialize as Normal (0)
            final_preds = torch.zeros_like(b_pred)
            
            # Mask for Abnormal predictions
            is_abn_pred = (b_pred == 1)
            # 'Other' is strictly inference-time logic based on low confidence
            is_other = is_abn_pred & (max_p < OTHER_THRESHOLD)
            is_typed = is_abn_pred & (~is_other)
            
            final_preds[is_other] = 4 # Other (Global ID)
            final_preds[is_typed] = t_preds[is_typed] + 1 # 1:Starter, 2:Engine, 3:Brake
            
            # GT Mapping for 5-class CM
            gt_5class = torch.zeros_like(a_lbl)
            is_abn_gt = (a_lbl == 1)
            gt_5class[is_abn_gt] = t_lbl[is_abn_gt] + 1 # 1, 2, 3
            
            all_tp.extend(final_preds.cpu().numpy())
            all_tl.extend(gt_5class.cpu().numpy())
            all_ap.extend(b_pred.cpu().numpy())
            all_al.extend(a_lbl.cpu().numpy())

    all_al_np, all_ap_np = np.array(all_al), np.array(all_ap)
    abn_p, abn_r, abn_f1, _ = precision_recall_fscore_support(all_al_np, all_ap_np, average='binary', zero_division=0)

    # [Method A] Integrated 5-Class Evaluation
    all_tl_np, all_tp_np = np.array(all_tl), np.array(all_tp)
    
    if len(all_tl_np) > 0:
        # Balanced Accuracy should only consider defined classes (exclude other from BAcc calculation if needed, 
        # but here we include it as a valid output state)
        # Note: BAcc on 5 classes where 'other' GT is 0 is tricky. 
        # We use a custom valid mask to exclude 'other' from ground truth but keep in predictions.
        # But wait, there is no GT other, so it's fine.
        balanced_acc = balanced_accuracy_score(all_tl_np, all_tp_np)
        acc = accuracy_score(all_tl_np, all_tp_np)
        t_p, t_r, t_f1, _ = precision_recall_fscore_support(all_tl_np, all_tp_np, labels=[0, 1, 2, 3, 4], average='macro', zero_division=0)
    else:
        acc = balanced_acc = t_p = t_r = t_f1 = 0.0

    # ── Step 3: Uncertain (LLM Fallback) Rate ──
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
        starter_f1 = report["starter"]["f1-score"]
        engine_f1 = report["engine"]["f1-score"]
        brake_f1 = report["brake"]["f1-score"]

        # [Add] Confusion Matrix Analysis (5x5)
        cm = confusion_matrix(all_tl_np, all_tp_np, labels=[0, 1, 2, 3, 4])
        print(f"   [Confusion Matrix (5-class Hierarchical)]")
        print(f"   {'':>10} " + " ".join([f"{l:>8}" for l in DISP]))
        for i in range(len(DISP)):
            print(f"   {DISP[i]:>10} | " + " ".join([f"{v:>8}" for v in cm[i]]))
    else:
        starter_f1 = engine_f1 = brake_f1 = 0.0

    print(f"{'='*60}\n", flush=True)

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
            raw = batch["raw_audio"].to(DEVICE)
            a_lbl = batch["abnormal_label"].to(DEVICE)
            
            t_log, b_log = model(raw)
            probs = torch.softmax(b_log, dim=1)[:, 1] # Abnormal probability
            
            feats = model.get_features(raw)
            
            all_scores.extend(probs.cpu().numpy())
            all_labels.extend(a_lbl.cpu().numpy())
            all_features.append(feats.cpu().numpy())
            
    return np.array(all_labels), np.array(all_scores), np.concatenate(all_features, axis=0)


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
        lr = lr or COMMON_CONFIG["lr_lora_head"]

    batch_size = batch_size or (32 if DEVICE.type == "cuda" and torch.cuda.get_device_properties(0).total_memory > 16e9 else COMMON_CONFIG["batch_size"])
    grad_accum = COMMON_CONFIG["grad_accum"]
    fp16 = torch.cuda.is_available()
    # ── Model ──
    model = PaSSTMultiTask(arch=arch).to(DEVICE)

    if mode == "baseline":
        print("🔒 Backbone FROZEN (Except last block) — heads only", flush=True)
        # Apply partial unfreeze
        model.freeze_backbone()
        
        # Ensure heads are trainable
        for p in model.binary_head.parameters(): p.requires_grad = True
        for p in model.type_head.parameters(): p.requires_grad = True
    else:
        # Fine-tune Mode: Load Baseline Best Weights first (Warm-up)
        baseline_path = os.path.join(SAVE_ROOT, f"{arch_short}_baseline", "best_model.pt")
        if os.path.exists(baseline_path):
            print(f"🔥 Fine-tune: Loading Baseline weights from {baseline_path} (including Trained Heads!)", flush=True)
            state_dict = torch.load(baseline_path, map_location=DEVICE, weights_only=False)
            # [Fix v4.6.3] Do NOT filter heads! We want to keep the trained heads from baseline.
            # state_dict = {k: v for k, v in state_dict.items() if not k.startswith("type_head") ...} <--- REMOVED
            model.load_state_dict(state_dict, strict=False)
        else:
            print("⚠️  Baseline weights not found. Fine-tuning from pretrained.", flush=True)

        print("🔓 ALL parameters UNFROZEN — full fine-tune with differential LR", flush=True)
        for p in model.parameters():
            p.requires_grad = True
        # LayerNorm + pos_embed 열기 (domain shift 적응)
        for name, p in model.passt_net.named_parameters():
            if "norm" in name.lower() or "pos_embed" in name.lower():
                p.requires_grad = True

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(f"📐 Trainable: {trainable:,} / {total:,} ({trainable/total*100:.1f}%)", flush=True)

    # PaSST uses raw_audio → mel internally, so arch="passt" for data_loader
    train_loader, val_loader, val_loader_balanced, test_loader, test_loader_balanced, type_weights = create_dataloaders("passt", batch_size=batch_size)
    # ── Optimizer ──
    use_swa = False # Default initialization
    use_swa = False # Default initialization
    if mode == "baseline":
        print(f"🔒 Baseline Optimization: Fixed LR={lr}, Weight Decay=0.1, No Scheduler", flush=True)
        optimizer = torch.optim.AdamW(filter(lambda p: p.requires_grad, model.parameters()), lr=lr, weight_decay=0.1)
        scheduler = None # [v4.8] No scheduler for baseline (Pure fixed LR)
    else:
        # Differential LR for PaSST (Suggested: Backbone 1.5e-5, Head 1e-4)
        backbone_lr = COMMON_CONFIG["lr_lora_backbone"]
        head_lr = COMMON_CONFIG["lr_lora_head"]
        
        print(f"🔓 LoRA Fine-tune: Backbone (LoRA) LR={backbone_lr:.1e}, Head LR={head_lr:.1e}", flush=True)
        # Apply LoRA before creating optimizer
        model.unfreeze_backbone(mode="finetune")
        
        optimizer = torch.optim.AdamW([
            {"params": model.passt_net.parameters(), "lr": backbone_lr},
            {"params": model.type_head.parameters(), "lr": head_lr},
            {"params": model.binary_head.parameters(), "lr": head_lr},
        ])
        
        # ── Cosine Scheduler with Linear Warmup ──
        total_steps = epochs * len(train_loader)
        warmup_ratio = COMMON_CONFIG.get("warmup_ratio", 0.1)
        warmup_steps = int(total_steps * warmup_ratio)
        
        def lr_lambda(current_step):
            if current_step < warmup_steps:
                return float(current_step) / float(max(1, warmup_steps))
            progress = float(current_step - warmup_steps) / float(max(1, total_steps - warmup_steps))
            return 0.5 * (1.0 + np.cos(np.pi * progress))
            
        scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda=lr_lambda)
        # ── SWA (Stochastic Weight Averaging) Setup ──
        # [v4.5] SWA starts earlier (at 60%) to catch up in short epochs
        use_swa = COMMON_CONFIG.get("use_swa", True) and mode == "finetune"
        if use_swa:
            swa_model = swa_utils.AveragedModel(model)
            swa_start = int(epochs * 0.6) # Start SWA at 60% (e.g., epoch 4 of 6)
            swa_scheduler = swa_utils.SWALR(optimizer, swa_lr=head_lr * 0.35)
            print(f"🌊 SWA Enabled: Starts at epoch {swa_start+1}", flush=True)
        else:
            swa_model = None
            
        print(f"📈 Scheduler: Cosine with {warmup_steps} warmup steps ({warmup_ratio*100:.1f}%)", flush=True)

    # Loss Functions
    label_smoothing = COMMON_CONFIG.get("label_smoothing", 0.0)
    
    if COMMON_CONFIG.get("use_focal_loss", False):
        print(f"🔥 Using Focal Low (gamma={COMMON_CONFIG.get('focal_gamma', 2.0)}, ls={label_smoothing})", flush=True)
        criterion_type = FocalLoss(alpha=type_weights[:3], gamma=COMMON_CONFIG.get("focal_gamma", 2.0), 
                                  ignore_index=-100, label_smoothing=label_smoothing)
    else:
        criterion_type = nn.CrossEntropyLoss(weight=type_weights[:3], ignore_index=-100, label_smoothing=label_smoothing)
        
    # [v4.6.2] Binary Loss Weighting (Normal 1.2, Abnormal 0.8)
    bin_weights = torch.tensor([1.2, 0.8]).to(DEVICE)
    criterion_bin = nn.CrossEntropyLoss(weight=bin_weights, label_smoothing=label_smoothing)
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
                a_lbl = batch["abnormal_label"].to(DEVICE)
                t_lbl = batch["type_label"].to(DEVICE)
                # [Strict v3.7] Loss calculation
                if COMMON_CONFIG.get("use_mixup", False) and mode != "baseline": # Mixup only for Fine-tuning
                    # Mixup Applied
                    raw, a_lbl_a, a_lbl_b, t_lbl_a, t_lbl_b, lam = mixup_data(
                        raw, a_lbl, t_lbl, 
                        alpha=COMMON_CONFIG.get("mixup_alpha", 0.45), 
                        device=DEVICE
                    )
                    t_log, b_log = model(raw)
                    
                    # 1. Binary Loss
                    loss_bin = lam * criterion_bin(b_log, a_lbl_a) + (1 - lam) * criterion_bin(b_log, a_lbl_b)
                    
                    # 2. Type Loss: Apply mask even after mixup
                    abn_mask_a = (a_lbl_a == 1)
                    abn_mask_b = (a_lbl_b == 1)
                    
                    loss_type = torch.tensor(0.0).to(DEVICE) # Initialize
                    if abn_mask_a.sum() > 0:
                        loss_type += lam * criterion_type(t_log[abn_mask_a][:, :3], t_lbl_a[abn_mask_a])
                    if abn_mask_b.sum() > 0:
                        loss_type += (1 - lam) * criterion_type(t_log[abn_mask_b][:, :3], t_lbl_b[abn_mask_b])
                    
                    loss = loss_bin + COMMON_CONFIG["lambda_type"] * loss_type
                else:
                    # Standard Training
                    t_log, b_log = model(raw)
                    
                    # 1. Binary Loss (All samples)
                    loss_bin = criterion_bin(b_log, a_lbl)
                    
                    # 2. Type Loss (Abnormal samples only, Target indices 0, 1, 2)
                    abn_mask = (a_lbl == 1)
                    if abn_mask.sum() > 0:
                        # Slice logits to only train the 3 known types
                        loss_type = criterion_type(t_log[abn_mask][:, :3], t_lbl[abn_mask])
                    else:
                        loss_type = torch.tensor(0.0).to(DEVICE)
                    
                    loss = loss_bin + COMMON_CONFIG["lambda_type"] * loss_type

            if not torch.isnan(loss):
                scaler.scale(loss / grad_accum).backward()
            if (i + 1) % grad_accum == 0:
                # [Fix] Gradient Clipping
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), COMMON_CONFIG["max_grad_norm"])
                
                scaler.step(optimizer); scaler.update(); optimizer.zero_grad()
                
                if mode != "baseline": # Step scheduler per batch
                    if use_swa and epoch >= swa_start:
                        swa_model.update_parameters(model)
                        swa_scheduler.step()
                    else:
                        scheduler.step()
            total_loss += loss.item() * grad_accum
            if (i + 1) % 10 == 0 or (i + 1) == len(train_loader):
                print(f"[{i+1}/{len(train_loader)}]", end=" ", flush=True)

        print(f"\n⏳ Validating...", flush=True)
        metrics, _ = evaluate_model(model, val_loader, f"Epoch {epoch+1} Valid")
        combined_score = (metrics["abnormal_f1"] + metrics["type_macro_f1"] + metrics["type_acc"]) / 3
        print(f"📈 Epoch {epoch+1}/{epochs} | Abn F1: {metrics['abnormal_f1']:.4f} | Type F1: {metrics['type_macro_f1']:.4f} | Type Acc: {metrics['type_acc']:.4f} | Score: {combined_score:.4f}", flush=True)

        # [Fix] No epoch-level scheduler step needed for LambdaLR or Fixed Baseline
        # if mode == "baseline": scheduler.step(combined_score)

        if combined_score > best_f1:
            best_f1 = combined_score
            torch.save(model.state_dict(), os.path.join(save_dir, "best_model.pt"))
            print(f"💾 Best @ {best_f1:.4f}", flush=True)

        if early_stop.step(combined_score, epoch):
            break

    # ── [V3.1] Dual Evaluation Strategy — Comparative Report ──
    print(f"\n{'='*80}", flush=True)
    print(f"🏁 DUAL TEST EVALUATION — Original vs Balanced Subset", flush=True)
    print(f"{'='*80}", flush=True)

    best_path = os.path.join(save_dir, "best_model.pt")
    if os.path.exists(best_path):
        model.load_state_dict(torch.load(best_path, map_location=DEVICE, weights_only=False))
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
    dummy = torch.randn(1, 16000 * 5).to(DEVICE)
    latency = measure_latency(model, dummy, DEVICE)

    # ── Model Size ──
    model_size_mb = os.path.getsize(best_path) / (1024 * 1024) if os.path.exists(best_path) else 0

    # ── SWA Finalization ──
    if use_swa:
        print(f"\n🌊 SWA Finalizing: Updating BN statistics...", flush=True)
        swa_utils.update_bn(train_loader, swa_model)
        swa_path = os.path.join(save_dir, "best_model_swa.pt") # Save as best_model_swa.pt
        torch.save(swa_model.module.state_dict(), swa_path)
        print(f"💾 SWA Model Saved: {swa_path}", flush=True)

    # ── Save Metrics ──
    # ── Save Metrics ──
    # [v4.7] Reflect SWA usage in model name regardless of backbone
    if "swa" in arch:
        base_name = "passt_s_swa" # Distinct name for SWA
    elif "s16" in arch:
        base_name = "passt_s" # User requested PaSST-S
    else:
        base_name = "passt"
        
    model_name = f"{base_name}_swa" if use_swa and "swa" not in base_name else base_name
    
    final_metrics = {
        "model": model_name, "mode": mode, 
        **test_metrics, 
        **fpr_metrics,
        "trr": round(trr, 4), "nrs": round(nrs, 4), "divergence": round(div, 4),
        "balanced_type_macro_f1": balanced_metrics["type_macro_f1"],
        "balanced_type_acc": balanced_metrics["type_acc"],
        "latency_ms": round(latency, 1), 
        "model_size_mb": round(model_size_mb, 1)
    }
    save_metrics(base_name, mode, final_metrics)
    print(f"\n✅ PaSST {mode.upper()} training complete! (Model: {model_name})\n", flush=True)
    return final_metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--arch", default="passt_s_p16_s16_128_ap468", help="passt_s_p16_s16_128_ap468 or passt_s_swa_p16_128_ap476")
    parser.add_argument("--mode", choices=["baseline", "finetune"], required=True)
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--batch_size", type=int, default=None)
    parser.add_argument("--lr", type=float, default=None)
    args = parser.parse_args()
    train(args.arch, args.mode, args.epochs, args.batch_size, args.lr)
