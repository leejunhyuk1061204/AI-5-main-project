# ai/scripts/audio/train_audio_2stage.py
"""
AST 2-Stage 분류 모델 학습 도구

[아키텍처]
Stage 1: normal vs abnormal (이진 분류)
Stage 2: abnormal → engine / brake / starter (다중 분류)

[장점]
- 소량 데이터에 강함
- 실제 서비스 구조와 일치 (먼저 이상 탐지 → 원인 분석)
- 각 Stage별 최적화 가능

[사용법]
python ai/scripts/audio/train_audio_2stage.py --mode all --epochs 10
"""
import argparse
import os
import sys
from pathlib import Path

# 프로젝트 루트를 PATH에 추가
project_root = str(Path(__file__).parents[3])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import torch
import numpy as np
import librosa
import concurrent.futures
from functools import partial
from collections import Counter
from transformers import ASTForAudioClassification, ASTFeatureExtractor, Trainer, TrainingArguments
from datasets import Dataset
from sklearn.metrics import precision_recall_fscore_support, accuracy_score, confusion_matrix
from sklearn.model_selection import train_test_split
from torch import nn

from ai.app.services.audio.audio_preprocessing import (
    trim_silence_rms, apply_bandpass_filter, calculate_speech_ratio,
    apply_speech_soft_masking, apply_spectral_gating
)

# =============================================================================
# [설정] 경로 및 하이퍼파라미터
# =============================================================================
MODEL_NAME = "MIT/ast-finetuned-audioset-10-10-0.4593"
OUTPUT_DIR_STAGE1 = "./ai/runs/audio_model_stage1"
OUTPUT_DIR_STAGE2 = "./ai/runs/audio_model_stage2"
SAVE_PATH_STAGE1 = "./ai/weights/audio/stage1_normal_vs_abnormal"
SAVE_PATH_STAGE2 = "./ai/weights/audio/stage2_fault_classifier"
GOLDEN_DATA_DIR = "./ai/data/audio/golden"

TRAIN_DATA_DIR = "./ai/data/audio/train"
TEST_DATA_DIR = "./ai/data/audio/test"

# Stage 1: 이진 분류
STAGE1_LABELS = ["normal", "abnormal"]
stage1_label2id = {label: i for i, label in enumerate(STAGE1_LABELS)}
stage1_id2label = {i: label for i, label in enumerate(STAGE1_LABELS)}

# Stage 2: 고장 유형 분류 (abnormal만 대상)
STAGE2_LABELS = ["engine", "brake", "starter"]
stage2_label2id = {label: i for i, label in enumerate(STAGE2_LABELS)}
stage2_id2label = {i: label for i, label in enumerate(STAGE2_LABELS)}

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
feature_extractor = None

# =============================================================================
# 1. 데이터 로딩 및 전처리
# =============================================================================
def load_data_from_dir(base_dir):
    """폴더 직접 스캔으로 데이터 로드"""
    data_list = []
    
    # normal 폴더
    normal_dir = os.path.join(base_dir, "normal")
    if os.path.exists(normal_dir):
        for f in os.listdir(normal_dir):
            if f.endswith('.wav'):
                data_list.append({
                    "audio": os.path.join(normal_dir, f), 
                    "label": "normal",
                    "stage1_label": "normal",
                    "stage2_label": None
                })
    
    # abnormal 폴더
    abnormal_dir = os.path.join(base_dir, "abnormal")
    if os.path.exists(abnormal_dir):
        for cls in ["engine", "brake", "starter"]:
            cls_dir = os.path.join(abnormal_dir, cls)
            if not os.path.exists(cls_dir):
                continue
            for f in os.listdir(cls_dir):
                if f.endswith(".wav"):
                    data_list.append({
                        "audio": os.path.join(cls_dir, f),
                        "label": cls,
                        "stage1_label": "abnormal",
                        "stage2_label": cls
                    })
    
    return data_list

def process_single_audio(item):
    """단일 오디오 전처리"""
    try:
        y, sr = librosa.load(item["audio"], sr=16000)
        label = item.get("label", "normal")
        
        # 전처리 파이프라인
        y = trim_silence_rms(y, sr, top_db=50) # top_db=50: 무음 제거 기준 완화
        y = apply_bandpass_filter(y, sr)
        
        speech_ratio, vad_mask = calculate_speech_ratio(y, sr)
        # ✅ VAD 기준 완화: 0.2 -> 0.05
        if label == "normal" and speech_ratio > 0.05:
            y = apply_speech_soft_masking(y, sr, vad_mask)
        
        if label == "normal":
            y = apply_spectral_gating(y, sr, min_gain=0.2)
        else:
            y = apply_spectral_gating(y, sr, min_gain=0.5)
        
        # RMS Normalization
        target_rms = 0.1
        current_rms = np.sqrt(np.mean(y**2)) + 1e-8
        y = y * (target_rms / current_rms)
        
        return {"audio_array": y, **item}
    except Exception as e:
        return {"error": str(e), "path": item["audio"]}

