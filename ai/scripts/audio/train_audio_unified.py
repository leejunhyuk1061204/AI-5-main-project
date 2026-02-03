# ai/scripts/audio/train_audio_unified.py
"""
🚀 통합 오디오 학습 도구 v2

[Core Principles]
- Feature config = backbone 기준 (model_id X)
- Baseline/Train 동일 config 사용
- CNN random = inference only
- Ensemble ≤ AST baseline (sanity check)

[사용법]
python ai/scripts/audio/train_audio_unified.py --arch basic --mode baseline
python ai/scripts/audio/train_audio_unified.py --arch hybrid --mode baseline --baseline-type pretrained
python ai/scripts/audio/train_audio_unified.py --arch all --mode all --epochs 10
"""
import argparse
import os
import sys
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional, Dict, List

project_root = str(Path(__file__).parents[3])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import torch
import torch.nn as nn
import numpy as np
import librosa
import gc
from collections import Counter
from transformers import ASTForAudioClassification, ASTFeatureExtractor, Trainer, TrainingArguments
from datasets import Dataset, disable_caching
from sklearn.metrics import precision_recall_fscore_support, accuracy_score, confusion_matrix
from sklearn.model_selection import train_test_split

# 🔧 HuggingFace fingerprint caching 비활성화 (MemoryError 방지)
# - 대용량 in-memory arrays에서 fingerprint 계산 시 pickle 오버헤드 발생
# - 실험 코드에서는 reproducibility를 파일로 관리하므로 불필요
disable_caching()

from ai.app.services.audio.audio_preprocessing import (
    trim_silence_rms, apply_bandpass_filter, calculate_speech_ratio,
    apply_speech_soft_masking, apply_spectral_gating
)

# =============================================================================
# 설정 & 타입
# =============================================================================
@dataclass
class BaselineResult:
    arch: str
    component: str  # "ast", "cnn", "ensemble", "stage1", "stage2"
    baseline_type: str  # "pretrained", "trained", "random"
    acc: float
    f1: float
    recall: float

# Backbone 기준 Feature Config (model_id 아님!)
BACKBONE_CONFIGS = {
    "ast": {"max_length": 1024, "padding": "longest", "sr": 16000},
    "cnn": {"n_mels": 128, "target_len": 256, "sr": 16000},
}

DEFAULT_AST_MODEL = "MIT/ast-finetuned-audioset-10-10-0.4593"
TRAIN_DATA_DIR = "./ai/data/audio/train"
TEST_DATA_DIR = "./ai/data/audio/test"

LABEL_LIST = ["normal", "engine", "brake", "starter"]
STAGE1_LABELS = ["normal", "abnormal"]
STAGE2_LABELS = ["engine", "brake", "starter"]

label2id = {l: i for i, l in enumerate(LABEL_LIST)}
id2label = {i: l for i, l in enumerate(LABEL_LIST)}
stage1_label2id = {l: i for i, l in enumerate(STAGE1_LABELS)}
stage2_label2id = {l: i for i, l in enumerate(STAGE2_LABELS)}

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
_feature_extractor = None

def get_feature_extractor(model_id):
    global _feature_extractor
    if _feature_extractor is None:
        _feature_extractor = ASTFeatureExtractor.from_pretrained(model_id)
    return _feature_extractor

# =============================================================================
# 공통 함수
# =============================================================================
def load_data_from_dir(base_dir):
    data_list = []
    normal_dir = os.path.join(base_dir, "normal")
    if os.path.exists(normal_dir):
        for f in os.listdir(normal_dir):
            if f.endswith('.wav'):
                data_list.append({
                    "audio": os.path.join(normal_dir, f),
                    "label": "normal", "stage1_label": "normal", "stage2_label": None
                })
    
    abnormal_dir = os.path.join(base_dir, "abnormal")
    if os.path.exists(abnormal_dir):
        for cls in ["engine", "brake", "starter"]:
            cls_dir = os.path.join(abnormal_dir, cls)
            if os.path.exists(cls_dir):
                for f in os.listdir(cls_dir):
                    if f.endswith(".wav"):
                        data_list.append({
                            "audio": os.path.join(cls_dir, f),
                            "label": cls, "stage1_label": "abnormal", "stage2_label": cls
                        })
    return data_list

