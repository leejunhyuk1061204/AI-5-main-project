# ai/scripts/audio/train_yamnet.py
"""
🚀 YAMNet-style CNN (MobileNetV1-based) + Attention Pooling 기반 차량 결함 진단 학습 스크립트

[Core Strategy]
1. YAMNet-style CNN: MobileNetV1 아키텍처를 직접 구현 (Scratched-trained).
   - NOTE: AudioSet 가중치(Pre-trained) 없이 데이터셋에 맞춰 처음부터 학습을 진행합니다.
2. Attention Pooling: 프레임별 임베딩의 기여도를 학습하여 대표 벡터 생성 (Temporal Dependency 확보)
3. 3-Phase Progressive Training:
   - Phase 0: Data Sanity Check (Binary Recall check on frozen backbone)
   - Phase 1: Safety-First (Abnormal Detection, Recall > 0.85 focus)
   - Phase 2: Diagnostic Precision (Type Classification focus)
   - Phase 3: Final Refinement (Attention Pooling & Joint Fine-tuning)
4. Cost-sensitive Loss: 결함 탐지 시 False Negative 비용을 고려해 Abnormal Loss 가중치 부여 (1.5x)

[Expected Performance Milestones]
| 단계 | 핵심 목표 | 주요 지표 | 비고 |
| :--- | :--- | :--- | :--- |
| **Phase 0/1** | 결함 탐지 (Sanity/Recall) | **Abnormal Recall > 0.85** | 결함 누락 방지 최우선 |
| **Phase 2** | 진단 정밀도 (Diagnostic) | **Recall @ Prec ≥ 0.5** | 오진 리스크 하의 최대 검출 |
| **Phase 3** | 신뢰할 수 있는 거절 (OOD) | **Rejection Rate (Proper)** | "모호하면 거절"로 신뢰도 확보 |
| **Common** | 추론 및 효율성 | **~15ms / 14.5MB** | MobileNetV1 최적화 |

[Execution Commands]
- Phase 0/1: python ai/scripts/audio/train_yamnet.py --mode baseline --epochs 2
- Phase 2/3: python ai/scripts/audio/train_yamnet.py --mode finetune --epochs 10
"""

import argparse
import os
import sys
import time
from pathlib import Path
from collections import Counter

project_root = str(Path(__file__).parents[3])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
import librosa
from sklearn.metrics import classification_report, confusion_matrix, f1_score, recall_score, precision_score, accuracy_score

from ai.scripts.audio.config import (
    TRAIN_DATA_DIR, TEST_DATA_DIR, TYPE_LABELS, type2id, id2type,
    COMMON_CONFIG, DEVICE, IS_RUNPOD, set_seed, EarlyStopping, save_metrics,
    measure_latency # Added for benchmarking
)
from ai.scripts.audio.data_loader import create_dataloaders
from ai.scripts.audio.advanced_metrics import calculate_fpr_at_recall, calculate_trr, calculate_nrs, calculate_divergence

# =============================================================================
# 1. 모델 정의 (YAMNet Backbone + Attention Pooling)
# =============================================================================

class AttentionPooling(nn.Module):
    """
    Frame-level embedding 중 결함 관련 신호의 기여도를 학습적으로 가중합.
    [Method A] Backbone Output의 Temporal Dimension(T')에 대해 Attention을 적용.
    (B, C, T') -> (B, C)
    """
    def __init__(self, input_dim):
        super().__init__()
        self.query = nn.Linear(input_dim, 1)
        self.temperature = nn.Parameter(torch.tensor(1.0))
        # [Stabilization] Freeze temperature to preventing early collapse (User feedback)
        self.temperature.requires_grad = False 

    def forward(self, x, return_weights=False):
        # x shape: (batch_size, time_steps, input_dim)
        # Numerical stability: Squeeze -> Softmax -> Unsqueeze
        temp = torch.clamp(self.temperature, min=0.3) 
        scores = self.query(x).squeeze(-1)
        attn_weights = F.softmax(scores / temp, dim=1).unsqueeze(-1)
        # pooled: (batch_size, input_dim)
        pooled = torch.sum(x * attn_weights, dim=1)
        
        if return_weights:
            return pooled, attn_weights
        return pooled

