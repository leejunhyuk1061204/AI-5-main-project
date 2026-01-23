# ai/scripts/train_audio.py
"""
AST 기계 소음 분류 모델 학습 도구 (Audio Trainer)

[역할]
1. 소리 기반 진단: 차량에서 발생하는 오디오 데이터를 분석하여 기계적 고장(노킹, 실화 등)을 분류하는 AST 모델을 학습합니다.
2. 전처리 자동화: 오디오 파일을 스펙트로그램 특징(Feature)으로 자동 변환하며, Windows 환경에서의 librosa 로딩 이슈를 해결했습니다.
3. 성능 리포트: 학습 전(Baseline)과 학습 후(Final)의 정확도를 비교하여 모델의 개선 정도를 측정합니다.

[사용법]
python ai/scripts/train_audio.py --mode all --epochs 10
"""
import argparse
import os
import torch
import numpy as np
import boto3
import evaluate
from transformers import ASTForAudioClassification, ASTFeatureExtractor, Trainer, TrainingArguments
from datasets import Dataset, Audio
from sklearn.model_selection import train_test_split

# =============================================================================
# [설정] 경로 및 하이퍼파라미터
# =============================================================================
MODEL_NAME = "MIT/ast-finetuned-audioset-10-10-0.4593"
OUTPUT_DIR = "./ai/runs/audio_model"
SAVE_PATH = "./ai/weights/audio/best_ast_model"

LABEL_MAP = {
    "benz_normal": "Normal",
    "audi_normal": "Normal",
    "정상": "Normal",
    "Knocking": "Engine_Knocking",
    "Misfire": "Engine_Misfire",
    "Belt": "Belt_Issue",
    "소음": "Abnormal_Noise"
}

# =============================================================================
# 전역 변수 (데이터 준비 후 공유)
# =============================================================================
train_dataset = None
eval_dataset = None
test_dataset = None
label2id = None
id2label = None
labels = None
feature_extractor = None