def process_audio(item, backbone="ast"):
    """전처리 파이프라인 (backbone-aware)"""
    try:
        cfg = BACKBONE_CONFIGS.get(backbone, BACKBONE_CONFIGS["ast"])
        sr = cfg.get("sr", 16000)
        y, _ = librosa.load(item["audio"], sr=sr)
        label = item.get("label", "normal")
        
        # 공통 전처리
        y = trim_silence_rms(y, sr)
        y = apply_bandpass_filter(y, sr)
        
        # AST backbone: 전체 전처리 적용
        # CNN backbone: 최소 전처리만 (silent trim + bandpass)
        if backbone == "ast":
            speech_ratio, vad_mask = calculate_speech_ratio(y, sr)
            if label == "normal" and speech_ratio > 0.2:
                y = apply_speech_soft_masking(y, sr, vad_mask)
            y = apply_spectral_gating(y, sr, min_gain=0.2 if label == "normal" else 0.5)
        
        # RMS 정규화
        target_rms = 0.1
        current_rms = np.sqrt(np.mean(y**2)) + 1e-8
        y = y * (target_rms / current_rms)
        
        # Mel for CNN
        mel_spec = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=128, fmax=8000)
        mel_spec_db = librosa.power_to_db(mel_spec, ref=np.max)
        
        return {"audio_array": y, "mel_spec": mel_spec_db, "backbone": backbone, **item}
    except Exception as e:
        return {"error": str(e), "path": item.get("audio", "unknown")}

def prepare_dataset_generator(data_list, label_key, label2id_map, model_id, desc="Data", backbone="ast"):
    """Generator 방식으로 메모리 효율적 Dataset 생성 (backbone-aware)"""
    fe = get_feature_extractor(model_id)
    cfg = BACKBONE_CONFIGS["ast"]
    cnn_cfg = BACKBONE_CONFIGS["cnn"]
    
    print(f"[Info] {desc} 전처리 중 ({len(data_list)}개, backbone={backbone})...")
    
    for i, item in enumerate(data_list):
        res = process_audio(item, backbone=backbone)
        if "error" in res or res.get(label_key) is None:
            continue
        
        ast_input = fe(
            res["audio_array"], sampling_rate=cfg["sr"],
            return_tensors="pt", padding=cfg["padding"],
            truncation=True, max_length=cfg["max_length"]
        )["input_values"].squeeze(0).numpy()
        
        mel_spec = res["mel_spec"]
        if mel_spec.shape[1] < cnn_cfg["target_len"]:
            mel_spec = np.pad(mel_spec, ((0, 0), (0, cnn_cfg["target_len"] - mel_spec.shape[1])))
        else:
            mel_spec = mel_spec[:, :cnn_cfg["target_len"]]
        
        yield {
            "input_values": ast_input,
            "cnn_input": mel_spec.astype(np.float32),
            "labels": label2id_map[res[label_key]]
        }
        
        if (i + 1) % 100 == 0:
            print(f"  > {desc}: {i+1}/{len(data_list)}")
            gc.collect()

def prepare_dataset(data_list, label_key, label2id_map, model_id, desc="Data", backbone="ast"):
    """Dataset 준비 (from_generator 사용으로 메모리 효율화)"""
    return Dataset.from_generator(
        prepare_dataset_generator,
        gen_kwargs={
            "data_list": data_list,
            "label_key": label_key,
            "label2id_map": label2id_map,
            "model_id": model_id,
            "desc": desc,
            "backbone": backbone
        }
    )

def evaluate(model, dataloader, label_names, arch, component, baseline_type) -> BaselineResult:
    """통합 평가 함수 - baseline/train/test 공용"""
    model.eval()
    all_preds, all_labels = [], []
    
    with torch.no_grad():
        for batch in dataloader:
            inputs = batch["input_values"].to(device)
            labels = batch["labels"]
            outputs = model(inputs)
            preds = torch.argmax(outputs.logits, dim=-1).cpu().numpy()
            all_preds.extend(preds)
            all_labels.extend(labels.numpy())
    
    acc = accuracy_score(all_labels, all_preds)
    p, r, f1, _ = precision_recall_fscore_support(all_labels, all_preds, average='macro', zero_division=0)
    
    print(f"\n📊 {arch}/{component}/{baseline_type}:")
    print(f" - Accuracy: {acc:.4f}, Macro F1: {f1:.4f}, Recall: {r:.4f}")
    
    cm = confusion_matrix(all_labels, all_preds)
    print(f"   Confusion Matrix: {label_names}")
    for i, row in enumerate(cm):
        print(f"   {label_names[i]:>8}: {list(row)}")
    
    return BaselineResult(arch=arch, component=component, baseline_type=baseline_type, acc=acc, f1=f1, recall=r)

