# ai/scripts/audio/train_audio.py
"""
AST 기계 소음 분류 모델 학습 도구 (Audio Trainer - Optimized)

[역할]
1. 데이터 파티션: 미리 분할된 'train' 및 'test' 디렉토리에서 데이터를 로드합니다.
2. 불균형 해소: Class Weight를 적용하여 샘플 수가 적은 비정상 소리에 대한 학습 가중치를 높입니다.
3. 데이터 증강: 비정상 데이터에 대해 Pitch Shift 등 Augmentation을 적용하여 견고함을 높입니다.
4. 성능 리포트: Macro-F1, Precision, Recall 등을 포함한 정밀 리포트를 제공합니다.

[사용법]
python ai/scripts/audio/train_audio.py --mode all --epochs 10
"""
import argparse
import os
import sys
from pathlib import Path

# 프로젝트 루트를 PATH에 추가 (ModuleNotFoundError 해결)
project_root = str(Path(__file__).parents[3])  # ai/scripts/audio/train_audio.py -> 루트
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import torch
import numpy as np
import csv
import librosa
from transformers import ASTForAudioClassification, ASTFeatureExtractor, Trainer, TrainingArguments
from datasets import Dataset
from pathlib import Path
from sklearn.metrics import precision_recall_fscore_support, accuracy_score, confusion_matrix
from collections import Counter
from torch import nn

# =============================================================================
# [설정] 경로 및 하이퍼파라미터
# =============================================================================
MODEL_NAME = "MIT/ast-finetuned-audioset-10-10-0.4593"
OUTPUT_DIR = "./ai/runs/audio_model"
SAVE_PATH = "./ai/weights/audio/best_ast_model"

TRAIN_DATA_DIR = "./ai/data/audio/train"
TEST_DATA_DIR = "./ai/data/audio/test"

LABEL_LIST = ["normal", "engine", "brake", "starter"]
label2id = {label: i for i, label in enumerate(LABEL_LIST)}
id2label = {i: label for i, label in enumerate(LABEL_LIST)}

# 데이터셋 변수
train_dataset = None
eval_dataset = None
test_dataset = None
feature_extractor = None
class_weights = None

import concurrent.futures
from functools import partial
from ai.app.services.audio.audio_preprocessing import (
    trim_silence_rms, apply_bandpass_filter, calculate_speech_ratio,
    apply_speech_soft_masking, apply_spectral_gating
)

# =============================================================================
# 1. 데이터 증강 및 고도화된 전처리 (Preprocessing)
# =============================================================================
def spec_augment(spec, time_mask_param=30, freq_mask_param=20):
    """
    SpecAugment: AST에 특히 효과적인 증강 기법
    Pitch shift보다 안전하게 스펙트로그램 레벨에서 마스킹
    """
    # Time masking
    if len(spec.shape) == 2:
        freq_bins, time_steps = spec.shape
        t = np.random.randint(0, min(time_mask_param, time_steps))
        t0 = np.random.randint(0, max(1, time_steps - t))
        spec[:, t0:t0+t] = 0
        
        # Frequency masking
        f = np.random.randint(0, min(freq_mask_param, freq_bins))
        f0 = np.random.randint(0, max(1, freq_bins - f))
        spec[f0:f0+f, :] = 0
    return spec

def augment_audio(y, sr=16000):
    """
    비정상 데이터용 오디오 증강
    [v2] SpecAugment 추가, 보수적 pitch shift 유지
    """
    choice = np.random.choice(['none', 'noise', 'shift', 'spec_aug'], p=[0.2, 0.3, 0.2, 0.3])
    
    if choice == 'noise':
        # Band-limited noise (더 현실적)
        noise_amp = 0.01 * np.random.uniform() * np.max(y)
        noise = np.random.normal(size=y.shape) * noise_amp
        return y + noise
    elif choice == 'shift':
        shift = int(sr * np.random.uniform(-0.3, 0.3))
        return np.roll(y, shift)
    elif choice == 'spec_aug':
        # SpecAugment는 feature_extractor 후에 적용되므로 여기서는 플래그만 설정
        return y  # spec_aug는 후처리로 진행
    
    return y