def prepare_datasets(data_list, label_key, label2id, desc="Data"):
    """병렬 전처리로 Dataset 준비"""
    global feature_extractor
    if feature_extractor is None:
        feature_extractor = ASTFeatureExtractor.from_pretrained(MODEL_NAME)
    
    print(f"[Info] {desc} 전처리 중 (총 {len(data_list)}개)...")
    results = []
    
    num_workers = min(os.cpu_count(), 4)
    with concurrent.futures.ProcessPoolExecutor(max_workers=num_workers) as executor:
        futures = {executor.submit(process_single_audio, item): i for i, item in enumerate(data_list)}
        
        completed = 0
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if "error" in res:
                print(f"[Warning] 처리 실패: {res.get('path', 'unknown')}")
            elif res.get(label_key) is not None:
                input_values = feature_extractor(
                    res["audio_array"], sampling_rate=16000,
                    return_tensors="pt", padding="longest", truncation=True, max_length=1024
                )["input_values"].squeeze(0).numpy()
                
                results.append({
                    "input_values": input_values,
                    "labels": label2id[res[label_key]]
                })
            
            completed += 1
            if completed % 100 == 0:
                print(f"  > {desc}: {completed}/{len(data_list)} ({completed/len(data_list)*100:.1f}%)")
    
    dataset = Dataset.from_list(results)
    dataset.set_format(type="torch", columns=["input_values", "labels"])
    return dataset

# =============================================================================
# 2. Stage 1: Normal vs Abnormal
# =============================================================================
def train_stage1(train_data, test_data, epochs=10, batch_size=4, grad_accum=4):
    print("\n" + "="*60)
    print(f"[Stage 1] Normal vs Abnormal 이진 분류 학습 (Batch: {batch_size}, Accum: {grad_accum})")
    print("="*60)
    
    # 데이터 준비
    t_data, v_data = train_test_split(
        train_data, test_size=0.1, 
        stratify=[x['stage1_label'] for x in train_data], random_state=42
    )
    
    train_ds = prepare_datasets(t_data, "stage1_label", stage1_label2id, "Train(S1)")
    eval_ds = prepare_datasets(v_data, "stage1_label", stage1_label2id, "Valid(S1)")
    test_ds = prepare_datasets(test_data, "stage1_label", stage1_label2id, "Test(S1)")
    
    # 클래스 가중치
    labels = [x['stage1_label'] for x in train_data]
    counts = [labels.count(l) for l in STAGE1_LABELS]
    weights = torch.tensor([sum(counts) / (len(STAGE1_LABELS) * c + 1e-8) for c in counts], dtype=torch.float)
    print(f"[Info] Stage1 Class Distribution: {dict(zip(STAGE1_LABELS, counts))}")
    
    # 모델
    model = ASTForAudioClassification.from_pretrained(
        MODEL_NAME, num_labels=2,
        label2id=stage1_label2id, id2label=stage1_id2label,
        ignore_mismatched_sizes=True
    ).to(device)
    
    # Trainer
    class WeightedTrainer(Trainer):
        def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
            labels = inputs.get("labels")
            outputs = model(**inputs)
            loss_fct = nn.CrossEntropyLoss(weight=weights.to(model.device))
            loss = loss_fct(outputs.logits.view(-1, 2), labels.view(-1))
            return (loss, outputs) if return_outputs else loss
    
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR_STAGE1,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=grad_accum,
        num_train_epochs=epochs,
        learning_rate=3e-5,
        logging_steps=10,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="recall",
        greater_is_better=True,
        fp16=torch.cuda.is_available(),
    )
    
    def compute_metrics(eval_pred):
        preds = np.argmax(eval_pred.predictions, axis=-1)
        labels = eval_pred.label_ids
        precision, recall, f1, _ = precision_recall_fscore_support(labels, preds, average='binary', pos_label=1)
        acc = accuracy_score(labels, preds)
        return {"accuracy": acc, "f1": f1, "precision": precision, "recall": recall}
    
    trainer = WeightedTrainer(
        model=model, args=training_args,
        train_dataset=train_ds, eval_dataset=eval_ds,
        compute_metrics=compute_metrics,
    )
    
    trainer.train()
    
    # 저장 및 평가
    os.makedirs(SAVE_PATH_STAGE1, exist_ok=True)
    model.save_pretrained(SAVE_PATH_STAGE1)
    feature_extractor.save_pretrained(SAVE_PATH_STAGE1)
    
    # Test 평가
    results = trainer.predict(test_ds)
    preds = np.argmax(results.predictions, axis=-1)
    labels = results.label_ids
    
    print(f"\n📊 Stage 1 Test 결과:")
    print(f" - Accuracy: {accuracy_score(labels, preds):.4f}")
    print(f" - Recall (abnormal): {precision_recall_fscore_support(labels, preds, average='binary', pos_label=1)[1]:.4f}")
    
    cm = confusion_matrix(labels, preds)
    print(f"\n🖼️ Confusion Matrix:")
    print(f"   Labels: {STAGE1_LABELS}")
    for i, row in enumerate(cm):
        print(f"   {STAGE1_LABELS[i]:>8}: {list(row)}")
    
    return model