def evaluate_simple(labels, preds, label_names, arch, component, baseline_type) -> BaselineResult:
    """간단한 평가 (이미 예측값이 있을 때)"""
    acc = accuracy_score(labels, preds)
    p, r, f1, _ = precision_recall_fscore_support(labels, preds, average='macro', zero_division=0)
    
    print(f"\n📊 {arch}/{component}/{baseline_type}:")
    print(f" - Accuracy: {acc:.4f}, Macro F1: {f1:.4f}, Recall: {r:.4f}")
    
    cm = confusion_matrix(labels, preds)
    print(f"   Confusion Matrix: {label_names}")
    for i, row in enumerate(cm):
        print(f"   {label_names[i]:>8}: {list(row)}")
    
    return BaselineResult(arch=arch, component=component, baseline_type=baseline_type, acc=acc, f1=f1, recall=r)

# =============================================================================
# CNN14 모델
# =============================================================================
class CNN14(nn.Module):
    def __init__(self, num_classes=4):
        super().__init__()
        self.conv = nn.Sequential(
            self._block(1, 64), self._block(64, 128), self._block(128, 256),
            self._block(256, 512), self._block(512, 1024), self._block(1024, 2048)
        )
        self.fc = nn.Sequential(nn.Linear(2048, 512), nn.ReLU(), nn.Dropout(0.3), nn.Linear(512, num_classes))
    
    def _block(self, in_c, out_c):
        return nn.Sequential(
            nn.Conv2d(in_c, out_c, 3, padding=1), nn.BatchNorm2d(out_c), nn.ReLU(),
            nn.Conv2d(out_c, out_c, 3, padding=1), nn.BatchNorm2d(out_c), nn.ReLU(),
            nn.AvgPool2d(2, 2)
        )
    
    def forward(self, x):
        if len(x.shape) == 3: x = x.unsqueeze(1)
        x = self.conv(x)
        x = torch.mean(x, dim=(2, 3))
        return self.fc(x)

# =============================================================================
# BASIC 아키텍처
# =============================================================================
class BasicArch:
    def __init__(self, model_id=DEFAULT_AST_MODEL):
        self.model_id = model_id
        self.save_path = "./ai/weights/audio/basic_model"
        self.output_dir = "./ai/runs/audio_basic"
    
    def baseline(self, test_data, baseline_type="pretrained") -> BaselineResult:
        print(f"\n{'='*60}\n[Basic] Baseline 평가 ({baseline_type})\n{'='*60}")
        
        ds = prepare_dataset(test_data, "label", label2id, self.model_id, "Test")
        ds.set_format(type="torch", columns=["input_values", "labels"])
        
        if baseline_type == "trained" and os.path.exists(self.save_path):
            model = ASTForAudioClassification.from_pretrained(self.save_path).to(device)
        else:
            model = ASTForAudioClassification.from_pretrained(
                self.model_id, num_labels=4, label2id=label2id, id2label=id2label, ignore_mismatched_sizes=True
            ).to(device)
        
        model.eval()
        trainer = Trainer(model=model)
        res = trainer.predict(ds)
        preds = np.argmax(res.predictions, axis=-1)
        
        return evaluate_simple(res.label_ids, preds, LABEL_LIST, "basic", "ast", baseline_type)
    
    def train(self, train_data, test_data, epochs) -> BaselineResult:
        print(f"\n{'='*60}\n[Basic] 4-Class 학습\n{'='*60}")
        
        t_data, v_data = train_test_split(train_data, test_size=0.1, stratify=[x['label'] for x in train_data], random_state=42)
        
        train_ds = prepare_dataset(t_data, "label", label2id, self.model_id, "Train")
        val_ds = prepare_dataset(v_data, "label", label2id, self.model_id, "Valid")
        test_ds = prepare_dataset(test_data, "label", label2id, self.model_id, "Test")
        
        for ds in [train_ds, val_ds, test_ds]:
            ds.set_format(type="torch", columns=["input_values", "labels"])
        
        labels = [x['label'] for x in train_data]
        counts = [labels.count(l) for l in LABEL_LIST]
        weights = torch.tensor([sum(counts) / (4 * c + 1e-8) for c in counts], dtype=torch.float)
        
        model = ASTForAudioClassification.from_pretrained(
            self.model_id, num_labels=4, label2id=label2id, id2label=id2label, ignore_mismatched_sizes=True
        ).to(device)
        
        class WTrainer(Trainer):
            def compute_loss(self, mdl, inputs, return_outputs=False):
                lbl = inputs.get("labels")
                out = mdl(**inputs)
                loss = nn.CrossEntropyLoss(weight=weights.to(mdl.device))(out.logits.view(-1, 4), lbl.view(-1))
                return (loss, out) if return_outputs else loss
        
        args = TrainingArguments(
            output_dir=self.output_dir, per_device_train_batch_size=8, num_train_epochs=epochs,
            learning_rate=3e-5, eval_strategy="epoch", save_strategy="epoch",
            load_best_model_at_end=True, metric_for_best_model="recall", greater_is_better=True,
            fp16=torch.cuda.is_available()
        )
        
        def metrics(ep):
            p = np.argmax(ep.predictions, axis=-1)
            _, r, f1, _ = precision_recall_fscore_support(ep.label_ids, p, average='macro')
            return {"accuracy": accuracy_score(ep.label_ids, p), "f1": f1, "recall": r}
        
        trainer = WTrainer(model=model, args=args, train_dataset=train_ds, eval_dataset=val_ds, compute_metrics=metrics)
        trainer.train()
        
        os.makedirs(self.save_path, exist_ok=True)
        model.save_pretrained(self.save_path)
        get_feature_extractor(self.model_id).save_pretrained(self.save_path)
        
        res = trainer.predict(test_ds)
        preds = np.argmax(res.predictions, axis=-1)
        return evaluate_simple(res.label_ids, preds, LABEL_LIST, "basic", "ast", "trained")

