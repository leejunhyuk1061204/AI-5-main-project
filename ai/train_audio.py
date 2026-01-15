import kagglehub
import os
import torch
import librosa
import numpy as np
from transformers import ASTConfig, ASTForAudioClassification, ASTFeatureExtractor, Trainer, TrainingArguments
from datasets import Dataset, Audio
from sklearn.model_selection import train_test_split
import evaluate

# -----------------------------------------------------------------------------
# [설정] 데이터 소스 경로 리스트 (확장성: 여기에 새 경로만 추가하면 됨)
# -----------------------------------------------------------------------------
DATA_SOURCE_PATHS = []

# 1. Kaggle 데이터셋 다운로드 (자동 추가)
try:
    kaggle_path = kagglehub.dataset_download("janboubiabderrahim/vehicle-sounds-dataset")
    print(f"[Info] Kaggle 데이터셋 다운로드 완료: {kaggle_path}")
    DATA_SOURCE_PATHS.append(kaggle_path)
except Exception as e:
    print(f"[Warning] Kaggle 다운로드 실패 (인터넷 연결 확인): {e}")

# 2. 로컬 데이터 폴더 (예시: 필요하면 주석 해제 후 수정)
# DATA_SOURCE_PATHS.append("C:/Users/301/Documents/MyCarSounds")

print(f"[Info] 총 {len(DATA_SOURCE_PATHS)}개의 데이터 소스를 탐색합니다.")

# -----------------------------------------------------------------------------
# 3. 전처리 설정 (16kHz 리샘플링)
# -----------------------------------------------------------------------------
feature_extractor = ASTFeatureExtractor.from_pretrained("MIT/ast-finetuned-audioset-10-10-0.4593")

def preprocess_function(examples):
    audio_arrays = [x["array"] for x in examples["audio"]]
    inputs = feature_extractor(audio_arrays, sampling_rate=16000, return_tensors="pt", padding="max_length")
    return inputs

def compute_metrics(eval_pred):
    accuracy_metric = evaluate.load("accuracy")
    predictions, labels = eval_pred
    predictions = np.argmax(predictions, axis=1)
    return accuracy_metric.compute(predictions=predictions, references=labels)

# -----------------------------------------------------------------------------
# 4. 데이터 로드 (Recursive os.walk)
# -----------------------------------------------------------------------------
# [설정] 라벨 맵핑 규칙 (폴더명 -> 학습할 라벨명)
# 이 딕셔너리에 없는 폴더명은 그냥 폴더명 그대로 라벨로 사용됨
LABEL_MAP = {
    # 예시: "폴더이름": "통합라벨"
    "benz_normal": "Normal",
    "audi_normal": "Normal",
    "정상": "Normal",
    
    "Knocking": "Engine_Knocking",
    "Misfire": "Engine_Misfire",
    "Belt": "Belt_Issue",
    "소음": "Abnormal_Noise"
}

data_list = []

for base_path in DATA_SOURCE_PATHS:
    if not os.path.exists(base_path):
        continue
        
    for root, dirs, files in os.walk(base_path):
        for file in files:
            if file.lower().endswith('.wav'):
                # 1. 파일이 들어있는 '바로 위 폴더 이름' 추출
                folder_name = os.path.basename(root)
                
                # 2. 라벨 맵핑 적용 (없으면 폴더명 그대로 사용)
                label = LABEL_MAP.get(folder_name, folder_name)
                
                full_path = os.path.join(root, file)
                data_list.append({"audio": full_path, "label": label})

print(f"[Info] 총 {len(data_list)}개의 오디오 파일을 발견했습니다.")

if len(data_list) == 0:
    print("[Error] 데이터가 없습니다. 스크립트를 종료합니다.")
    exit()

# -----------------------------------------------------------------------------
# 5. 데이터 분할 (7:2:1 -> Train:Test:Valid)
# -----------------------------------------------------------------------------
# 라벨 인코딩 준비
labels = list(set([x['label'] for x in data_list]))
label2id = {label: i for i, label in enumerate(labels)}
id2label = {i: label for i, label in enumerate(labels)}

print(f"[Info] 감지된 라벨({len(labels)}개): {labels}")

# 1단계: 전체를 Train(80%) + Rest(20%)로 분할 (Test용 확보)
train_val, test_data = train_test_split(
    data_list, test_size=0.2, stratify=[x['label'] for x in data_list], random_state=42
)

# 2단계: Train(80%)를 다시 Train(70%) + Valid(10%)로 분할
# 남은 80% 중에서 1/8(12.5%)을 떼어내면 전체의 10%가 됨
train_data, val_data = train_test_split(
    train_val, test_size=0.125, stratify=[x['label'] for x in train_val], random_state=42
)

print(f"[Info] 데이터 분할 완료:")
print(f" - 학습용(Train 70%): {len(train_data)}개")
print(f" - 검증용(Valid 10%): {len(val_data)}개 (학습 중 성능 체크)")
print(f" - 평가용(Test  20%): {len(test_data)}개 (최종 채점)")

# Dataset 객체 생성
train_ds = Dataset.from_list(train_data).cast_column("audio", Audio(sampling_rate=16000))
val_ds   = Dataset.from_list(val_data).cast_column("audio", Audio(sampling_rate=16000))
test_ds  = Dataset.from_list(test_data).cast_column("audio", Audio(sampling_rate=16000))

# 전처리 적용
print("[Info] 데이터 전처리(Audio -> Spectrogram) 시작...")
train_dataset = train_ds.map(preprocess_function, batched=True)
eval_dataset  = val_ds.map(preprocess_function, batched=True)
test_dataset  = test_ds.map(preprocess_function, batched=True)

# -----------------------------------------------------------------------------
# 6. 모델 학습
# -----------------------------------------------------------------------------
model = ASTForAudioClassification.from_pretrained(
    "MIT/ast-finetuned-audioset-10-10-0.4593",
    num_labels=len(labels),
    label2id=label2id,
    id2label=id2label,
    ignore_mismatched_sizes=True
)

training_args = TrainingArguments(
    output_dir="./Ai/runs/audio_model",
    per_device_train_batch_size=8,
    num_train_epochs=10,
    learning_rate=3e-5,
    logging_dir='./logs',
    evaluation_strategy="epoch", # 매 epoch마다 검증(Valid) 수행
    save_strategy="epoch",
    load_best_model_at_end=True, # Valid 점수 가장 좋은 모델 저장
    metric_for_best_model="accuracy",
    push_to_hub=False,
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=train_dataset,
    eval_dataset=eval_dataset,   # 여기는 검증셋(10%)
    compute_metrics=compute_metrics,
)

print("AST 모델 학습을 시작합니다...")
trainer.train()

# -----------------------------------------------------------------------------
# 7. 최종 평가 및 저장
# -----------------------------------------------------------------------------
print("[Info] 최종 테스트(Test 20%) 수행 중...")
metrics = trainer.evaluate(test_dataset) # 여기는 테스트셋(20%)
print(f"🎯 최종 정확도(Accuracy): {metrics['eval_accuracy']:.4f}")

# 7. 학습된 모델 저장 (이것이 음성판 'best.pt'가 됩니다)
model.save_pretrained("./ai/weights/audio/best_ast_model")
feature_extractor.save_pretrained("./ai/weights/audio/best_ast_model") # Feature Extractor도 같이 저장
print("학습 완료 및 모델 저장 완료")