import os
import torch
import numpy as np
from transformers import ASTForAudioClassification, ASTFeatureExtractor, Trainer, TrainingArguments
from datasets import Dataset, Audio
import evaluate

# -----------------------------------------------------------------------------
# [설정] 평가할 데이터 소스 경로
# -----------------------------------------------------------------------------
# 테스트하고 싶은 데이터가 있는 폴더 경로를 리스트에 추가하세요.
EVAL_DATA_PATHS = [
    # "C:/Users/301/Downloads/New_Test_Data" 
]

MODEL_PATH = "./Ai/weights/audio/best_ast_model"

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
