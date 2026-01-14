import kagglehub
import os
import torch
import librosa
import numpy as np
from transformers import ASTConfig, ASTForAudioClassification, ASTFeatureExtractor, Trainer, TrainingArguments
from datasets import Dataset, Audio

# 1. Kaggle 데이터셋 다운로드 (janboubiabderrahim/vehicle-sounds-dataset)
# 별도의 API Key 설정 없이 최신 버전을 다운로드합니다.
path = kagglehub.dataset_download("janboubiabderrahim/vehicle-sounds-dataset")
print(f"데이터셋 다운로드 위치: {path}")

# 2. 전처리 설정 (16kHz 리샘플링 포함)
feature_extractor = ASTFeatureExtractor.from_pretrained("MIT/ast-finetuned-audioset-10-10-0.4593")

def preprocess_function(examples):
    # 오디오 파일을 16kHz로 로드하여 특징 추출
    audio_arrays = [x["array"] for x in examples["audio"]]
    inputs = feature_extractor(audio_arrays, sampling_rate=16000, return_tensors="pt", padding="max_length")
    return inputs

# 3. 데이터셋 로드 및 준비
# Kaggle 폴더 구조에 맞춰 데이터를 Label링하는 로직이 필요합니다.
# 여기서는 폴더명이 클래스명(Car, Bus 등)인 경우를 가정합니다.
data_list = []
for label in os.listdir(path):
    label_path = os.path.join(path, label)
    if os.path.isdir(label_path):
        for file in os.listdir(label_path):
            if file.endswith('.wav'):
                data_list.append({"audio": os.path.join(label_path, file), "label": label})

dataset = Dataset.from_list(data_list).cast_column("audio", Audio(sampling_rate=16000))
dataset = dataset.map(preprocess_function, batched=True)

# 4. AST 모델 설정 (YOLO 대신 사용)
# '엔진 소리인가?'를 판별하기 위한 이진 또는 다중 분류 설정
labels = list(set([x['label'] for x in data_list]))
label2id = {label: i for i, label in enumerate(labels)}
id2label = {i: label for i, label in enumerate(labels)}

model = ASTForAudioClassification.from_pretrained(
    "MIT/ast-finetuned-audioset-10-10-0.4593",
    num_labels=len(labels),
    label2id=label2id,
    id2label=id2label,
    ignore_mismatched_sizes=True
)

# 5. 학습 설정 (TrainingArguments)
training_args = TrainingArguments(
    output_dir="./Ai/runs/audio_model",
    per_device_train_batch_size=8,
    num_train_epochs=10,        # 음성은 이미지보다 학습이 빠를 수 있습니다.
    learning_rate=3e-5,
    logging_dir='./logs',
    save_strategy="epoch",
    evaluation_strategy="epoch",
    push_to_hub=False,
)

# 6. 학습 시작
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=dataset,
)

print("AST 모델 학습을 시작합니다...")
trainer.train()

# 7. 학습된 모델 저장 (이것이 음성판 'best.pt'가 됩니다)
model.save_pretrained("./Ai/weights/audio/best_ast_model")
print("학습 완료 및 모델 저장 완료")