# =============================================================================
# 2-STAGE 아키텍처
# =============================================================================
class TwoStageArch:
    def __init__(self, model_id=DEFAULT_AST_MODEL):
        self.model_id = model_id
        self.s1_path = "./ai/weights/audio/stage1_model"
        self.s2_path = "./ai/weights/audio/stage2_model"
    
    def baseline(self, test_data, baseline_type="pretrained") -> Dict[str, BaselineResult]:
        print(f"\n{'='*60}\n[2-Stage] Baseline 평가 ({baseline_type})\n{'='*60}")
        
        # Stage 1: Normal vs Abnormal
        ds = prepare_dataset(test_data, "stage1_label", stage1_label2id, self.model_id, "Test(S1)")
        ds.set_format(type="torch", columns=["input_values", "labels"])
        
        if baseline_type == "trained" and os.path.exists(self.s1_path):
            model = ASTForAudioClassification.from_pretrained(self.s1_path).to(device)
        else:
            model = ASTForAudioClassification.from_pretrained(self.model_id, num_labels=2, ignore_mismatched_sizes=True).to(device)
        
        res = Trainer(model=model).predict(ds)
        s1_res = evaluate_simple(res.label_ids, np.argmax(res.predictions, axis=-1), STAGE1_LABELS, "2stage", "stage1", baseline_type)
        
        # Stage 2: Abnormal → Fault type
        abnormal = [x for x in test_data if x['stage1_label'] == 'abnormal']
        s2_res = None
        if abnormal:
            ds2 = prepare_dataset(abnormal, "stage2_label", stage2_label2id, self.model_id, "Test(S2)")
            ds2.set_format(type="torch", columns=["input_values", "labels"])
            
            if baseline_type == "trained" and os.path.exists(self.s2_path):
                model2 = ASTForAudioClassification.from_pretrained(self.s2_path).to(device)
            else:
                model2 = ASTForAudioClassification.from_pretrained(self.model_id, num_labels=3, ignore_mismatched_sizes=True).to(device)
            
            res2 = Trainer(model=model2).predict(ds2)
            s2_res = evaluate_simple(res2.label_ids, np.argmax(res2.predictions, axis=-1), STAGE2_LABELS, "2stage", "stage2", baseline_type)
        
        return {"s1": s1_res, "s2": s2_res} if s2_res else {"s1": s1_res}
    
    def train(self, train_data, test_data, epochs) -> Dict[str, BaselineResult]:
        print(f"\n{'='*60}\n[2-Stage] 학습\n{'='*60}")
        s1_res = self._train_stage(train_data, test_data, epochs, 1)
        s2_res = self._train_stage(train_data, test_data, epochs, 2)
        return {"s1": s1_res, "s2": s2_res}
    
    def _train_stage(self, train_data, test_data, epochs, stage) -> Optional[BaselineResult]:
        if stage == 1:
            label_key, label2id_map, labels_list, save_path, num_labels = "stage1_label", stage1_label2id, STAGE1_LABELS, self.s1_path, 2
            train_f, test_f = train_data, test_data
        else:
            label_key, label2id_map, labels_list, save_path, num_labels = "stage2_label", stage2_label2id, STAGE2_LABELS, self.s2_path, 3
            train_f = [x for x in train_data if x['stage1_label'] == 'abnormal']
            test_f = [x for x in test_data if x['stage1_label'] == 'abnormal']
        
        if not train_f:
            print(f"[Error] Stage {stage} 데이터 없음")
            return None
        
        print(f"\n--- Stage {stage} 학습 ---")
        t, v = train_test_split(train_f, test_size=0.1, stratify=[x[label_key] for x in train_f], random_state=42)
        
        train_ds = prepare_dataset(t, label_key, label2id_map, self.model_id, f"Train(S{stage})")
        val_ds = prepare_dataset(v, label_key, label2id_map, self.model_id, f"Valid(S{stage})")
        test_ds = prepare_dataset(test_f, label_key, label2id_map, self.model_id, f"Test(S{stage})")
        
        for ds in [train_ds, val_ds, test_ds]:
            ds.set_format(type="torch", columns=["input_values", "labels"])
        
        labels = [x[label_key] for x in train_f]
        counts = [labels.count(l) for l in labels_list]
        weights = torch.tensor([sum(counts) / (num_labels * c + 1e-8) for c in counts], dtype=torch.float)
        
        model = ASTForAudioClassification.from_pretrained(self.model_id, num_labels=num_labels, ignore_mismatched_sizes=True).to(device)
        
        class WTrainer(Trainer):
            def compute_loss(self, mdl, inputs, return_outputs=False):
                lbl = inputs.get("labels")
                out = mdl(**inputs)
                loss = nn.CrossEntropyLoss(weight=weights.to(mdl.device))(out.logits.view(-1, num_labels), lbl.view(-1))
                return (loss, out) if return_outputs else loss
        
        args = TrainingArguments(
            output_dir=f"./ai/runs/audio_s{stage}", per_device_train_batch_size=8, num_train_epochs=epochs,
            learning_rate=3e-5, eval_strategy="epoch", save_strategy="epoch",
            load_best_model_at_end=True, metric_for_best_model="recall", greater_is_better=True,
            fp16=torch.cuda.is_available()
        )
        
        def metrics(ep):
            p = np.argmax(ep.predictions, axis=-1)
            _, r, f1, _ = precision_recall_fscore_support(ep.label_ids, p, average='macro')
            return {"accuracy": accuracy_score(ep.label_ids, p), "f1": f1, "recall": r}
        
        trainer = WTrainer(model=model, args=args, train_dataset=train_ds, eval_dataset=val_ds, compute_metrics=metrics)
        trainer.train()
        
        os.makedirs(save_path, exist_ok=True)
        model.save_pretrained(save_path)
        get_feature_extractor(self.model_id).save_pretrained(save_path)
        
        res = trainer.predict(test_ds)
        return evaluate_simple(res.label_ids, np.argmax(res.predictions, axis=-1), labels_list, "2stage", f"stage{stage}", "trained")