def process_single_audio(item, is_train=False, is_baseline=False):
    """
    단일 오디오 파일에 대해 고도화 전처리 적용 (병렬 처리용)
    [핵심 개선] 비정상 클래스는 VAD/Spectral Gating을 약화
    """
    try:
        y, sr = librosa.load(item["audio"], sr=16000)
        label = item["label"]
        
        # 1. Silence Trim (공통)
        y = trim_silence_rms(y, sr)
        
        # 2. Band-pass Filter (공통)
        y = apply_bandpass_filter(y, sr)
        
        # 3. VAD & Speech Masking (정상 데이터에만 강하게 적용)
        speech_ratio, vad_mask = calculate_speech_ratio(y, sr)
        if label == "normal" and speech_ratio > 0.2:
            y = apply_speech_soft_masking(y, sr, vad_mask)
        # 비정상은 약한 마스킹 또는 스킵 (기계음 보존)
            
        # 4. Spectral Gating (정상만 적용, 비정상은 min_gain 높게)
        if label == "normal":
            y = apply_spectral_gating(y, sr, min_gain=0.2)
        else:
            y = apply_spectral_gating(y, sr, min_gain=0.5)  # 약하게
        
        # 5. RMS Normalization (공통)
        target_rms = 0.1
        current_rms = np.sqrt(np.mean(y**2)) + 1e-8
        y = y * (target_rms / current_rms)

        # 6. Data Augmentation (학습 시 비정상만)
        if not is_baseline and is_train and label != "normal":
            y = augment_audio(y, sr)
            
        return {"audio_array": y, "label": label, "path": item["audio"]}
    except Exception as e:
        return {"error": str(e), "path": item["audio"]}

def load_data_from_dir(base_dir):
    """
    지정된 디렉토리(train/test)에서 데이터를 로드합니다.
    [핵심] 폴더 직접 스캔을 우선, metadata는 보조로만 사용
    """
    data_list = []
    used_files = set()

    # 1. normal 폴더 직접 스캔
    normal_dir = os.path.join(base_dir, "normal")
    if os.path.exists(normal_dir):
        for f in os.listdir(normal_dir):
            if f.endswith('.wav'):
                full_path = os.path.join(normal_dir, f)
                data_list.append({"audio": full_path, "label": "normal"})
                used_files.add(os.path.abspath(full_path))
    
    # 2. abnormal 폴더 직접 스캔 (engine, brake, starter)
    abnormal_dir = os.path.join(base_dir, "abnormal")
    if os.path.exists(abnormal_dir):
        for cls in ["engine", "brake", "starter"]:
            cls_dir = os.path.join(abnormal_dir, cls)
            if not os.path.exists(cls_dir):
                continue
            for f in os.listdir(cls_dir):
                if f.endswith(".wav"):
                    full_path = os.path.join(cls_dir, f)
                    data_list.append({"audio": full_path, "label": cls})
                    used_files.add(os.path.abspath(full_path))
    
    return data_list