# =============================================================================
# 1. 데이터 준비
# =============================================================================
def prepare_data():
    global train_dataset, eval_dataset, test_dataset, label2id, id2label, labels, feature_extractor
    
    print("\n" + "="*50)
    print("[Step 1] 데이터 준비 시작...")
    print("="*50)
    
    # =============================================================================
    # 로컬 데이터 폴더에서 불러오기
    # 폴더 구조:
    #   ai/data/ast/
    #     ├── normal/          (정상 엔진음: .wav 파일들)
    #     ├── knocking/        (노킹 소리)
    #     ├── belt/            (벨트 소리)
    #     ├── misfire/         (실화 소리)
    #     └── ... (추가 라벨 폴더)
    # =============================================================================
    LOCAL_DATA_DIR = "./ai/data/ast"
    
    if not os.path.exists(LOCAL_DATA_DIR):
        os.makedirs(LOCAL_DATA_DIR, exist_ok=True)
        print(f"[Warning] 데이터 폴더가 없어서 생성했습니다: {LOCAL_DATA_DIR}")
        print(f"         여기에 라벨별 하위 폴더(normal, knocking 등)를 만들고 오디오 파일을 넣어주세요.")
        print(f"         지원 형식: .wav, .mp3, .m4a, .ogg, .flac")
        return False
    
    DATA_SOURCE_PATHS = [LOCAL_DATA_DIR]
    
    # (선택적) S3 수집 데이터도 추가로 불러오기 - 나중에 Active Learning 때 사용
    try:
        s3_download_dir = "./ai/data/s3_audio"
        s3 = boto3.client('s3')
        bucket_name = os.getenv("S3_BUCKET_NAME", "car-sentry-data")
        
        objects = s3.list_objects_v2(Bucket=bucket_name, Prefix="dataset/audio/")
        if 'Contents' in objects:
            count = 0
            for obj in objects['Contents']:
                key = obj['Key']
                # 다양한 오디오 형식 지원
                audio_extensions = ('.wav', '.mp3', '.m4a', '.ogg', '.flac')
                if not key.lower().endswith(audio_extensions): continue
                
                rel_path = key.replace("dataset/audio/", "")
                local_path = os.path.join(s3_download_dir, rel_path)
                
                if not os.path.exists(local_path):
                    os.makedirs(os.path.dirname(local_path), exist_ok=True)
                    s3.download_file(bucket_name, key, local_path)
                    count += 1
            
            if count > 0:
                print(f"[Info] S3에서 {count}개의 신규 데이터를 다운로드했습니다.")
            DATA_SOURCE_PATHS.append(s3_download_dir)
            
    except Exception as e:
        print(f"[Info] S3 연결 건너뜀 (로컬 데이터만 사용): {e}")

    # 데이터 수집
    data_list = []
    for base_path in DATA_SOURCE_PATHS:
        if not os.path.exists(base_path):
            continue
        for root, dirs, files in os.walk(base_path):
            for file in files:
                # 다양한 오디오 형식 지원
                audio_extensions = ('.wav', '.mp3', '.m4a', '.ogg', '.flac')
                if file.lower().endswith(audio_extensions):
                    folder_name = os.path.basename(root)
                    label = LABEL_MAP.get(folder_name, folder_name)
                    full_path = os.path.join(root, file)
                    data_list.append({"audio": full_path, "label": label})
    
    print(f"[Info] 총 {len(data_list)}개의 오디오 파일 발견")
    
    if len(data_list) == 0:
        print("[Error] 데이터가 없습니다.")
        return False
    
    # 라벨 인코딩
    labels = list(set([x['label'] for x in data_list]))
    label2id = {label: i for i, label in enumerate(labels)}
    id2label = {i: label for i, label in enumerate(labels)}
    print(f"[Info] 감지된 라벨({len(labels)}개): {labels}")
    
    # 7:2:1 분할
    train_val, test_data = train_test_split(
        data_list, test_size=0.2, stratify=[x['label'] for x in data_list], random_state=42
    )
    train_data, val_data = train_test_split(
        train_val, test_size=0.125, stratify=[x['label'] for x in train_val], random_state=42
    )
    
    print(f"[Info] 데이터 분할: Train={len(train_data)}, Valid={len(val_data)}, Test={len(test_data)}")
    
    # Feature Extractor 로드
    feature_extractor = ASTFeatureExtractor.from_pretrained(MODEL_NAME)
    
    # librosa로 직접 오디오 로딩 (torchcodec 우회!)
    import librosa
    
    def load_audio_with_librosa(file_path, target_sr=16000):
        """librosa로 오디오 로드 (Windows 호환)"""
        try:
            audio_array, _ = librosa.load(file_path, sr=target_sr)
            return audio_array
        except Exception as e:
            print(f"[Warning] 오디오 로드 실패: {file_path} - {e}")
            return None
    
    def preprocess_batch(data_list, desc="Processing"):
        """배치 전처리 (librosa 사용)"""
        processed_data = []
        
        for item in data_list:
            audio_array = load_audio_with_librosa(item["audio"])
            if audio_array is None:
                continue
            
            # Feature extraction
            inputs = feature_extractor(
                audio_array, 
                sampling_rate=16000, 
                return_tensors="pt", 
                padding="max_length"
            )
            
            processed_data.append({
                "input_values": inputs["input_values"].squeeze(0).numpy(),
                "labels": label2id[item["label"]]
            })
        
        return processed_data
    
    # Dataset 생성 및 전처리
    print("[Info] 데이터 전처리 중 (librosa 사용)...")
    
    train_processed = preprocess_batch(train_data, "Train")
    val_processed = preprocess_batch(val_data, "Valid")
    test_processed = preprocess_batch(test_data, "Test")
    
    print(f"[Info] 전처리 완료: Train={len(train_processed)}, Valid={len(val_processed)}, Test={len(test_processed)}")
    
    # HuggingFace Dataset으로 변환
    train_dataset = Dataset.from_list(train_processed)
    eval_dataset = Dataset.from_list(val_processed)
    test_dataset = Dataset.from_list(test_processed)
    
    # Tensor 형식 설정
    train_dataset.set_format(type="torch", columns=["input_values", "labels"])
    eval_dataset.set_format(type="torch", columns=["input_values", "labels"])
    test_dataset.set_format(type="torch", columns=["input_values", "labels"])
    
    print("[✓] 데이터 준비 완료!")
    return True

# =============================================================================
# 2. 초기 모델 정밀도 측정 (Baseline)
# =============================================================================
def evaluate_baseline():
    print("\n" + "="*50)
    print("[Step 2] 초기 모델(Baseline) 정밀도 측정...")
    print("="*50)
    
    if test_dataset is None:
        print("[Error] 먼저 데이터를 준비해주세요 (--mode all 또는 prepare_data 호출)")
        return
    
    # 사전학습 모델 로드 (Fine-tuning 전)
    model = ASTForAudioClassification.from_pretrained(
        MODEL_NAME,
        num_labels=len(labels),
        label2id=label2id,
        id2label=id2label,
        ignore_mismatched_sizes=True
    )
    
    accuracy_metric = evaluate.load("accuracy")
    
    def compute_metrics(eval_pred):
        predictions, labels_arr = eval_pred
        predictions = np.argmax(predictions, axis=1)
        return accuracy_metric.compute(predictions=predictions, references=labels_arr)
    
    training_args = TrainingArguments(
        output_dir="./ai/runs/baseline_eval",
        per_device_eval_batch_size=8,
        push_to_hub=False,
    )
    
    trainer = Trainer(
        model=model,
        args=training_args,
        eval_dataset=test_dataset,
        compute_metrics=compute_metrics,
    )
    
    metrics = trainer.evaluate()
    
    print("\n" + "="*40)
    print(f"🎯 초기 모델 정확도(Baseline): {metrics['eval_accuracy']:.4f}")
    print("="*40 + "\n")
    
    return metrics['eval_accuracy']