# =============================================================================
# HYBRID 아키텍처
# =============================================================================
class HybridArch:
    def __init__(self, model_id=DEFAULT_AST_MODEL):
        self.model_id = model_id
        self.ast_path = "./ai/weights/audio/hybrid_ast"
        self.cnn_path = "./ai/weights/audio/hybrid_cnn"
    
    def baseline(self, test_data, baseline_type="pretrained") -> Dict[str, BaselineResult]:
        """3-Component baseline: AST, CNN(random), Ensemble"""
        print(f"\n{'='*60}\n[Hybrid] Baseline 평가 ({baseline_type})\n{'='*60}")
        
        ds = prepare_dataset(test_data, "label", label2id, self.model_id, "Test")
        
        # 1. AST baseline
        ast_res = self._ast_baseline(ds, baseline_type)
        
        # 2. CNN baseline (random init, inference only)
        cnn_res = self._cnn_baseline(ds)
        
        # 3. Ensemble baseline
        ens_res = self._ensemble_baseline(ds, baseline_type)
        
        # Sanity check: F1 기준
        if ens_res.f1 > ast_res.f1 + 0.01:
            print("⚠️ Warning: Ensemble F1 > AST F1 + 0.01 — possible bug or feature leakage!")
        
        return {"ast": ast_res, "cnn": cnn_res, "ensemble": ens_res}
    
    def _ast_baseline(self, ds, baseline_type) -> BaselineResult:
        ds.set_format(type="torch", columns=["input_values", "labels"])
        
        if baseline_type == "trained" and os.path.exists(self.ast_path):
            model = ASTForAudioClassification.from_pretrained(self.ast_path).to(device)
        else:
            model = ASTForAudioClassification.from_pretrained(
                self.model_id, num_labels=4, ignore_mismatched_sizes=True
            ).to(device)
        
        model.eval()
        res = Trainer(model=model).predict(ds)
        return evaluate_simple(res.label_ids, np.argmax(res.predictions, axis=-1), LABEL_LIST, "hybrid", "ast", baseline_type)
    
    def _cnn_baseline(self, ds) -> BaselineResult:
        """CNN random baseline: 학습 X, inference만
        
        ⚠️ Note: CNN은 AST와 동일한 전처리된 mel spectrogram을 사용합니다.
        이는 "preprocessing 효과"와 "model 구조 효과"를 분리하기 위함입니다.
        진짜 lower bound를 원하면 process_audio(item, backbone='cnn') 사용.
        """
        print("[CNN Baseline] Random init + AST-preprocessed mel (inference only)")
        model = CNN14(num_classes=4).to(device)
        model.eval()  # ❌ No training!
        
        all_preds, all_labels = [], []
        ds.set_format(type="torch", columns=["cnn_input", "labels"])
        dataloader = torch.utils.data.DataLoader(ds, batch_size=32)
        
        with torch.no_grad():
            for batch in dataloader:
                x = batch["cnn_input"].to(device)
                preds = torch.argmax(model(x), dim=-1).cpu().numpy()
                all_preds.extend(preds)
                all_labels.extend(batch["labels"].numpy())
        
        return evaluate_simple(all_labels, all_preds, LABEL_LIST, "hybrid", "cnn", "random")
    
    def _ensemble_baseline(self, ds, baseline_type, ast_weight=0.6) -> BaselineResult:
        """AST(pretrained/trained) + CNN(random) ensemble"""
        # ... logic truncated for brevity but essentially switching to DataLoader ...
        # [Full replacement needed below]
        assert 0.0 <= ast_weight <= 1.0, f"ast_weight must be 0-1, got {ast_weight}"
        print(f"[Ensemble Baseline] AST weight = {ast_weight:.0%}, CNN weight = {1-ast_weight:.0%}")
        print("  ⚠️ Note: Raw logit sum (no temperature scaling)")
        
        if baseline_type == "trained" and os.path.exists(self.ast_path):
            ast_model = ASTForAudioClassification.from_pretrained(self.ast_path).to(device)
        else:
            ast_model = ASTForAudioClassification.from_pretrained(
                self.model_id, num_labels=4, ignore_mismatched_sizes=True
            ).to(device)
        
        cnn_model = CNN14(num_classes=4).to(device)
        ast_model.eval()
        cnn_model.eval()
        
        all_preds, all_labels = [], []
        ds.set_format(type="torch", columns=["input_values", "cnn_input", "labels"])
        dataloader = torch.utils.data.DataLoader(ds, batch_size=32)
        
        with torch.no_grad():
            for batch in dataloader:
                ast_in = batch["input_values"].to(device)
                cnn_in = batch["cnn_input"].to(device)
                
                ast_logits = ast_model(ast_in).logits
                cnn_logits = cnn_model(cnn_in)
                
                logits = ast_weight * ast_logits + (1 - ast_weight) * cnn_logits
                preds = torch.argmax(logits, dim=-1).cpu().numpy()
                all_preds.extend(preds)
                all_labels.extend(batch["labels"].numpy())
        
        return evaluate_simple(all_labels, all_preds, LABEL_LIST, "hybrid", "ensemble", baseline_type)
    
    def train(self, train_data, test_data, epochs, ast_weight=0.6) -> BaselineResult:
        print(f"\n{'='*60}\n[Hybrid] 학습\n{'='*60}")
        
        # AST 학습
        print("\n--- AST 학습 ---")
        self._train_ast(train_data, test_data, epochs)
        
        # CNN 학습
        print("\n--- CNN14 학습 ---")
        self._train_cnn(train_data, test_data, epochs)
        
        # Ensemble 평가
        print("\n--- 앙상블 평가 ---")
        ds = prepare_dataset(test_data, "label", label2id, self.model_id, "Test(Ens)")
        return self._evaluate_trained_ensemble(ds, ast_weight)
    
    def _train_ast(self, train_data, test_data, epochs):
        t, v = train_test_split(train_data, test_size=0.1, stratify=[x['label'] for x in train_data], random_state=42)
        
        train_ds = prepare_dataset(t, "label", label2id, self.model_id, "Train(AST)")
        val_ds = prepare_dataset(v, "label", label2id, self.model_id, "Valid(AST)")
        
        for ds in [train_ds, val_ds]:
            ds.set_format(type="torch", columns=["input_values", "labels"])
        
        model = ASTForAudioClassification.from_pretrained(self.model_id, num_labels=4, ignore_mismatched_sizes=True).to(device)
        
        args = TrainingArguments(
            output_dir="./ai/runs/hybrid_ast", per_device_train_batch_size=8, num_train_epochs=epochs,
            learning_rate=3e-5, eval_strategy="epoch", save_strategy="epoch",
            load_best_model_at_end=True, metric_for_best_model="recall", greater_is_better=True,
            fp16=torch.cuda.is_available()
        )
        
        def metrics(ep):
            p = np.argmax(ep.predictions, axis=-1)
            _, r, f1, _ = precision_recall_fscore_support(ep.label_ids, p, average='macro')
            return {"accuracy": accuracy_score(ep.label_ids, p), "f1": f1, "recall": r}
        
        trainer = Trainer(model=model, args=args, train_dataset=train_ds, eval_dataset=val_ds, compute_metrics=metrics)
        trainer.train()
        
        os.makedirs(self.ast_path, exist_ok=True)
        model.save_pretrained(self.ast_path)
        get_feature_extractor(self.model_id).save_pretrained(self.ast_path)
    
    def _train_cnn(self, train_data, test_data, epochs):
        t, v = train_test_split(train_data, test_size=0.1, stratify=[x['label'] for x in train_data], random_state=42)
        
        train_ds = prepare_dataset(t, "label", label2id, self.model_id, "Train(CNN)")
        val_ds = prepare_dataset(v, "label", label2id, self.model_id, "Valid(CNN)")
        
        train_ds.set_format(type="torch", columns=["cnn_input", "labels"])
        val_ds.set_format(type="torch", columns=["cnn_input", "labels"])
        
        train_loader = torch.utils.data.DataLoader(train_ds, batch_size=16, shuffle=True)
        val_loader = torch.utils.data.DataLoader(val_ds, batch_size=16)
        
        model = CNN14(num_classes=4).to(device)
        optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4)
        
        best_f1 = 0
        for epoch in range(epochs):
            model.train()
            for bx, by in train_loader:
                bx = bx.to(device)
                by = by.clone().detach().to(device) if isinstance(by, torch.Tensor) else torch.tensor(by).to(device)
                optimizer.zero_grad()
                loss = nn.CrossEntropyLoss()(model(bx), by)
                loss.backward()
                optimizer.step()
            
            model.eval()
            all_p, all_l = [], []
            with torch.no_grad():
                for bx, by in val_loader:
                    all_p.extend(torch.argmax(model(bx.to(device)), dim=-1).cpu().numpy())
                    all_l.extend(by)
            
            _, _, f1, _ = precision_recall_fscore_support(all_l, all_p, average='macro')
            print(f"[Epoch {epoch+1}] Val F1: {f1:.4f}")
            
            if f1 > best_f1:
                best_f1 = f1
                os.makedirs(self.cnn_path, exist_ok=True)
                torch.save(model.state_dict(), os.path.join(self.cnn_path, "cnn14.pt"))
    
    def _evaluate_trained_ensemble(self, ds, ast_weight) -> BaselineResult:
        ast_model = ASTForAudioClassification.from_pretrained(self.ast_path).to(device)
        cnn_model = CNN14(num_classes=4).to(device)
        cnn_model.load_state_dict(torch.load(os.path.join(self.cnn_path, "cnn14.pt")))
        
        ast_model.eval()
        cnn_model.eval()
        
        all_preds, all_labels = [], []
        ds.set_format(type="torch", columns=["input_values", "cnn_input", "labels"])
        dataloader = torch.utils.data.DataLoader(ds, batch_size=32)
        
        with torch.no_grad():
            for batch in dataloader:
                ast_in = batch["input_values"].to(device)
                cnn_in = batch["cnn_input"].to(device)
                
                logits = ast_weight * ast_model(ast_in).logits + (1 - ast_weight) * cnn_model(cnn_in)
                preds = torch.argmax(logits, dim=-1).cpu().numpy()
                all_preds.extend(preds)
                all_labels.extend(batch["labels"].numpy())
        
        return evaluate_simple(all_labels, all_preds, LABEL_LIST, "hybrid", "ensemble", "trained")