def prepare_data(mode="all"):
    global train_dataset, eval_dataset, test_dataset, feature_extractor, class_weights
    
    print(f"\n[Step 1] 데이터 로드 및 고도화 전처리 시작 (Target Mode: {mode})...")
    
    # 1. 원시 파일 리스트 로드
    train_raw = load_data_from_dir(TRAIN_DATA_DIR) if mode in ["train", "all"] else []
    test_raw = load_data_from_dir(TEST_DATA_DIR) if mode in ["baseline", "test", "all"] else []
    
    if (mode in ["train", "all"] and not train_raw) or (mode in ["baseline", "test", "all"] and not test_raw):
        print("[Error] 데이터를 찾을 수 없습니다. 경로를 확인하세요.")
        return False

    # [Sanity Check] 데이터 분포 출력
    if train_raw:
        print(f"[Sanity Check] Train Label Distribution: {dict(Counter([x['label'] for x in train_raw]))}")
    if test_raw:
        print(f"[Sanity Check] Test Label Distribution: {dict(Counter([x['label'] for x in test_raw]))}")

    # 2. 클래스 가중치 계산
    if train_raw:
        labels_all = [x['label'] for x in train_raw]
        counts = [labels_all.count(l) for l in LABEL_LIST]
        total = sum(counts)
        weights = [total / (len(LABEL_LIST) * c + 1e-8) for c in counts]
        class_weights = torch.tensor(weights, dtype=torch.float)
        print(f"[Info] 라벨 분포 (Train): {dict(zip(LABEL_LIST, counts))}")

    # 3. Feature Extractor
    feature_extractor = ASTFeatureExtractor.from_pretrained(MODEL_NAME)

    def parallel_preprocess(examples, desc="Data", is_train=False, is_baseline=False):
        """병렬 전처리 실행 및 진행률 출력"""
        print(f"[Info] {desc} 전처리 중 (Parallel, 총 {len(examples)}개)...")
        results = []
        
        # CPU 코어 수 고려 (너무 많으면 메모리 부족 주의)
        num_workers = min(os.cpu_count(), 4) # 메모리 안전을 위해 최대 4개로 제한 추천
        
        with concurrent.futures.ProcessPoolExecutor(max_workers=num_workers) as executor:
            # 부분 적용 함수 생성
            worker_fn = partial(process_single_audio, is_train=is_train, is_baseline=is_baseline)
            
            # 진행 상황 추적을 위한 future 매핑
            future_to_item = {executor.submit(worker_fn, item): i for i, item in enumerate(examples)}
            
            completed = 0
            for future in concurrent.futures.as_completed(future_to_item):
                res = future.result()
                if "error" in res:
                    print(f"[Warning] 처리 실패: {res['path']} -> {res['error']}")
                else:
                    # Feature extraction with proper padding
                    input_values = feature_extractor(
                        res["audio_array"], sampling_rate=16000, 
                        return_tensors="pt", 
                        padding="longest",  # max_length 대신 longest 사용 (무음 학습 방지)
                        truncation=True,
                        max_length=1024  # AST 기준 ~10초
                    )["input_values"].squeeze(0).numpy()
                    
                    # SpecAugment (is_train일 때만)
                    if is_train and res["label"] != "normal":
                        input_values = spec_augment(input_values)
                    
                    results.append({
                        "input_values": input_values,
                        "labels": label2id[res["label"]]
                    })
                
                completed += 1
                if completed % 100 == 0 or completed == len(examples):
                    print(f"  > {desc} 진행도: {completed}/{len(examples)} ({ (completed/len(examples))*100:.1f}%)")
        
        return results

    # 4. Dataset 생성 (병렬 로딩)
    if mode in ["train", "all"]:
        from sklearn.model_selection import train_test_split
        t_data, v_data = train_test_split(train_raw, test_size=0.1, stratify=[x['label'] for x in train_raw], random_state=42)
        train_dataset = Dataset.from_list(parallel_preprocess(t_data, "Train", is_train=True))
        eval_dataset = Dataset.from_list(parallel_preprocess(v_data, "Valid", is_train=False))

    if mode in ["baseline", "test", "all"]:
        test_dataset = Dataset.from_list(parallel_preprocess(test_raw, "Test", is_train=False, is_baseline=(mode=="baseline")))

    # Tensor 형식 설정
    for ds in [train_dataset, eval_dataset, test_dataset]:
        if ds: ds.set_format(type="torch", columns=["input_values", "labels"])

    print(f"[✓] 준비 완료!")
    return True

# =============================================================================
# 3. 모델 베이스라인 평가 (학습 전)
# =============================================================================
def evaluate_baseline():
    print("\n" + "="*50)
    print("[Step 2] 베이스라인 모델 평가 (Pre-trained)")
    print("="*50)
    print("""
[Baseline Definition]
1. Model: Pre-trained AST (finetuned-audioset)
2. Fine-tuning: False (Zero-shot evaluation)
3. Class Weighting: False
4. Data Augmentation: False
5. Metric: Macro F1 / Recall (Focus on Imbalance)

*Note: Pre-trained AST may show low scores for domain-specific labels 
(engine, brake, starter) that are not explicitly in AudioSet.
""")
    print(f"[Info] 사용 디바이스: {device}")
    
    # fine-tuning 전 원본 모델 로드
    model = ASTForAudioClassification.from_pretrained(
        MODEL_NAME, num_labels=len(LABEL_LIST), 
        label2id=label2id, id2label=id2label, 
        ignore_mismatched_sizes=True
    ).to(device)

    trainer = Trainer(model=model, compute_metrics=compute_metrics)
    results = trainer.predict(test_dataset)
    preds = np.argmax(results.predictions, axis=-1)
    labels = results.label_ids
    
    # Metrics
    precision, recall, f1, _ = precision_recall_fscore_support(labels, preds, average='macro')
    acc = accuracy_score(labels, preds)
    
    print(f"\n📊 베이스라인 결과 (Macro Metrics):")
    print(f" - Accuracy:  {acc:.4f}")
    print(f" - F1-Score:  {f1:.4f}")
    print(f" - Precision: {precision:.4f}")
    print(f" - Recall:    {recall:.4f}")
    
    # Confusion Matrix
    cm = confusion_matrix(labels, preds)
    print(f"\n🖼️ Confusion Matrix (rows=True, cols=Pred):")
    print(f"   Labels: {LABEL_LIST}")
    for i, row in enumerate(cm):
        print(f"   {LABEL_LIST[i]:>8}: {list(row)}")
    
    return {"accuracy": acc, "f1": f1, "precision": precision, "recall": recall}