# =============================================================================
# 3. 모델 학습
# =============================================================================
def train_model(epochs=10):
    print("\n" + "="*50)
    print(f"[Step 3] 모델 학습 시작 ({epochs} epochs)...")
    print("="*50)
    
    if train_dataset is None:
        print("[Error] 먼저 데이터를 준비해주세요")
        return None
    
    model = ASTForAudioClassification.from_pretrained(
        MODEL_NAME,
        num_labels=len(labels),
        label2id=label2id,
        id2label=id2label,
        ignore_mismatched_sizes=True
    )
    
    accuracy_metric = evaluate.load("accuracy")
    
    def compute_metrics(eval_pred):
        predictions, labels_arr = eval_pred
        predictions = np.argmax(predictions, axis=1)
        return accuracy_metric.compute(predictions=predictions, references=labels_arr)
    
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        per_device_train_batch_size=8,
        num_train_epochs=epochs,
        learning_rate=3e-5,
        logging_dir='./logs',
        eval_strategy="epoch",  # 최신 버전 호환
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="accuracy",
        push_to_hub=False,
    )
    
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        compute_metrics=compute_metrics,
    )
    
    print("학습 시작...")
    trainer.train()
    
    # 모델 저장
    os.makedirs(SAVE_PATH, exist_ok=True)
    model.save_pretrained(SAVE_PATH)
    feature_extractor.save_pretrained(SAVE_PATH)
    print(f"[✓] 모델 저장 완료: {SAVE_PATH}")
    
    return trainer

# =============================================================================
# 4. 최종 모델 테스트
# =============================================================================
def evaluate_final():
    print("\n" + "="*50)
    print("[Step 4] 최종 모델 정밀도 측정...")
    print("="*50)
    
    if not os.path.exists(SAVE_PATH):
        print(f"[Error] 학습된 모델이 없습니다: {SAVE_PATH}")
        print("먼저 --mode train 으로 학습을 실행해주세요.")
        return
    
    if test_dataset is None:
        print("[Error] 먼저 데이터를 준비해주세요")
        return
    
    # 학습된 모델 로드
    model = ASTForAudioClassification.from_pretrained(SAVE_PATH)
    
    accuracy_metric = evaluate.load("accuracy")
    
    def compute_metrics(eval_pred):
        predictions, labels_arr = eval_pred
        predictions = np.argmax(predictions, axis=1)
        return accuracy_metric.compute(predictions=predictions, references=labels_arr)
    
    training_args = TrainingArguments(
        output_dir="./ai/runs/final_eval",
        per_device_eval_batch_size=8,
        push_to_hub=False,
    )
    
    trainer = Trainer(
        model=model,
        args=training_args,
        eval_dataset=test_dataset,
        compute_metrics=compute_metrics,
    )
    
    metrics = trainer.evaluate()
    
    print("\n" + "="*40)
    print(f"🎯 최종 모델 정확도(Final): {metrics['eval_accuracy']:.4f}")
    print("="*40 + "\n")
    
    return metrics['eval_accuracy']

# =============================================================================
# Main
# =============================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AST Audio Model Training Script")
    parser.add_argument("--mode", type=str, default="all",
                        choices=["baseline", "train", "test", "all"],
                        help="실행 모드: baseline(초기), train(학습), test(테스트), all(전체)")
    parser.add_argument("--epochs", type=int, default=10,
                        help="학습 에폭 수 (기본값: 10)")
    
    args = parser.parse_args()
    
    print(f"\n🚀 Audio Training Script 시작 (mode={args.mode}, epochs={args.epochs})")
    
    # 데이터 준비 (모든 모드에서 필요)
    if not prepare_data():
        exit(1)
    
    if args.mode == "baseline":
        evaluate_baseline()
    
    elif args.mode == "train":
        train_model(epochs=args.epochs)
    
    elif args.mode == "test":
        evaluate_final()
    
    elif args.mode == "all":
        baseline_acc = evaluate_baseline()
        train_model(epochs=args.epochs)
        final_acc = evaluate_final()
        
        print("\n" + "="*50)
        print("📊 정확도 비교")
        print("="*50)
        print(f"   초기 모델(Baseline): {baseline_acc:.4f}")
        print(f"   최종 모델(Final):    {final_acc:.4f}")
        print(f"   향상도:              +{(final_acc - baseline_acc)*100:.2f}%")
        print("="*50 + "\n")
    
    print("✅ 완료!")