# =============================================================================
# Main
# =============================================================================
def add_result_to_summary(summary: List, result: BaselineResult):
    summary.append([f"{result.arch}_{result.component}_{result.baseline_type}", result.acc, result.f1, result.recall])

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="🚀 통합 오디오 학습 도구 v2")
    parser.add_argument("--arch", type=str, default="basic", choices=["basic", "2stage", "hybrid", "all"])
    parser.add_argument("--mode", type=str, default="all", choices=["baseline", "train", "all"])
    parser.add_argument("--baseline-type", type=str, default="pretrained", choices=["pretrained", "trained"])
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--ast-weight", type=float, default=0.6)
    parser.add_argument("--model-id", type=str, default=DEFAULT_AST_MODEL)
    args = parser.parse_args()
    
    print(f"🚀 통합 오디오 학습 도구 v2")
    print(f"   디바이스: {device}")
    print(f"   아키텍처: {args.arch}")
    print(f"   모드: {args.mode}")
    print(f"   Baseline 타입: {args.baseline_type}")
    print(f"   에폭: {args.epochs}")
    
    train_data = load_data_from_dir(TRAIN_DATA_DIR)
    test_data = load_data_from_dir(TEST_DATA_DIR)
    
    print(f"\n[Data] Train: {dict(Counter([x['label'] for x in train_data]))}")
    print(f"[Data] Test: {dict(Counter([x['label'] for x in test_data]))}")
    
    archs = {
        "basic": BasicArch(args.model_id),
        "2stage": TwoStageArch(args.model_id),
        "hybrid": HybridArch(args.model_id)
    }
    final_summary = []
    
    if args.arch == "all":
        for name, arch in archs.items():
            print(f"\n{'#'*60}\n# {name.upper()} 아키텍처\n{'#'*60}")
            if args.mode in ["baseline", "all"]:
                m = arch.baseline(test_data, args.baseline_type)
                if name == "hybrid":
                    add_result_to_summary(final_summary, m["ast"])
                    add_result_to_summary(final_summary, m["cnn"])
                    add_result_to_summary(final_summary, m["ensemble"])
                elif name == "2stage":
                    add_result_to_summary(final_summary, m["s1"])
                    if m.get("s2"): add_result_to_summary(final_summary, m["s2"])
                else:
                    add_result_to_summary(final_summary, m)
            
            if args.mode in ["train", "all"]:
                if name == "hybrid":
                    m = arch.train(train_data, test_data, args.epochs, args.ast_weight)
                else:
                    m = arch.train(train_data, test_data, args.epochs)
                
                if name == "2stage":
                    add_result_to_summary(final_summary, m["s1"])
                    if m.get("s2"): add_result_to_summary(final_summary, m["s2"])
                else:
                    add_result_to_summary(final_summary, m)
    else:
        arch = archs[args.arch]
        if args.mode in ["baseline", "all"]:
            m = arch.baseline(test_data, args.baseline_type)
            if args.arch == "hybrid":
                add_result_to_summary(final_summary, m["ast"])
                add_result_to_summary(final_summary, m["cnn"])
                add_result_to_summary(final_summary, m["ensemble"])
            elif args.arch == "2stage":
                add_result_to_summary(final_summary, m["s1"])
                if m.get("s2"): add_result_to_summary(final_summary, m["s2"])
            else:
                add_result_to_summary(final_summary, m)
        
        if args.mode in ["train", "all"]:
            if args.arch == "hybrid":
                m = arch.train(train_data, test_data, args.epochs, args.ast_weight)
            else:
                m = arch.train(train_data, test_data, args.epochs)
            
            if args.arch == "2stage":
                add_result_to_summary(final_summary, m["s1"])
                if m.get("s2"): add_result_to_summary(final_summary, m["s2"])
            else:
                add_result_to_summary(final_summary, m)
    
    # 최종 요약
    if final_summary:
        print("\n" + "="*80)
        print(f"{'ARCH_COMPONENT_TYPE':<35} | {'ACC':<8} | {'F1':<8} | {'RECALL':<8}")
        print("-" * 80)
        for row in final_summary:
            print(f"{row[0]:<35} | {row[1]:.4f}   | {row[2]:.4f}   | {row[3]:.4f}")
        print("="*80)
    
    print("\n✅ 완료!")