# ── torch_audioset compatible architecture (for direct weight loading) ──

class Conv2d_tf(nn.Conv2d):
    """Conv2d with TF-style SAME padding (from torch_audioset)"""
    def __init__(self, *args, **kwargs):
        kwargs.pop("padding", None)
        super().__init__(*args, **kwargs)

    def forward(self, x):
        # SAME padding implementation
        ih, iw = x.size()[-2:]
        kh, kw = self.kernel_size
        sh, sw = self.stride
        oh = (ih + sh - 1) // sh
        ow = (iw + sw - 1) // sw
        pad_h = max((oh - 1) * sh + kh - ih, 0)
        pad_w = max((ow - 1) * sw + kw - iw, 0)
        if pad_h > 0 or pad_w > 0:
            x = F.pad(x, [pad_w // 2, pad_w - pad_w // 2,
                          pad_h // 2, pad_h - pad_h // 2])
        return F.conv2d(x, self.weight, self.bias, self.stride,
                        padding=0, dilation=self.dilation, groups=self.groups)


class CONV_BN_RELU(nn.Module):
    """Matches torch_audioset's CONV_BN_RELU exactly"""
    def __init__(self, conv):
        super().__init__()
        self.conv = conv
        self.bn = nn.BatchNorm2d(conv.out_channels, eps=1e-4)  # YAMNet uses eps=1e-4
        self.relu = nn.ReLU()

    def forward(self, x):
        return self.relu(self.bn(self.conv(x)))


class Conv(nn.Module):
    """First conv block - matches torch_audioset's Conv"""
    def __init__(self, kernel, stride, input_dim, output_dim):
        super().__init__()
        self.fused = CONV_BN_RELU(
            Conv2d_tf(input_dim, output_dim, kernel_size=kernel, stride=stride, bias=False)
        )

    def forward(self, x):
        return self.fused(x)


class SeparableConv(nn.Module):
    """Matches torch_audioset's SeparableConv exactly (2 BN+ReLU blocks)"""
    def __init__(self, kernel, stride, input_dim, output_dim):
        super().__init__()
        self.depthwise_conv = CONV_BN_RELU(
            Conv2d_tf(input_dim, input_dim, kernel_size=kernel, stride=stride,
                      groups=input_dim, bias=False)
        )
        self.pointwise_conv = CONV_BN_RELU(
            Conv2d_tf(input_dim, output_dim, kernel_size=1, stride=1, bias=False)
        )

    def forward(self, x):
        return self.pointwise_conv(self.depthwise_conv(x))


class YAMNetStyleBackbone(nn.Module):
    """
    Exact replica of torch_audioset's YAMNet (without final classifier).
    Uses add_module('layerX', ...) naming so load_state_dict works directly.
    """
    def __init__(self):
        super().__init__()
        net_configs = [
            # (layer_function, kernel, stride, num_filters)
            (Conv,          [3, 3], 2,   32),
            (SeparableConv, [3, 3], 1,   64),
            (SeparableConv, [3, 3], 2,  128),
            (SeparableConv, [3, 3], 1,  128),
            (SeparableConv, [3, 3], 2,  256),
            (SeparableConv, [3, 3], 1,  256),
            (SeparableConv, [3, 3], 2,  512),
            (SeparableConv, [3, 3], 1,  512),
            (SeparableConv, [3, 3], 1,  512),
            (SeparableConv, [3, 3], 1,  512),
            (SeparableConv, [3, 3], 1,  512),
            (SeparableConv, [3, 3], 1,  512),
            (SeparableConv, [3, 3], 2, 1024),
            (SeparableConv, [3, 3], 1, 1024),
        ]

        self.layer_names = []
        input_dim = 1
        for i, (layer_mod, kernel, stride, output_dim) in enumerate(net_configs):
            name = 'layer{}'.format(i + 1)
            self.add_module(name, layer_mod(kernel, stride, input_dim, output_dim))
            input_dim = output_dim
            self.layer_names.append(name)
        
        # [Method A] No classifier, no avg_pool — return (B, 1024, F', T')

    def forward(self, x):
        for name in self.layer_names:
            x = getattr(self, name)(x)
        return x  # Keep spatial/temporal dims

class YAMNetStyleClassifier(nn.Module):
    def __init__(self, num_classes=3):
        super().__init__()
        self.backbone = YAMNetStyleBackbone()
        self.embedding_dim = 1024
        self.attention_pool = AttentionPooling(self.embedding_dim)
        
        # [Phase 3 Upgrade] Patch-level Attention for Type Classification
        # Aggregates N patches (Time-Distributed) into 1 Clip-level embedding
        self.patch_attention = AttentionPooling(self.embedding_dim)
        
        # Multi-task Heads
        self.type_head = nn.Sequential(
            nn.Linear(self.embedding_dim, 256),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(256, num_classes)
        )
        self.abnormal_head = nn.Linear(self.embedding_dim, 1)

    def get_features(self, x):
        """지표 계산을 위한 feature 추출"""
        if x.dim() == 3: x = x.unsqueeze(1)
        B, C, F_dim, T_dim = x.shape
        patches = x.unfold(3, 96, 48) # (B, C, F, N_patches, 96)
        patches = patches.permute(0, 3, 1, 2, 4) # (B, N_patches, C, F, 96)
        N_patches = patches.shape[1]
        patches = patches.contiguous().view(-1, 1, F_dim, 96)
        
        feat = self.backbone(patches)
        feat = feat.mean(dim=2) # Freq Average
        feat = feat.permute(0, 2, 1) # (B*N, T', 1024)
        pooled_patches = self.attention_pool(feat)
        pooled_patches = pooled_patches.view(B, N_patches, -1)
        
        clip_embedding = self.patch_attention(pooled_patches)
        return clip_embedding # (B, 1024)

    def forward(self, x, return_attn=False):
        # x shape: (B, 1, F, T) -> e.g. (32, 1, 64, 501)
        
        # [Auto-fix] DataLoader returns (B, F, T) -> add channel dim
        if x.dim() == 3:
            x = x.unsqueeze(1)
        
        if x.dim() == 4:
            B, C, F_dim, T_dim = x.shape
            
            # [Sanity Check] Mel bins must match YAMNet (64)
            if F_dim != 64:
                raise ValueError(f"YAMNet expects 64 mel bins, got {F_dim}. Check data_loader arch='yamnet'.")

            # Simple manual unfold
            # Window size = 96 (0.96s for 16kHz, hop 10ms), Stride = 48 (50% overlap)
            patches = x.unfold(3, 96, 48) # (B, C, F, N_patches, 96)
            patches = patches.permute(0, 3, 1, 2, 4) # (B, N_patches, C, F, 96)
            N_patches = patches.shape[1]
            patches = patches.contiguous().view(-1, 1, F_dim, 96) # (B*N, 1, F, 96)
            
            # [Stage 1] Backbone Feature Extraction
            feat = self.backbone(patches) # (B*N, 1024, F', T')
            
            # [Stage 2] Time-level Attention (within Patch)
            feat = feat.mean(dim=2) # Freq Average -> (B*N, 1024, T')
            feat = feat.permute(0, 2, 1) # (B*N, T', 1024)
            
            pooled_patches, time_attn = self.attention_pool(feat, return_weights=True) 
            # pooled_patches: (B*N, 1024), time_attn: (B*N, T', 1)
            
            # [Stage 3] Patch-level Aggregation
            # Reshape to (B, N, 1024)
            pooled_patches = pooled_patches.view(B, N_patches, -1)
            
            # 3-1. Abnormal Head: Max Pooling (MIL) - Detecting any local defect
            # If any patch is abnormal -> Global Abnormal
            abn_logits_patch = self.abnormal_head(pooled_patches).squeeze(-1) # (B, N)
            abn_logits = abn_logits_patch.max(dim=1).values # (B)
            
            # 3-2. Type Head: Attention Pooling (Phase 3 Upgrade) - Focusing on relevant patches
            # Aggregates defective patches to determine defect type
            clip_embedding, patch_attn = self.patch_attention(pooled_patches, return_weights=True)
            # clip_embedding: (B, 1024), patch_attn: (B, N, 1)
            
            type_logits = self.type_head(clip_embedding) # (B, Classes)
            
            if return_attn:
                # time_attn: (B*N, T', 1) -> (B, N, T')
                time_attn = time_attn.squeeze(-1).view(B, N_patches, -1)
                patch_attn = patch_attn.squeeze(-1) # (B, N)
                
                # Compute entropy of patch attention weights for uncertainty estimation
                # Add a small epsilon for numerical stability before log
                entropy = -torch.sum(patch_attn * torch.log(patch_attn + 1e-9), dim=1)
                return type_logits, abn_logits, time_attn, patch_attn, entropy
            
            return type_logits, abn_logits
        else:
            raise ValueError(f"Unexpected input shape: {x.shape}. Expected 4D (B, 1, F, T).")

# ... 

def train(mode, epochs=None, batch_size=None):
    set_seed(42)
    # [Fix] Default values for benchmark integration
    epochs = epochs if epochs is not None else 30
    batch_size = batch_size if batch_size is not None else 16
    arch = "yamnet"
    
    print(f"🚀 YAMNet Training - Architecture: {arch}, Mode: {mode}")

    # 1. 데이터 로더 준비
    # data_loader.py의 create_dataloaders 활용 (arch='yamnet'에 맞춤 대응 필요)
    # [Fix] create_dataloaders returns 6 values:
    # (train_loader, val_loader, val_loader_balanced, test_loader, test_loader_balanced, weights)
    train_loader, val_loader, _, test_loader, _, class_weights = create_dataloaders(
        arch="yamnet", 
        batch_size=batch_size or COMMON_CONFIG["batch_size"],
        samples_per_class=COMMON_CONFIG["samples_per_class"]
    )

    # [Data & Weights Path]
    weight_dir = "./ai/weights/audio"
    os.makedirs(weight_dir, exist_ok=True)
    pretrained_path = os.path.join(weight_dir, "yamnet.pth")
    
    # 2. 모델 초기화
    model = YAMNetStyleClassifier(num_classes=len(TYPE_LABELS)).to(DEVICE)
    
    # ═══════════════════════════════════════════════════════════════════
    # [Training Strategy]
    # Baseline: Random Init → 전체 레이어 학습 (Pretrained 없이)
    # Finetune: AudioSet Pretrained → 전체 레이어 학습
    # 비교 의미: "AudioSet Pretrained가 얼마나 도움되는가?"
    # ═══════════════════════════════════════════════════════════════════
    
    if mode == "baseline":
        print("\n🥇 Baseline: Random Init + Full Training (No Pretrained Weights)")
        print("   → 비교 기준: Pretrained 없이 처음부터 학습한 성능")
        
        # 모든 레이어 학습 가능 (기본값 = requires_grad=True)
        optimizer = torch.optim.AdamW([
            {'params': model.backbone.parameters(), 'lr': 1e-4},       # Backbone: 안정적 학습
            {'params': model.attention_pool.parameters(), 'lr': 1e-3}, # Attention: 빠른 학습
            {'params': model.type_head.parameters(), 'lr': 1e-3},      # Head: 빠른 학습
            {'params': model.abnormal_head.parameters(), 'lr': 1e-3},  # Head: 빠른 학습
        ], weight_decay=1e-2)
        
    elif mode == "finetune":
        print("\n🥈 Finetune: AudioSet Pretrained + Full Training")
        print("   → AudioSet 521 클래스 사전학습 활용 (Vehicle, Engine 등 포함)")
        
        # [Pretrained Weight Loading]
        if not os.path.exists(pretrained_path):
            print(f"📥 Downloading YAMNet pretrained weights to {pretrained_path}...")
            url = "https://github.com/w-hc/torch_audioset/releases/download/v0.1/yamnet.pth"
            try:
                torch.hub.download_url_to_file(url, pretrained_path)
                print("✅ Download Complete.")
            except Exception as e:
                print(f"❌ Download Failed: {e}")
                print("⚠️ Proceeding with Random Initialization.")
        
        if os.path.exists(pretrained_path):
            print(f"📦 Loading AudioSet Pretrained Weights from {pretrained_path}")
            state_dict = torch.load(pretrained_path, map_location=DEVICE, weights_only=True)
            
            # [Simple Mapping] Add 'backbone.' prefix, skip 'classifier.*'
            mapped_dict = {}
            for k, v in state_dict.items():
                if k.startswith("classifier"):
                    continue
                mapped_dict[f"backbone.{k}"] = v
            
            print(f"   🔍 Pretrained Keys: {len(state_dict)}, Mapped Keys: {len(mapped_dict)}")
            missing, unexpected = model.load_state_dict(mapped_dict, strict=False)
            loaded = len(mapped_dict) - len(unexpected)
            print(f"   ✅ Loaded Keys: {loaded}")
            print(f"   ⏭️  Missing Keys: {len(missing)} (Attention Pool + Heads)")
        else:
            print("⚠️ Pretrained weights not found. Falling back to Random Init.")
        
        # 모든 레이어 학습 가능 (Discriminative LR)
        optimizer = torch.optim.AdamW([
            {'params': model.backbone.parameters(), 'lr': 1e-4},       # Backbone: pretrained 기반 적극 학습
            {'params': model.attention_pool.parameters(), 'lr': 1e-3}, # Attention: 빠른 학습
            {'params': model.type_head.parameters(), 'lr': 1e-3},      # Head: 빠른 학습
            {'params': model.abnormal_head.parameters(), 'lr': 1e-3},  # Head: 빠른 학습
        ], weight_decay=1e-2)
    else:
        raise ValueError(f"Unknown mode: {mode}. Must be 'baseline' or 'finetune'")

    # [Cost-sensitive Loss] Abnormal(안전 직결)에 가중치 부여 (pos_weight 사용)
    class_weights = class_weights.to(DEVICE)
    assert len(class_weights) == len(TYPE_LABELS), \
        f"class_weights length ({len(class_weights)}) must match TYPE_LABELS ({len(TYPE_LABELS)})"
    
    ABNORMAL_LOSS_WEIGHT = 1.5
    pos_weight = torch.tensor([ABNORMAL_LOSS_WEIGHT]).to(DEVICE)
    
    criterion_type = nn.CrossEntropyLoss(weight=class_weights, ignore_index=-100)
    criterion_abn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    early_stopping = EarlyStopping(patience=COMMON_CONFIG["early_stop_patience"], 
                                   min_epochs=COMMON_CONFIG["early_stop_min_epochs"])

    best_f1 = 0
    save_path = f"./ai/weights/audio/yamnet_{mode}.pt"
    os.makedirs(os.path.dirname(save_path), exist_ok=True)

    # 3. Epoch Loop
    for epoch in range(epochs):
        model.train()
        train_loss = 0
        
        for batch in train_loader:
            x = batch["mel_input"].to(DEVICE)
            # [Fix] Ensure 4D input (B, 1, F, T)
            if x.dim() == 3:
                x = x.unsqueeze(1)
            
            t_labels = batch["type_label"].to(DEVICE)
            a_labels = batch["abnormal_label"].to(DEVICE)
            
            optimizer.zero_grad()
            t_logits, a_logits = model(x)
            
            # Loss Calculation (Masked for Abnormal Only Types)
            is_abn = (a_labels == 1)
            if is_abn.any():
                loss_t = criterion_type(t_logits[is_abn], t_labels[is_abn])
            else:
                loss_t = torch.tensor(0.0, device=DEVICE) # Fixed: Ensure Tensor type
            
            # [Cost-sensitive Loss] pos_weight is already applied in criterion_abn
            # Ensures False Negative penalty (Recall priority)
            loss_a = criterion_abn(a_logits, a_labels.float())
            
            loss = 2.0 * loss_t + loss_a  # Type 분류에 가중치 부여
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0) # Gradient Clipping 추가
            optimizer.step()
            train_loss += loss.item()

        # Validation
        val_metrics = evaluate(model, val_loader)
        print(f"Epoch [{epoch+1}/{epochs}] Loss: {train_loss/len(train_loader):.4f} | "
              f"Safety F1: {val_metrics['safety_joint_f1']:.4f} | Recall: {val_metrics['defect_recall']:.4f}")

        # Safety-critical Monitoring: Use Safety Joint F1 for EarlyStopping
        if early_stopping.step(val_metrics['safety_joint_f1'], epoch):
            break
            
        if val_metrics['safety_joint_f1'] > best_f1:
            best_f1 = val_metrics['safety_joint_f1']
            torch.save(model.state_dict(), save_path)
            print(f"🌟 Best Model Saved (Epoch {epoch+1})")

    # Final Evaluation (Traditional)
    test_metrics = evaluate(model, test_loader, verbose=False, save_attention=True, mode=mode)
    
    # ── Advanced Metrics (Operational) ──
    print(f"🧪 Calculating Advanced Metrics (FPR@P99x, TRR, NRS, Div)...", flush=True)
    test_labels, test_scores, test_feats = get_scores_and_features(model, test_loader)
    
    # Train subset for divergence
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

    # [Benchmark Metrics] Add Latency & Model Size
    sample_input = torch.randn(1, 1, 64, 501).to(DEVICE) # (B, 1, F, T) - Standardized
    latency = measure_latency(model, sample_input, DEVICE)
    
    param_count = sum(p.numel() for p in model.parameters())
    model_size = param_count * 4 / (1024 * 1024) # MB (FP32)
    
    test_metrics.update({
        "model": "yamnet",
        "mode": mode,
        **fpr_metrics,
        "trr": round(trr, 4), "nrs": round(nrs, 4), "divergence": round(div, 4),
        "latency_ms": latency,
        "model_size_mb": model_size,
        "uncertain_pct": 0.0 # Placeholder for OOD
    })
    
    save_metrics("yamnet", mode, test_metrics)

    # 📝 Print Benchmark-Style Table
    print("\n" + "="*136)
    print("📊 YAMNet Benchmark Result")
    print("="*136)
    # Header with F1 + Recall per class
    print(f"{'Model':<25} {'Mode':<12} {'Abn P':<6} {'Abn R':<6} {'Abn F1':<6} | {'starter':<18} {'engine':<18} {'brake':<18} {'Macro F1':<10} {'Acc':<6} | {'Uncert%':<7} | {'ms':>6} {'MB':>4}")
    print(f"{'':.<25} {'':.<12} {'':.<6} {'':.<6} {'':.<6} | {'F1    R     P':<18} {'F1    R     P':<18} {'F1    R     P':<18} {'':.<10} {'':.<6} | {'':.<7} | {'':>6} {'':>4}")
    print("-" * 160)

    abn_prec = test_metrics["abnormal_precision"]
    abn_rec = test_metrics["defect_recall"]
    abn_f1 = test_metrics["abnormal_f1"]
    s_f1 = test_metrics.get("starter_f1", 0.0)
    s_r  = test_metrics.get("starter_recall", 0.0)
    s_p  = test_metrics.get("starter_prec", 0.0)
    e_f1 = test_metrics.get("engine_f1", 0.0)
    e_r  = test_metrics.get("engine_recall", 0.0)
    e_p  = test_metrics.get("engine_prec", 0.0)
    b_f1 = test_metrics.get("brake_f1", 0.0)
    b_r  = test_metrics.get("brake_recall", 0.0)
    b_p  = test_metrics.get("brake_prec", 0.0)
    macro_f1 = test_metrics["type_macro_f1"]
    acc = test_metrics["type_acc"]
    uncert = test_metrics["uncertain_pct"]
    ms = latency
    mb = model_size

    row = (f"{arch:<25} {mode:<12} "
           f"{abn_prec:.4f} {abn_rec:.4f} {abn_f1:.4f} | "
           f"{s_f1:.2f} {s_r:.2f} {s_p:.2f}       "
           f"{e_f1:.2f} {e_r:.2f} {e_p:.2f}       "
           f"{b_f1:.2f} {b_r:.2f} {b_p:.2f}       "
           f"{macro_f1:.4f}     {acc:.4f} | "
           f"{uncert:>6.1f}% | {ms:>6.1f} {mb:>4.1f}")

    print(row)
    print("="*160)
    # NOTE: Embedding centroid & OOD thresholding are applied at inference time (app/services/audio)

def evaluate(model, loader, verbose=False, save_attention=False, mode="unknown"):
    model.eval()
    all_t_preds, all_t_labels = [], []
    all_a_preds, all_a_labels = [], []
    
    # [Visualization Data]
    attn_data = {
        "starter": [], "engine": [], "brake": [], "normal": []
    }
    
    # [Entropy Statistics]
    entropy_stats = {"normal": [], "abnormal": []}

    with torch.no_grad():
        for batch in loader:
            x = batch["mel_input"].to(DEVICE)
            
            if save_attention:
                # Upgraded forward signature: type_logits, abn_logits, time_attn, patch_attn, entropy
                t_log, a_log, time_attn, patch_attn, entropy = model(x, return_attn=True)
            else:
                t_log, a_log = model(x)
            
            # Abnormal detection
            a_preds = (torch.sigmoid(a_log) > 0.5).int().cpu().numpy()
            all_a_preds.extend(a_preds)
            all_a_labels.extend(batch["abnormal_label"].int().numpy())
            
            # Type classification (GT Abnormal Only)
            t_probs = torch.softmax(t_log, dim=1)
            t_preds = torch.argmax(t_probs, dim=1).cpu().numpy()
            t_labels = batch["type_label"].numpy()
            
            mask = (t_labels != -100)
            all_t_preds.extend(t_preds[mask])
            all_t_labels.extend(t_labels[mask])

            # [Collect Attention & Entropy] Save 5 samples per class
            if save_attention:
                bs = x.size(0)
                for i in range(bs):
                    label_idx = t_labels[i]
                    is_abnormal = (label_idx != -100)
                    
                    # Entropy collection
                    ent_val = entropy[i].item()
                    if is_abnormal:
                        entropy_stats["abnormal"].append(ent_val)
                    else:
                        entropy_stats["normal"].append(ent_val)

                    # Attention Weight Collection
                    if is_abnormal: 
                        cls_name = TYPE_LABELS[label_idx]
                        if len(attn_data[cls_name]) < 5:
                            attn_data[cls_name].append({
                                "time_attn": time_attn[i].cpu().numpy(),
                                "patch_attn": patch_attn[i].cpu().numpy(),
                                "entropy": ent_val
                            })
                    else: # Normal
                        if len(attn_data["normal"]) < 5:
                            attn_data["normal"].append({
                                "time_attn": time_attn[i].cpu().numpy(),
                                "patch_attn": patch_attn[i].cpu().numpy(),
                                "entropy": ent_val
                            })

    # [Save Attention Artifacts]
    if save_attention:
        save_path = f"./ai/runs/vis_attention_yamnet_{mode}.pkl"
        import pickle
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, "wb") as f:
            pickle.dump(attn_data, f)
        print(f"🎨 Attention weights saved to {save_path}")
        
        # [Log Entropy Stats]
        norm_ent = np.mean(entropy_stats["normal"]) if entropy_stats["normal"] else 0.0
        abn_ent = np.mean(entropy_stats["abnormal"]) if entropy_stats["abnormal"] else 0.0
        print(f"🧩 Attention Entropy (Peaky=Low, Flat=High): Normal={norm_ent:.4f}, Abnormal={abn_ent:.4f}")

    # Metrics
    macro_f1 = f1_score(all_t_labels, all_t_preds, average='macro', zero_division=0)
    type_acc = accuracy_score(all_t_labels, all_t_preds)
    
    abnormal_f1 = f1_score(all_a_labels, all_a_preds, average='binary', zero_division=0)
    abnormal_prec = precision_score(all_a_labels, all_a_preds, average='binary', zero_division=0)
    defect_recall = recall_score(all_a_labels, all_a_preds, average='binary', zero_division=0)
    
    # Per-class metrics for benchmark table
    per_class_f1 = f1_score(all_t_labels, all_t_preds, average=None, zero_division=0)
    per_class_recall = recall_score(all_t_labels, all_t_preds, average=None, zero_division=0)
    per_class_prec = precision_score(all_t_labels, all_t_preds, average=None, zero_division=0)
    class_metrics = {}
    for i, name in enumerate(TYPE_LABELS):
        class_metrics[f"{name}_f1"] = per_class_f1[i] if i < len(per_class_f1) else 0.0
        class_metrics[f"{name}_recall"] = per_class_recall[i] if i < len(per_class_recall) else 0.0
        class_metrics[f"{name}_prec"] = per_class_prec[i] if i < len(per_class_prec) else 0.0
    
    # [Joint Metric] Harmonic Mean of Detection & Type Classification
    if macro_f1 > 0 and abnormal_f1 > 0:
        safety_joint_f1 = 2 * (macro_f1 * abnormal_f1) / (macro_f1 + abnormal_f1)
    else:
        safety_joint_f1 = 0.0
    
    if verbose:
        print("\n[ 📋 Detailed Classification Report (Abnormal Only) ]")
        print(classification_report(all_t_labels, all_t_preds, target_names=TYPE_LABELS, zero_division=0))
    
    metrics = {
        "type_macro_f1": macro_f1,
        "type_acc": type_acc,
        "abnormal_f1": abnormal_f1,
        "abnormal_precision": abnormal_prec, 
        "safety_joint_f1": safety_joint_f1,
        "defect_recall": defect_recall,
        "abnormal_recall": defect_recall 
    }
    metrics.update(class_metrics)
    return metrics