# =============================================================================
# 3. Stage 2: Abnormal → Fault Type
# =============================================================================
def train_stage2(train_data, test_data, epochs=10, batch_size=4, grad_accum=4):
    print("\n" + "="*60)
    print(f"[Stage 2] Abnormal → Engine/Brake/Starter 분류 학습 (Batch: {batch_size}, Accum: {grad_accum})")
    print("="*60)
    
    # abnormal 데이터만 필터링
    train_abnormal = [x for x in train_data if x['stage1_label'] == 'abnormal']
    test_abnormal = [x for x in test_data if x['stage1_label'] == 'abnormal']
    
    if not train_abnormal:
        print("[Error] Abnormal 학습 데이터가 없습니다!")
        return None
    
    t_data, v_data = train_test_split(
        train_abnormal, test_size=0.1,
        stratify=[x['stage2_label'] for x in train_abnormal], random_state=42
    )
    
    train_ds = prepare_datasets(t_data, "stage2_label", stage2_label2id, "Train(S2)")
    eval_ds = prepare_datasets(v_data, "stage2_label", stage2_label2id, "Valid(S2)")
    test_ds = prepare_datasets(test_abnormal, "stage2_label", stage2_label2id, "Test(S2)")
    
    # 클래스 가중치
    labels = [x['stage2_label'] for x in train_abnormal]
    counts = [labels.count(l) for l in STAGE2_LABELS]
    weights = torch.tensor([sum(counts) / (len(STAGE2_LABELS) * c + 1e-8) for c in counts], dtype=torch.float)
    print(f"[Info] Stage2 Class Distribution: {dict(zip(STAGE2_LABELS, counts))}")
    
    # 모델
    model = ASTForAudioClassification.from_pretrained(
        MODEL_NAME, num_labels=3,
        label2id=stage2_label2id, id2label=stage2_id2label,
        ignore_mismatched_sizes=True
    ).to(device)
    
    class WeightedTrainer(Trainer):
        def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
            labels = inputs.get("labels")
            outputs = model(**inputs)
            loss_fct = nn.CrossEntropyLoss(weight=weights.to(model.device))
            loss = loss_fct(outputs.logits.view(-1, 3), labels.view(-1))
            return (loss, outputs) if return_outputs else loss
    
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR_STAGE2,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=grad_accum,
        num_train_epochs=epochs,
        learning_rate=3e-5,
        logging_steps=10,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        greater_is_better=True,
        fp16=torch.cuda.is_available(),
    )
    
    def compute_metrics(eval_pred):
        preds = np.argmax(eval_pred.predictions, axis=-1)
        labels = eval_pred.label_ids
        precision, recall, f1, _ = precision_recall_fscore_support(labels, preds, average='macro')
        acc = accuracy_score(labels, preds)
        return {"accuracy": acc, "f1": f1, "precision": precision, "recall": recall}
    
    trainer = WeightedTrainer(
        model=model, args=training_args,
        train_dataset=train_ds, eval_dataset=eval_ds,
        compute_metrics=compute_metrics,
    )
    
    trainer.train()
    
    # 저장 및 평가
    os.makedirs(SAVE_PATH_STAGE2, exist_ok=True)
    model.save_pretrained(SAVE_PATH_STAGE2)
    feature_extractor.save_pretrained(SAVE_PATH_STAGE2)
    
    results = trainer.predict(test_ds)
    preds = np.argmax(results.predictions, axis=-1)
    labels = results.label_ids
    
    print(f"\n📊 Stage 2 Test 결과:")
    p, r, f1, _ = precision_recall_fscore_support(labels, preds, average='macro')
    print(f" - Accuracy: {accuracy_score(labels, preds):.4f}")
    print(f" - Macro F1: {f1:.4f}")
    
    cm = confusion_matrix(labels, preds)
    print(f"\n🖼️ Confusion Matrix:")
    print(f"   Labels: {STAGE2_LABELS}")
    for i, row in enumerate(cm):
        print(f"   {STAGE2_LABELS[i]:>8}: {list(row)}")
    
    return model

