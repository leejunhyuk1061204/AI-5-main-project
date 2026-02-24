# ai/scripts/audio/train_audio.py
"""
AST 기계 소음 분류 모델 학습 도구 (Audio Trainer - Optimized)

[역할]
1. 데이터 파티션: 미리 분할된 'train' 및 'test' 디렉토리에서 데이터를 로드합니다.
2. 불균형 해소: Class Weight를 적용하여 샘플 수가 적은 비정상 소리에 대한 학습 가중치를 높입니다.
3. 데이터 증강: 비정상 데이터에 대해 Pitch Shift 등 Augmentation을 적용하여 견고함을 높입니다.
4. 성능 리포트: Macro-F1, Precision, Recall 등을 포함한 정밀 리포트를 제공합니다.

[사용법]
python ai/scripts/audio/train_audio.py --mode all --epochs 10 --batch_size 2 --grad_accum 4
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
from datasets import Dataset, Features, Value, Sequence
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

# [Path Config] RunPod과 로컬 환경 자동 감지
RUNPOD_DATA_PATH = "/workspace/large_data"
LOCAL_DATA_PATH = "ai/data"
DATA_ROOT = RUNPOD_DATA_PATH if os.path.exists(RUNPOD_DATA_PATH) else LOCAL_DATA_PATH

TRAIN_DATA_DIR = os.path.join(DATA_ROOT, "audio", "train")
TEST_DATA_DIR = os.path.join(DATA_ROOT, "audio", "test")

# [Environment Config] 환경 변수로 제어 가능
DEFAULT_BATCH_SIZE = int(os.getenv("BATCH_SIZE", "2"))  # Audio는 메모리 소모가 크므로 기본값 2
DEFAULT_GRAD_ACCUM = int(os.getenv("GRAD_ACCUM", "4"))

LABEL_LIST = ["normal", "engine", "brake", "starter"]
label2id = {label: i for i, label in enumerate(LABEL_LIST)}
id2label = {i: label for i, label in enumerate(LABEL_LIST)}

# 글로벌 변수
feature_extractor = None
class_weights = None

# =============================================================================
# [공통 상수] Abstraction layer for future ablation studies
# =============================================================================
# VAD Speech Ratio is essentially a "High-Energy Detector" 
# (Includes Engine RPM/Brake Squeal as high energy).
SPEECH_SKIP_THRESHOLD = 0.01  # Relaxed threshold (1%) to include almost all background sounds
SPEECH_MASK_THRESHOLD = 0.05  # Applied only to 'normal' samples (More aggressive masking)

import concurrent.futures
from functools import partial
from ai.app.services.audio.audio_preprocessing import (
    trim_silence_rms, apply_bandpass_filter, calculate_speech_ratio,
    apply_speech_soft_masking, apply_spectral_gating
)

# SpecAugment 제거 - AST와 shape 호환성 문제로 audio-level augmentation만 사용
# def spec_augment(spec, time_mask_param=30, freq_mask_param=20):
#     ... (audio-level augmentation으로 대체)

def augment_audio(y, sr=16000):
    """
    비정상 데이터용 오디오 증강 (Audio-level only - AST 호환)
    """
    choice = np.random.choice(['none', 'noise', 'shift', 'time_stretch'], p=[0.2, 0.3, 0.3, 0.2])
    
    if choice == 'noise':
        noise_amp = 0.01 * np.random.uniform() * np.max(np.abs(y))
        noise = np.random.normal(size=y.shape) * noise_amp
        return y + noise
    elif choice == 'shift':
        shift = int(sr * np.random.uniform(-0.3, 0.3))
        return np.roll(y, shift)
    elif choice == 'time_stretch':
        # 소폭 시간 신축 (0.9~1.1 배속)
        rate = np.random.uniform(0.9, 1.1)
        return librosa.effects.time_stretch(y, rate=rate)
    
    return y

def process_single_audio(item, is_train=False, is_baseline=False):
    """
    단일 오디오 파일 전처리
    - Samples with less than 10% detected speech were excluded from both training and evaluation.
    - Speech masking is applied only to normal samples to avoid suppressing 
      transient fault-related harmonics in abnormal classes.
    """
    try:
        y, sr = librosa.load(item["audio"], sr=16000)
        label = item["label"]
        
        # 공통 전처리
        y = trim_silence_rms(y, sr, top_db=50) # top_db=50: 무음 제거 기준 완화 (작은 소리도 유지)
        y = apply_bandpass_filter(y, sr)
        
        speech_ratio, vad_mask = calculate_speech_ratio(y, sr)
        
        # ✅ "자동으로 0개 처리" 방어 코드: VAD 기준 미달이라도 Skip하지 않고 포함
        if speech_ratio < SPEECH_SKIP_THRESHOLD:
            print(f"[Warning] Low speech ratio ({speech_ratio:.2%}), but preserving data (Defense Mode).")
            # return {"skip": "no_speech", "path": item["audio"]}

        # ✅ 'Normal' 클래스에 대해서만 Speech Masking 적용 (의도적 가정)
        if label == "normal" and speech_ratio > SPEECH_MASK_THRESHOLD:
            y = apply_speech_soft_masking(y, sr, vad_mask)
            
        # ✅ 전처리 불일치 해소: 모든 클래스/스플릿에 대해 min_gain=0.2 통일
        y = apply_spectral_gating(y, sr, min_gain=0.2)
        
        target_rms = 0.1
        current_rms = np.sqrt(np.mean(y**2)) + 1e-8
        y = y * (target_rms / current_rms)

        # ✅ Baseline mode: No augmentation/randomness applied by design to ensure reproducibility.
        if is_baseline:
            return {"audio_array": y, "label": label, "path": item["audio"]}

        if is_train and label != "normal":
            y = augment_audio(y, sr)
            
        return {"audio_array": y, "label": label, "path": item["audio"]}
    except Exception as e:
        return {"error": str(e), "path": item["audio"]}

def load_data_from_dir(base_dir):
    """
    디렉토리 스캔
    """
    data_list = []
    normal_dir = os.path.join(base_dir, "normal")
    if os.path.exists(normal_dir):
        for f in os.listdir(normal_dir):
            if f.endswith('.wav'):
                data_list.append({"audio": os.path.join(normal_dir, f), "label": "normal"})
    
    abnormal_dir = os.path.join(base_dir, "abnormal")
    if os.path.exists(abnormal_dir):
        for cls in ["engine", "brake", "starter"]:
            cls_dir = os.path.join(abnormal_dir, cls)
            if os.path.exists(cls_dir):
                for f in os.listdir(cls_dir):
                    if f.endswith(".wav"):
                        data_list.append({"audio": os.path.join(cls_dir, f), "label": cls})
    return data_list

def filter_audio_list(data_list, desc="Data"):
    """
    [Robust Filtering] 
    Dataset 생성 전, VAD 기반으로 무음 샘플을 미리 걸러냅니다.
    IndexError 및 Shard 이슈를 방지합니다.
    """
    print(f"[Info] {desc} 사전 검수 중 (샘플 수: {len(data_list)})...")
    filtered = []
    skipped = Counter()
    
    # 병렬 처리가 가능하면 좋지만, 메모리 안전을 위해 순차 혹은 소규모 병렬 권장
    for item in data_list:
        try:
            y, sr = librosa.load(item["audio"], sr=16000)
            y = trim_silence_rms(y, sr)
            ratio, _ = calculate_speech_ratio(y, sr)
            
            if ratio < SPEECH_SKIP_THRESHOLD:
                skipped[item["label"]] += 1
                continue
            filtered.append(item)
        except Exception:
            skipped["error"] += 1
            
    skip_total = sum(skipped.values())
    print(f"[Summary] {desc} 검수 완료: {len(filtered)} 유지, {skip_total} 제외 {dict(skipped)}")
    return filtered

def prepare_data(mode="all"):
    global feature_extractor, class_weights
    
    print(f"\n[Step 1] 데이터 준비 시작 (Mode: {mode})...")
    
    train_raw = load_data_from_dir(TRAIN_DATA_DIR) if mode in ["train", "all"] else []
    test_raw = load_data_from_dir(TEST_DATA_DIR) if mode in ["baseline", "test", "all"] else []
    
    if (mode in ["train", "all"] and not train_raw) or (mode in ["baseline", "test", "all"] and not test_raw):
        print("[Error] 데이터를 찾을 수 없습니다.")
        print(f"[Info] Checking paths:")
        print(f"  - RunPod path: {RUNPOD_DATA_PATH} (Exists: {os.path.exists(RUNPOD_DATA_PATH)})")
        print(f"  - Local path: {LOCAL_DATA_PATH} (Exists: {os.path.exists(LOCAL_DATA_PATH)})")
        print(f"  - Using: {DATA_ROOT}")
        print(f"  - Train dir: {TRAIN_DATA_DIR} (Exists: {os.path.exists(TRAIN_DATA_DIR)})")
        print(f"  - Test dir: {TEST_DATA_DIR} (Exists: {os.path.exists(TEST_DATA_DIR)})")
        return None, None, None

    if train_raw:
        # ✅ Pre-scan & Filter
        train_raw = filter_audio_list(train_raw, "Train")
        
        labels_all = [x['label'] for x in train_raw]
        counts = [labels_all.count(l) for l in LABEL_LIST]
        total = sum(counts)
        weights = [total / (len(LABEL_LIST) * c + 1e-8) for c in counts]
        # ✅ Immediate device move for safety and DDP readiness
        class_weights = torch.tensor(weights, dtype=torch.float).to(device)
    
    if test_raw:
        test_raw = filter_audio_list(test_raw, "Test")

    feature_extractor = ASTFeatureExtractor.from_pretrained(MODEL_NAME)

    # Dataset 생성 (Generator 방식 - RAM 절약 핵심)
    def dataset_generator(data_list, desc="Data", is_train=False, is_baseline=False):
        print(f"[Info] {desc} 데이터 생성 시작...")
        processed = 0
        
        for item in data_list:
            res = process_single_audio(item, is_train=is_train, is_baseline=is_baseline)
            
            # 사전 검수를 거쳤으므로 skip은 발생하지 않아야 함
            if "error" in res:
                print(f"[Error] Failed to process {item['audio']}: {res['error']}")
                continue
            if "skip" in res:
                print(f"[Skip] {item['audio']}: {res['skip']}")
                continue
            
            processed += 1
            # ✅ AST 규격: 모든 구간에서 input_values로 단일화하여 정합성 유지
            inputs = feature_extractor(
                res["audio_array"], 
                sampling_rate=16000, 
                return_tensors="pt",
                padding="longest",
                truncation=True
            )
            features = inputs["input_values"].squeeze(0).numpy()
            
            yield {"input_values": features, "labels": label2id[res["label"]]}
            
        print(f"[Summary] {desc} Dataset Ready: {processed} samples.")

    train_ds, eval_ds, test_ds = None, None, None

    features = Features({
        "input_values": Sequence(Sequence(Value("float32"))),
        "labels": Value("int64")
    })

    if mode in ["train", "all"]:
        from sklearn.model_selection import train_test_split
        t_data, v_data = train_test_split(train_raw, test_size=0.1, stratify=[x['label'] for x in train_raw], random_state=42)
        train_ds = Dataset.from_generator(dataset_generator, gen_kwargs={"data_list": t_data, "desc": "Train", "is_train": True}, features=features)
        eval_ds = Dataset.from_generator(dataset_generator, gen_kwargs={"data_list": v_data, "desc": "Valid", "is_train": False}, features=features)

    if mode in ["baseline", "test", "all"]:
        test_ds = Dataset.from_generator(dataset_generator, gen_kwargs={"data_list": test_raw, "desc": "Test", "is_train": False, "is_baseline": (mode=="baseline")}, features=features)

    print(f"[✓] 데이터셋 준비 완료")
    return train_ds, eval_ds, test_ds

# =============================================================================
# 3. 모델 베이스라인 평가
# =============================================================================
def evaluate_baseline(test_dataset):
    global class_weights
    print("\n" + "="*50 + "\n[Step 2] 베이스라인 모델 평가 (Preprocessing-aware)\n" + "="*50)
    
    # ✅ Safety: Baseline/Test 단계에서 학습용 가중치가 유출되지 않도록 명시적 초기화
    class_weights = None
    
    model = ASTForAudioClassification.from_pretrained(
        MODEL_NAME, num_labels=len(LABEL_LIST), label2id=label2id, id2label=id2label, ignore_mismatched_sizes=True
    ).to(device)
    trainer = Trainer(model=model, compute_metrics=compute_metrics)
    results = trainer.predict(test_dataset)
    _print_metrics(results.label_ids, np.argmax(results.predictions, axis=-1), "베이스라인")

def _print_metrics(labels, preds, title):
    precision, recall, f1, _ = precision_recall_fscore_support(labels, preds, average='macro')
    acc = accuracy_score(labels, preds)
    print(f"\n📊 {title} 결과: Accuracy: {acc:.4f}, F1: {f1:.4f}, Precision: {precision:.4f}, Recall: {recall:.4f}")
    cm = confusion_matrix(labels, preds)
    print(f"🖼️ CM: {cm}")

# =============================================================================
# 3. 모델 및 트레이너 설정
# =============================================================================
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

class WeightedTrainer(Trainer):
    """Class Weights를 적용한 커스텀 트레이너 (안전 처리 포함)"""
    def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None, **kwargs):
        labels = inputs.get("labels")
        outputs = model(**inputs)
        logits = outputs.get("logits")
        
        # ✅ class_weights 안전 처리 (baseline/test 모드에서도 안전)
        if class_weights is not None:
            loss_fct = nn.CrossEntropyLoss(weight=class_weights.to(model.device))
        else:
            loss_fct = nn.CrossEntropyLoss()
        
        loss = loss_fct(logits.view(-1, self.model.config.num_labels), labels.view(-1))
        return (loss, outputs) if return_outputs else loss

def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    precision, recall, f1, _ = precision_recall_fscore_support(labels, preds, average='macro')
    acc = accuracy_score(labels, preds)
    return {"accuracy": acc, "f1": f1, "precision": precision, "recall": recall}

def train_model(train_dataset, eval_dataset, args):
    print("\n" + "="*50 + "\n[Step 3] 모델 학습 시작\n" + "="*50)
    model = ASTForAudioClassification.from_pretrained(
        MODEL_NAME, num_labels=len(LABEL_LIST), label2id=label2id, id2label=id2label, ignore_mismatched_sizes=True
    ).to(device)

    # ✅ 초반 안정화를 위한 Freeze 전략 (선택적)
    if args.freeze_encoder:
        print("[Info] Encoder freezing enabled for first epochs...")
        for p in model.audio_spectrogram_transformer.encoder.parameters():
            p.requires_grad = False

    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        num_train_epochs=args.epochs,
        learning_rate=args.lr,  # ✅ LR 파라미터화
        logging_steps=10,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1",  # ✅ Macro-F1로 변경 (더 균형 잡힌 지표)
        greater_is_better=True,
        fp16=torch.cuda.is_available(),
        remove_unused_columns=False,
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
    print(f"[✓] 모델 저장: {SAVE_PATH}")

def evaluate_final(test_dataset):
    print("\n" + "="*50 + "\n[Step 4] 최종 모델 검증\n" + "="*50)
    if not os.path.exists(SAVE_PATH): return
    model = ASTForAudioClassification.from_pretrained(SAVE_PATH).to(device)
    trainer = Trainer(model=model, compute_metrics=compute_metrics)
    results = trainer.predict(test_dataset)
    _print_metrics(results.label_ids, np.argmax(results.predictions, axis=-1), "최종")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", type=str, default="all", choices=["baseline", "train", "test", "all"])
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch_size", type=int, default=DEFAULT_BATCH_SIZE, help=f"GPU batch size (default: {DEFAULT_BATCH_SIZE})")
    parser.add_argument("--grad_accum", type=int, default=DEFAULT_GRAD_ACCUM, help=f"Gradient accumulation steps (default: {DEFAULT_GRAD_ACCUM})")
    parser.add_argument("--lr", type=float, default=1e-4, help="Learning rate (추천: 1e-4 초기, 3e-5 fine-tune)")
    parser.add_argument("--freeze_encoder", action="store_true", help="Freeze encoder for stable training")
    args = parser.parse_args()

    print(f"\n🚀 Audio Training Script Started")
    print(f"   Environment: {'RunPod' if os.path.exists(RUNPOD_DATA_PATH) else 'Local'}")
    print(f"   Data Root: {DATA_ROOT}")
    print(f"   Train Dir: {TRAIN_DATA_DIR}")
    print(f"   Test Dir: {TEST_DATA_DIR}")
    print(f"   Batch Size: {args.batch_size}")
    print(f"   Grad Accum: {args.grad_accum}")
    print(f"   Mode: {args.mode}")

    train_ds, eval_ds, test_ds = prepare_data(mode=args.mode)

    if args.mode == "baseline" and test_ds:
        evaluate_baseline(test_ds)
    elif args.mode == "train" and train_ds:
        train_model(train_ds, eval_ds, args)
    elif args.mode == "test" and test_ds:
        evaluate_final(test_ds)
    elif args.mode == "all":
        if test_ds: evaluate_baseline(test_ds)
        if train_ds: train_model(train_ds, eval_ds, args)
        if test_ds: evaluate_final(test_ds)

    print("\n✅ 모든 과정 완료!")