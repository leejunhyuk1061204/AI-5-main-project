# ai/scripts/vision/train_router_moblieNetV3.py
"""
MobileNetV3-Small 기반 장면 분류 모델 학습 도구
YOLOv11M-cls 대비 훨씬 가벼운 모델로 실시간성을 극대화합니다.
"""

import os
import argparse
import time
import copy
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from torchvision import datasets, models, transforms
from tqdm import tqdm

# =============================================================================
# [Configuration]
# =============================================================================
# [Path Config] RunPod과 로컬 환경 자동 감지
RUNPOD_DATA_PATH = "/workspace/large_data"
LOCAL_DATA_PATH = "ai/data"
DATA_ROOT = RUNPOD_DATA_PATH if os.path.exists(RUNPOD_DATA_PATH) else LOCAL_DATA_PATH

DATA_DIR = os.path.join(DATA_ROOT, "yolo_router")
SAVE_PATH = "ai/weights/router/mobilenetv3_best.pth"

# Training Hyperparameters
DEFAULT_BATCH_SIZE = 32
DEFAULT_IMG_SIZE = 640 # MobileNetV3 최적 사이즈
DEFAULT_EPOCHS = 50
LEARNING_RATE = 0.001

device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

def get_transforms():
    """데이터 증강 설정"""
    data_transforms = {
        'train': transforms.Compose([
            transforms.RandomResizedCrop(DEFAULT_IMG_SIZE, scale=(0.8, 1.0)),
            transforms.RandomHorizontalFlip(),
            transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ]),
        'val': transforms.Compose([
            transforms.Resize(int(DEFAULT_IMG_SIZE * 1.14)), # 약 730
            transforms.CenterCrop(DEFAULT_IMG_SIZE),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ]),
        'test': transforms.Compose([
            transforms.Resize(int(DEFAULT_IMG_SIZE * 1.14)),
            transforms.CenterCrop(DEFAULT_IMG_SIZE),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ]),
    }
    return data_transforms

def train_model(epochs=DEFAULT_EPOCHS, batch_size=DEFAULT_BATCH_SIZE):
    print(f"\n🚀 Starting MobileNetV3-Small Training for Router")
    print(f"   Data: {DATA_DIR}")
    print(f"   Device: {device}")

    # 1. 데이터셋 로드
    data_transforms = get_transforms()
    
    image_datasets = {
        x: datasets.ImageFolder(os.path.join(DATA_DIR, x), data_transforms[x])
        for x in ['train', 'val', 'test'] if os.path.exists(os.path.join(DATA_DIR, x))
    }
    
    dataloaders = {
        x: DataLoader(image_datasets[x], batch_size=batch_size, shuffle=True, num_workers=4 if os.name != 'nt' else 0)
        for x in image_datasets.keys()
    }
    
    dataset_sizes = {x: len(image_datasets[x]) for x in image_datasets.keys()}
    class_names = image_datasets['train'].classes
    num_classes = len(class_names)
    
    print(f"   Classes: {class_names} ({num_classes})")
    print(f"   Dataset sizes: {dataset_sizes}")

    # 2. 모델 설정 (MobileNetV3-Small)
    model = models.mobilenet_v3_small(weights=models.MobileNet_V3_Small_Weights.DEFAULT)
    
    # Final layer 수정
    num_ftrs = model.classifier[3].in_features
    model.classifier[3] = nn.Linear(num_ftrs, num_classes)
    model = model.to(device)

    criterion = nn.CrossEntropyLoss()
    optimizer = optim.AdamW(model.parameters(), lr=LEARNING_RATE)
    scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=7, gamma=0.1)

    # 3. 학습 루프
    since = time.time()
    best_model_wts = copy.deepcopy(model.state_dict())
    best_acc = 0.0

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

            for inputs, labels in tqdm(dataloaders[phase], desc=f"{phase}"):
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
            
            if phase == 'train':
                scheduler.step()

            epoch_loss = running_loss / dataset_sizes[phase]
            epoch_acc = running_corrects.double() / dataset_sizes[phase]

            print(f'{phase} Loss: {epoch_loss:.4f} Acc: {epoch_acc:.4f}')

            if phase == 'val' and epoch_acc > best_acc:
                best_acc = epoch_acc
                best_model_wts = copy.deepcopy(model.state_dict())
                os.makedirs(os.path.dirname(SAVE_PATH), exist_ok=True)
                torch.save(model.state_dict(), SAVE_PATH)
                print(f"✨ Best model saved! (Acc: {best_acc:.4f})")

    time_elapsed = time.time() - since
    print(f'\nTraining complete in {time_elapsed // 60:.0f}m {time_elapsed % 60:.0f}s')
    print(f'Best val Acc: {best_acc:4f}')

    # 최종 가중치 로드
    model.load_state_dict(best_model_wts)
    return model

def evaluate_model(model, batch_size=DEFAULT_BATCH_SIZE):
    """테스트셋 평가"""
    print("\n🔍 Final Evaluation on Test Set...")
    data_transforms = get_transforms()
    test_dir = os.path.join(DATA_DIR, 'test')
    
    if not os.path.exists(test_dir):
        print("   ⚠️ Test directory not found. Skipping evaluation.")
        return

    test_dataset = datasets.ImageFolder(test_dir, data_transforms['test'])
    test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False, num_workers=4 if os.name != 'nt' else 0)
    
    model.eval()
    running_corrects = 0
    
    with torch.no_grad():
        for inputs, labels in tqdm(test_loader, desc="Testing"):
            inputs = inputs.to(device)
            labels = labels.to(device)
            outputs = model(inputs)
            _, preds = torch.max(outputs, 1)
            running_corrects += torch.sum(preds == labels.data)

    test_acc = running_corrects.double() / len(test_dataset)
    print(f'🎯 Test Accuracy: {test_acc:.4f}')

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", type=str, default="train", choices=["train", "val", "test"])
    parser.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS)
    parser.add_argument("--batch", type=int, default=DEFAULT_BATCH_SIZE)
    args = parser.parse_args()

    if args.mode == "train":
        best_model = train_model(epochs=args.epochs, batch_size=args.batch)
        evaluate_model(best_model, batch_size=args.batch)
    elif args.mode in ["val", "test"]:
        # 저장된 가중치 로드 후 평가만 진행
        class_names = os.listdir(os.path.join(DATA_DIR, 'train'))
        model = models.mobilenet_v3_small()
        num_ftrs = model.classifier[3].in_features
        model.classifier[3] = nn.Linear(num_ftrs, len(class_names))
        
        if os.path.exists(SAVE_PATH):
            model.load_state_dict(torch.load(SAVE_PATH, map_location=device, weights_only=True))
            model = model.to(device)
            evaluate_model(model, batch_size=args.batch)
        else:
            print(f"❌ Weights not found at {SAVE_PATH}")