# =============================================================================
# 4. Baseline 평가 (Fine-tuning 전 원본 모델)
# =============================================================================
def evaluate_baseline(test_data):
    """
    Pre-trained AST 모델의 Baseline 성능 평가
    Fine-tuning 전 기준점 확인용
    """
    print("\n" + "="*60)
    print("[Baseline] Pre-trained AST 모델 평가 (2-Stage 관점)")
    print("="*60)
    print("""
[Baseline 정의]
1. Model: MIT/ast-finetuned-audioset (Pre-trained, No Fine-tuning)
2. Data: Test set only
3. Note: AudioSet에 engine/brake/starter가 없어 성능이 낮을 수 있음
""")
    
    global feature_extractor
    if feature_extractor is None:
        feature_extractor = ASTFeatureExtractor.from_pretrained(MODEL_NAME)
    
    # Stage 1 Baseline (normal vs abnormal)
    print("\n--- Stage 1: Normal vs Abnormal ---")
    test_ds1 = prepare_datasets(test_data, "stage1_label", stage1_label2id, "Test(S1-Base)")
    
    model1 = ASTForAudioClassification.from_pretrained(
        MODEL_NAME, num_labels=2,
        label2id=stage1_label2id, id2label=stage1_id2label,
        ignore_mismatched_sizes=True
    ).to(device)
    
    trainer = Trainer(model=model1)
    results = trainer.predict(test_ds1)
    preds = np.argmax(results.predictions, axis=-1)
    labels = results.label_ids
    
    print(f"\n📊 Stage 1 Baseline 결과:")
    print(f" - Accuracy: {accuracy_score(labels, preds):.4f}")
    p, r, f1, _ = precision_recall_fscore_support(labels, preds, average='binary', pos_label=1)
    print(f" - Abnormal Recall: {r:.4f}")
    print(f" - Abnormal F1: {f1:.4f}")
    
    cm = confusion_matrix(labels, preds)
    print(f"\n🖼️ Confusion Matrix:")
    print(f"   Labels: {STAGE1_LABELS}")
    for i, row in enumerate(cm):
        print(f"   {STAGE1_LABELS[i]:>8}: {list(row)}")
    
    # Stage 2 Baseline (abnormal 내 분류)
    abnormal_test = [x for x in test_data if x['stage1_label'] == 'abnormal']
    if abnormal_test:
        print("\n--- Stage 2: Abnormal → Fault Type ---")
        test_ds2 = prepare_datasets(abnormal_test, "stage2_label", stage2_label2id, "Test(S2-Base)")
        
        model2 = ASTForAudioClassification.from_pretrained(
            MODEL_NAME, num_labels=3,
            label2id=stage2_label2id, id2label=stage2_id2label,
            ignore_mismatched_sizes=True
        ).to(device)
        
        trainer = Trainer(model=model2)
        results = trainer.predict(test_ds2)
        preds = np.argmax(results.predictions, axis=-1)
        labels = results.label_ids
        
        print(f"\n📊 Stage 2 Baseline 결과:")
        print(f" - Accuracy: {accuracy_score(labels, preds):.4f}")
        p, r, f1, _ = precision_recall_fscore_support(labels, preds, average='macro')
        print(f" - Macro F1: {f1:.4f}")
        print(f" - Macro Recall: {r:.4f}")
        
        cm = confusion_matrix(labels, preds)
        print(f"\n🖼️ Confusion Matrix:")
        print(f"   Labels: {STAGE2_LABELS}")
        for i, row in enumerate(cm):
            print(f"   {STAGE2_LABELS[i]:>8}: {list(row)}")
    
    print("\n[⚠️ 참고] Baseline이 낮으면 정상입니다. Fine-tuning 후 성능이 올라갑니다.")

