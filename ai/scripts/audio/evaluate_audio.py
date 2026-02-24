# ai/scripts/evaluate_audio.py
"""
[파일 용도] AST 오디오 모델 성능 평가 도구 (Audio Evaluator)
학습 완료된 AST 모델의 체크포인트(.pt)를 로드하여 테스트 데이터셋에 대한 정확도(Accuracy) 및 성능 지표를 측정합니다.
외부 데이터 테스트 및 추가적인 검증 목적으로 사용됩니다.

python ai/scripts/evaluate_audio.py

[주요 설정]
- EVAL_DATA_PATHS: 평가하고 싶은 오디오 데이터가 있는 폴더 목록
- MODEL_PATH: 평가 대상 모델 가중치 경로 (ai/weights/audio/best_ast_model)
"""
import os
import torch
import numpy as np
import evaluate
from transformers import ASTForAudioClassification, ASTFeatureExtractor, Trainer, TrainingArguments
from datasets import Dataset, Audio

# -----------------------------------------------------------------------------
# [설정] 평가할 데이터 소스 경로
# -----------------------------------------------------------------------------
EVAL_DATA_PATHS = [
    "./ai/data/ast/test"  # 기본 테스트셋 경로로 수정
]

MODEL_PATH = "./ai/weights/audio/best_ast_model"

# [설정] 라벨 맵핑 규칙 (학습 때와 동일하게 맞춰야 함)
LABEL_MAP = {
    "benz_normal": "Normal",
    "audi_normal": "Normal",
    "정상": "Normal",
    
    "Knocking": "Engine_Knocking",
    "Misfire": "Engine_Misfire",
    "Belt": "Belt_Issue",
    "소음": "Abnormal_Noise"
}

# -----------------------------------------------------------------------------
# 1. 모델 및 설정 로드
# -----------------------------------------------------------------------------
if not os.path.exists(MODEL_PATH):
    print(f"[Error] 학습된 모델이 없습니다: {MODEL_PATH}")
    print("먼저 train_audio.py를 실행해서 모델을 학습시켜주세요.")
    exit()

print(f"[Info] 모델을 로드합니다: {MODEL_PATH}")
model = ASTForAudioClassification.from_pretrained(MODEL_PATH)
feature_extractor = ASTFeatureExtractor.from_pretrained(MODEL_PATH)

# 라벨 정보 복원
id2label = model.config.id2label
label2id = model.config.label2id
print(f"[Info] 학습된 클래스 목록: {list(label2id.keys())}")

# -----------------------------------------------------------------------------
# 2. 데이터 로드 및 전처리
# -----------------------------------------------------------------------------
data_list = []

for base_path in EVAL_DATA_PATHS:
    if not os.path.exists(base_path):
        print(f"[Warning] 경로를 찾을 수 없습니다: {base_path}")
        continue
        
    for root, dirs, files in os.walk(base_path):
        for file in files:
            if file.lower().endswith('.wav'):
                folder_name = os.path.basename(root)
                label = LABEL_MAP.get(folder_name, folder_name)
                
                # 학습된 라벨에 없는 새로운 라벨이 들어오면 경고
                if label not in label2id:
                    print(f"[Warning] 학습되지 않은 라벨 발견: {label} (무시됨)")
                    continue
                    
                full_path = os.path.join(root, file)
                data_list.append({"audio": full_path, "label": label})

print(f"[Info] 총 {len(data_list)}개의 평가용 파일을 발견했습니다.")

if len(data_list) == 0:
    print("[Error] 평가할 데이터가 없습니다.")
    print("EVAL_DATA_PATHS 리스트에 올바른 경로를 추가해주세요.")
    exit()

# Dataset 생성
eval_ds = Dataset.from_list(data_list).cast_column("audio", Audio(sampling_rate=16000))

def preprocess_function(examples):
    audio_arrays = [x["array"] for x in examples["audio"]]
    inputs = feature_extractor(audio_arrays, sampling_rate=16000, return_tensors="pt", padding="max_length")
    return inputs

print("[Info] 데이터 전처리 중...")
eval_dataset = eval_ds.map(preprocess_function, batched=True)

# -----------------------------------------------------------------------------
# 3. 평가 실행
# -----------------------------------------------------------------------------
def compute_metrics(eval_pred):
    accuracy_metric = evaluate.load("accuracy")
    predictions, labels = eval_pred
    predictions = np.argmax(predictions, axis=1)
    return accuracy_metric.compute(predictions=predictions, references=labels)

# 평가용 Trainer 설정 (학습은 안 함)
training_args = TrainingArguments(
    output_dir="./Ai/runs/eval_temp",
    per_device_eval_batch_size=8,
    push_to_hub=False,
)

trainer = Trainer(
    model=model,
    args=training_args,
    eval_dataset=eval_dataset,
    compute_metrics=compute_metrics,
)

print("[Info] 평가 시작...")
metrics = trainer.evaluate()

print("\n" + "="*30)
print(f"🎯 최종 정확도(Accuracy): {metrics['eval_accuracy']:.4f}")
print("="*30 + "\n")