# =============================================================================
# 3. 모델 및 트레이너 설정
# =============================================================================
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

class WeightedTrainer(Trainer):
    """Class Weights를 적용한 커스텀 트레이너"""
    def compute_loss(self, model, inputs, return_outputs=False):
        labels = inputs.get("labels")
        outputs = model(**inputs)
        logits = outputs.get("logits")
        # class_weights를 모델의 현재 디바이스로 이동
        loss_fct = nn.CrossEntropyLoss(weight=class_weights.to(model.device))
        loss = loss_fct(logits.view(-1, self.model.config.num_labels), labels.view(-1))
        return (loss, outputs) if return_outputs else loss

def compute_metrics(eval_pred):
    logits, labels = eval_pred
    predictions = np.argmax(logits, axis=-1)
    
    # 클래스 불균형을 고려하여 Macro F1 사용
    precision, recall, f1, _ = precision_recall_fscore_support(labels, predictions, average='macro')
    acc = accuracy_score(labels, predictions)
    
    return {
        "accuracy": acc,
        "f1": f1,
        "precision": precision,
        "recall": recall
    }

def train_model(epochs=10):
    print("\n" + "="*50 + "\n[Step 3] 모델 학습 시작\n" + "="*50)
    print(f"[Info] 사용 디바이스: {device}")
    
    model = ASTForAudioClassification.from_pretrained(
        MODEL_NAME, num_labels=len(LABEL_LIST), 
        label2id=label2id, id2label=id2label, 
        ignore_mismatched_sizes=True
    ).to(device)

    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        per_device_train_batch_size=8,
        num_train_epochs=epochs,
        learning_rate=3e-5,
        logging_steps=10,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="recall",  # Fault detection에서는 Recall이 핵심
        greater_is_better=True,
        fp16=torch.cuda.is_available(),
        push_to_hub=False,
    )

    trainer = WeightedTrainer(
        model=model, args=training_args,
        train_dataset=train_dataset, eval_dataset=eval_dataset,
        compute_metrics=compute_metrics,
    )

    trainer.train()
    
    os.makedirs(SAVE_PATH, exist_ok=True)
    model.save_pretrained(SAVE_PATH)
    feature_extractor.save_pretrained(SAVE_PATH)
    print(f"[✓] 모델 저장 완료: {SAVE_PATH}")
    return trainer

def evaluate_final():
    print("\n" + "="*50 + "\n[Step 4] 최종 모델 검증 (Golden Set)\n" + "="*50)
    print(f"[Info] 사용 디바이스: {device}")
    if not os.path.exists(SAVE_PATH): return
    
    model = ASTForAudioClassification.from_pretrained(SAVE_PATH).to(device)
    trainer = Trainer(model=model, compute_metrics=compute_metrics)
    results = trainer.predict(test_dataset)
    preds = np.argmax(results.predictions, axis=-1)
    labels = results.label_ids
    
    # Metrics
    precision, recall, f1, _ = precision_recall_fscore_support(labels, preds, average='macro')
    acc = accuracy_score(labels, preds)
    
    print(f"\n🎯 최종 테스트 결과 (Macro Metrics):")
    print(f" - Accuracy:  {acc:.4f}")
    print(f" - F1-Score:  {f1:.4f}")
    print(f" - Precision: {precision:.4f}")
    print(f" - Recall:    {recall:.4f}")
    
    # Confusion Matrix
    cm = confusion_matrix(labels, preds)
    print(f"\n🖼️ Confusion Matrix (rows=True, cols=Pred):")
    print(f"   Labels: {LABEL_LIST}")
    for i, row in enumerate(cm):
        print(f"   {LABEL_LIST[i]:>8}: {list(row)}")
    
    return {"accuracy": acc, "f1": f1, "precision": precision, "recall": recall}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", type=str, default="all", choices=["baseline", "train", "test", "all"])
    parser.add_argument("--epochs", type=int, default=10)
    args = parser.parse_args()

    if prepare_data(mode=args.mode):
        if args.mode == "baseline":
            evaluate_baseline()
        elif args.mode == "train":
            train_model(args.epochs)
        elif args.mode == "test":
            evaluate_final()
        elif args.mode == "all":
            evaluate_baseline()
            train_model(args.epochs)
            evaluate_final()

    print("\n✅ 모든 과정 완료!")