def get_scores_and_features(model, loader):
    """지표 계산을 위한 예측 점수와 feature 추출"""
    model.eval()
    all_scores = []
    all_labels = []
    all_features = []
    
    with torch.no_grad():
        for batch in loader:
            x = batch["mel_input"].to(DEVICE)
            a_lbl = batch["abnormal_label"].to(DEVICE)
            
            t_log, a_log = model(x)
            probs = torch.sigmoid(a_log).cpu().numpy() # Abnormal probability
            
            feats = model.get_features(x)
            
            all_scores.extend(probs)
            all_labels.extend(a_lbl.cpu().numpy())
            all_features.append(feats.cpu().numpy())
            
    return np.array(all_labels), np.array(all_scores), np.concatenate(all_features, axis=0)

# =============================================================================
# Logging Helper
# =============================================================================
import sys
import datetime

class LoggerTee:
    """Writes to both stdout/stderr and a file"""
    def __init__(self, *files):
        self.files = files
    def write(self, obj):
        for f in self.files:
            f.write(obj)
            f.flush() # Auto-flush
    def flush(self):
        for f in self.files:
            f.flush()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", type=str, default="baseline", choices=["baseline", "finetune"])
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch_size", type=int, default=16)
    parser.add_argument("--arch", type=str, default="yamnet") # Used in table printing
    args = parser.parse_args()
    
    # [Logging Setup]
    TIMESTAMP = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    LOG_DIR = "./ai/runs"
    os.makedirs(LOG_DIR, exist_ok=True)
    LOG_FILE = os.path.join(LOG_DIR, f"yamnet_training_{args.mode}_{TIMESTAMP}.log")
    
    # Redirect stdout/stderr to file + console
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    
    with open(LOG_FILE, "a", encoding="utf-8") as log_f:
        sys.stdout = LoggerTee(sys.stdout, log_f)
        sys.stderr = LoggerTee(sys.stderr, log_f)
        
        print(f"📄 Logging to: {LOG_FILE}")
        try:
            train(args.mode, args.epochs, args.batch_size)
        except Exception as e:
            print(f"\n❌ Error during training: {e}")
            raise e
        finally:
            sys.stdout = original_stdout
            sys.stderr = original_stderr
