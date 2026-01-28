# ai/scripts/train_router.py
"""
AI 분석 장면 분류 모델 학습 도구 (Router Classification Trainer)

[역할]
1. 장면 분류 학습: 이미지가 차량의 어느 부위(엔진, 계기판, 외관, 타이어)인지 판단하는 MobileNetV3-Small 모델을 학습합니다.
2. 경량화 모델: 모바일 및 실시간 환경에 최적화된 아키텍처를 사용하여 빠른 추론 속도를 보장합니다.
3. 데이터셋 연동: ai/data/yolo_router에 구성된 데이터를 사용하여 학습을 진행합니다.

[사용법]
1. 데이터셋 생성: python ai/scripts/create_router_dataset.py
2. 모델 학습: python ai/scripts/train_router.py --epochs 50
"""

import os
import argparse
import time
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from torchvision import datasets, transforms, models
import shutil

# =============================================================================
# [Configuration]
# =============================================================================
DATA_DIR = "ai/data/yolo_router"
SAVE_PATH = "ai/weights/router/best.pt"
IMG_SIZE = 224
BATCH_SIZE = 32
DEFAULT_EPOCHS = 50
LEARNING_RATE = 0.001

def train_model(epochs=DEFAULT_EPOCHS):
    print("\n" + "="*60)
    print(f"🚀 Router 장면 분류 모델 학습 시작 (MobileNetV3-Small)")
    print(f"   Epochs: {epochs}, Batch Size: {BATCH_SIZE}")
    print("="*60)

    # Device 설정
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[Device] Using: {device}")

    # 데이터 전처리
    data_transforms = {
        'train': transforms.Compose([
            transforms.RandomResizedCrop(IMG_SIZE),
            transforms.RandomHorizontalFlip(),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ]),
        'val': transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(IMG_SIZE),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ]),
    }

    # 데이터셋 로드
    image_datasets = {
        x: datasets.ImageFolder(os.path.join(DATA_DIR, x), data_transforms[x])
        for x in ['train', 'val']
    }
    dataloaders = {
        x: DataLoader(image_datasets[x], batch_size=BATCH_SIZE, shuffle=True, num_workers=0)
        for x in ['train', 'val']
    }
    dataset_sizes = {x: len(image_datasets[x]) for x in ['train', 'val']}
    class_names = image_datasets['train'].classes
    print(f"[Data] Classes: {class_names}")
    print(f"[Data] Train: {dataset_sizes['train']}, Val: {dataset_sizes['val']}")

    # 모델 생성 (MobileNetV3-Small)
    try:
        model = models.mobilenet_v3_small(weights=models.MobileNet_V3_Small_Weights.DEFAULT)
    except AttributeError:
        # 구버전 또는 다른 명칭 대처
        print("[Info] MobileNet_V3_Small_Weights not found, trying legacy pretrained=True")
        model = models.mobilenet_v3_small(pretrained=True)
    
    # 출력층 수정 (4개 클래스)
    num_ftrs = model.classifier[-1].in_features
    model.classifier[-1] = nn.Linear(num_ftrs, len(class_names))
    model = model.to(device)

    # 손실 함수 및 옵티마이저
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE)

    # 학습 루프
    since = time.time()
    best_acc = 0.0
    best_model_wts = model.state_dict()

    for epoch in range(epochs):
        print(f'\nEpoch {epoch+1}/{epochs}')
        print('-' * 10)

        for phase in ['train', 'val']:
            if phase == 'train':
                model.train()
            else:
                model.eval()

            running_loss = 0.0
            running_corrects = 0

            batch_idx = 0
            for inputs, labels in dataloaders[phase]:
                inputs = inputs.to(device)
                labels = labels.to(device)

                optimizer.zero_grad()

                with torch.set_grad_enabled(phase == 'train'):
                    outputs = model(inputs)
                    _, preds = torch.max(outputs, 1)
                    loss = criterion(outputs, labels)

                    if phase == 'train':
                        loss.backward()
                        optimizer.step()

                running_loss += loss.item() * inputs.size(0)
                running_corrects += torch.sum(preds == labels.data)
                
                # 배치 진행률 표시 (추가됨)
                batch_idx += 1
                if batch_idx % 20 == 0:
                    print(f"  [{phase}] Batch {batch_idx}/{len(dataloaders[phase])} Loss: {loss.item():.4f}")

            epoch_loss = running_loss / dataset_sizes[phase]
            epoch_acc = running_corrects.double() / dataset_sizes[phase]

            print(f'{phase} Loss: {epoch_loss:.4f} Acc: {epoch_acc:.4f}')

            # Best 모델 저장
            if phase == 'val' and epoch_acc > best_acc:
                best_acc = epoch_acc
                best_model_wts = model.state_dict()

    time_elapsed = time.time() - since
    print(f'\n[✓] 학습 완료! 소요 시간: {time_elapsed // 60:.0f}분 {time_elapsed % 60:.0f}초')
    print(f'[✓] Best Val Acc: {best_acc:4f}')

    # 가중치 저장
    os.makedirs(os.path.dirname(SAVE_PATH), exist_ok=True)
    torch.save(best_model_wts, SAVE_PATH)
    print(f"[✓] Best 모델이 저장되었습니다: {SAVE_PATH}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Router Classification Training")
    parser.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS)
    args = parser.parse_args()
    
    train_model(args.epochs)