# =============================================================================
# 5. Golden Set 평가
# =============================================================================
def evaluate_golden():
    """Golden Set으로 필수 정확도 검증"""
    print("\n" + "="*60)
    print("[Golden Set] 필수 샘플 검증")
    print("="*60)
    
    if not os.path.exists(GOLDEN_DATA_DIR):
        print(f"[Warning] Golden Set 폴더가 없습니다: {GOLDEN_DATA_DIR}")
        print("[Info] ai/data/audio/golden/ 폴더를 만들고 대표 샘플을 넣어주세요.")
        return
    
    golden_data = load_data_from_dir(GOLDEN_DATA_DIR)
    if not golden_data:
        print("[Warning] Golden Set이 비어있습니다.")
        return
    
    print(f"[Info] Golden Set 샘플 수: {len(golden_data)}")
    print(f"[Info] 분포: {dict(Counter([x['label'] for x in golden_data]))}")
    
    # Stage 1 모델 로드
    if os.path.exists(SAVE_PATH_STAGE1):
        model1 = ASTForAudioClassification.from_pretrained(SAVE_PATH_STAGE1).to(device)
        golden_ds1 = prepare_datasets(golden_data, "stage1_label", stage1_label2id, "Golden(S1)")
        
        model1.eval()
        trainer = Trainer(model=model1)
        results = trainer.predict(golden_ds1)
        preds = np.argmax(results.predictions, axis=-1)
        labels = results.label_ids
        
        correct = sum(p == l for p, l in zip(preds, labels))
        print(f"\n🏆 Stage 1 Golden Set: {correct}/{len(labels)} ({100*correct/len(labels):.1f}%)")
        
        if correct == len(labels):
            print("✅ Stage 1 PASS - 모든 Golden 샘플 정답!")
        else:
            print("❌ Stage 1 FAIL - 일부 샘플 오답")
            for i, (p, l) in enumerate(zip(preds, labels)):
                if p != l:
                    print(f"   - {golden_data[i]['audio']}: 예측={STAGE1_LABELS[p]}, 정답={STAGE1_LABELS[l]}")
    
    # Stage 2 모델 로드 (abnormal만)
    if os.path.exists(SAVE_PATH_STAGE2):
        abnormal_golden = [x for x in golden_data if x['stage1_label'] == 'abnormal']
        if abnormal_golden:
            model2 = ASTForAudioClassification.from_pretrained(SAVE_PATH_STAGE2).to(device)
            golden_ds2 = prepare_datasets(abnormal_golden, "stage2_label", stage2_label2id, "Golden(S2)")
            
            trainer = Trainer(model=model2)
            results = trainer.predict(golden_ds2)
            preds = np.argmax(results.predictions, axis=-1)
            labels = results.label_ids
            
            correct = sum(p == l for p, l in zip(preds, labels))
            print(f"\n🏆 Stage 2 Golden Set: {correct}/{len(labels)} ({100*correct/len(labels):.1f}%)")
            
            if correct == len(labels):
                print("✅ Stage 2 PASS - 모든 Abnormal Golden 샘플 정답!")
            else:
                print("❌ Stage 2 FAIL")

# =============================================================================
# Main
# =============================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", type=str, default="all", choices=["baseline", "stage1", "stage2", "golden", "all"])
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch_size", type=int, default=4, help="Batch size for training")
    parser.add_argument("--grad_accum", type=int, default=4, help="Gradient accumulation steps")
    args = parser.parse_args()
    
    print(f"[Info] 사용 디바이스: {device}")
    
    # 데이터 로드
    train_data = load_data_from_dir(TRAIN_DATA_DIR)
    test_data = load_data_from_dir(TEST_DATA_DIR)
    
    print(f"[Sanity Check] Train: {dict(Counter([x['label'] for x in train_data]))}")
    print(f"[Sanity Check] Test: {dict(Counter([x['label'] for x in test_data]))}")
    
    if args.mode == "baseline":
        evaluate_baseline(test_data)
    elif args.mode == "stage1":
        train_stage1(train_data, test_data, args.epochs, args.batch_size, args.grad_accum)
    elif args.mode == "stage2":
        train_stage2(train_data, test_data, args.epochs, args.batch_size, args.grad_accum)
    elif args.mode == "golden":
        evaluate_golden()
    elif args.mode == "all":
        train_stage1(train_data, test_data, args.epochs, args.batch_size, args.grad_accum)
        train_stage2(train_data, test_data, args.epochs, args.batch_size, args.grad_accum)
        evaluate_golden()
    
    print("\n✅ 완료!")
