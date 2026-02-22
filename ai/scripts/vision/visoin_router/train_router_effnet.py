# ai/scripts/vision/train_router_effnet.py
"""
EfficientNet-B0 기반 차량 장면 분류(Router) 벤치마크 학습 스크립트
[기준]
- 해상도: 224x224
- 배치 크기: 16
- 학습 전략: 1단계(헤드 10ep) -> 2단계(전체 20ep)
- 옵티마이저: AdamW (weight decay 1e-4)
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
from sklearn.metrics import classification_report, confusion_matrix
import numpy as np

# [Config] 감지 및 경로 설정
RUNPOD_DATA_PATH = "/workspace/large_data"
LOCAL_DATA_PATH = "ai/data"
DATA_ROOT = RUNPOD_DATA_PATH if os.path.exists(RUNPOD_DATA_PATH) else LOCAL_DATA_PATH
DATA_DIR = os.path.join(DATA_ROOT, "yolo_router")
SAVE_ROOT = "ai/weights/router"
SAVE_PATH = os.path.join(SAVE_ROOT, "effnet_b0_best.pth")

# Hyperparameters (User Request)
IMG_SIZE = 224
BATCH_SIZE = 16
EPOCHS_S1 = 10  # Phase 1: Head only
EPOCHS_S2 = 20  # Phase 2: Full fine-tuning
WEIGHT_DECAY = 1e-4

device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

def get_transforms():
    """사용자 요청 해상도(224) 기반 변환 설정"""
    return {
        'train': transforms.Compose([
            transforms.RandomResizedCrop(IMG_SIZE),
            transforms.RandomHorizontalFlip(),
            transforms.ColorJitter(brightness=0.2, contrast=0.2),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ]),
        'val': transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(IMG_SIZE),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ]),
        'test': transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(IMG_SIZE),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ]),
    }

def train_model():
    print(f"\n🚀 [EffNet-B0] Starting Router Benchmark Training")
    print(f"   Settings: {IMG_SIZE}x{IMG_SIZE}, Batch {BATCH_SIZE}, AdamW (WD {WEIGHT_DECAY})")

    # 1. Dataset & Loader
    transforms_dict = get_transforms()
    image_datasets = {
        x: datasets.ImageFolder(os.path.join(DATA_DIR, x), transforms_dict[x])
        for x in ['train', 'val', 'test'] if os.path.exists(os.path.join(DATA_DIR, x))
    }
    dataloaders = {
        x: DataLoader(image_datasets[x], batch_size=BATCH_SIZE, shuffle=(x=='train'), num_workers=2 if os.name != 'nt' else 0)
        for x in image_datasets.keys()
    }
    dataset_sizes = {x: len(image_datasets[x]) for x in image_datasets.keys()}
    class_names = image_datasets['train'].classes
    num_classes = len(class_names)

    # 2. Model: EfficientNet-B0
    model = models.efficientnet_b0(weights=models.EfficientNet_B0_Weights.DEFAULT)
    num_ftrs = model.classifier[1].in_features
    model.classifier[1] = nn.Linear(num_ftrs, num_classes)
    model = model.to(device)

    criterion = nn.CrossEntropyLoss()
    best_acc = 0.0
    best_model_wts = copy.deepcopy(model.state_dict())

    # =========================================================================
    # [Phase 1] 10 Epochs - Output layer only
    # =========================================================================
    print(f"\n❄️ [Phase 1] Training Classifier only (10 Epochs)...")
    for param in model.features.parameters():
        param.requires_grad = False
        
    optimizer_s1 = optim.AdamW(model.classifier.parameters(), lr=1e-3, weight_decay=WEIGHT_DECAY)

    for epoch in range(EPOCHS_S1):
        print(f'Epoch {epoch+1}/{EPOCHS_S1} (Phase 1)')
        for phase in ['train', 'val']:
            model.train() if phase == 'train' else model.eval()
            running_loss, running_corrects = 0.0, 0
            for inputs, labels in tqdm(dataloaders[phase], desc=f"{phase}"):
                inputs, labels = inputs.to(device), labels.to(device)
                optimizer_s1.zero_grad()
                with torch.set_grad_enabled(phase == 'train'):
                    outputs = model(inputs)
                    _, preds = torch.max(outputs, 1)
                    loss = criterion(outputs, labels)
                    if phase == 'train':
                        loss.backward()
                        optimizer_s1.step()
                running_loss += loss.item() * inputs.size(0)
                running_corrects += torch.sum(preds == labels.data)
            
            epoch_loss = running_loss / dataset_sizes[phase]
            epoch_acc = running_corrects.double() / dataset_sizes[phase]
            print(f'{phase} Loss: {epoch_loss:.4f} Acc: {epoch_acc:.4f}')

            if phase == 'val' and epoch_acc > best_acc:
                best_acc = epoch_acc
                best_model_wts = copy.deepcopy(model.state_dict())
                os.makedirs(SAVE_ROOT, exist_ok=True)
                torch.save(model.state_dict(), SAVE_PATH)

    # =========================================================================
    # [Phase 2] 20 Epochs - Full Fine-tuning
    # =========================================================================
    print(f"\n🔥 [Phase 2] Unfreezing all layers (20 Epochs)...")
    for param in model.parameters():
        param.requires_grad = True
        
    # Full FT에서는 낮은 학습률 사용
    optimizer_s2 = optim.AdamW(model.parameters(), lr=1e-5, weight_decay=WEIGHT_DECAY)
    scheduler_s2 = optim.lr_scheduler.CosineAnnealingLR(optimizer_s2, T_max=EPOCHS_S2)

    for epoch in range(EPOCHS_S1, EPOCHS_S1 + EPOCHS_S2):
        print(f'Epoch {epoch+1}/{EPOCHS_S1 + EPOCHS_S2} (Phase 2)')
        for phase in ['train', 'val']:
            model.train() if phase == 'train' else model.eval()
            running_loss, running_corrects = 0.0, 0
            for inputs, labels in tqdm(dataloaders[phase], desc=f"{phase}"):
                inputs, labels = inputs.to(device), labels.to(device)
                optimizer_s2.zero_grad()
                with torch.set_grad_enabled(phase == 'train'):
                    outputs = model(inputs)
                    _, preds = torch.max(outputs, 1)
                    loss = criterion(outputs, labels)
                    if phase == 'train':
                        loss.backward()
                        optimizer_s2.step()
                running_loss += loss.item() * inputs.size(0)
                running_corrects += torch.sum(preds == labels.data)
            
            epoch_loss = running_loss / dataset_sizes[phase]
            epoch_acc = running_corrects.double() / dataset_sizes[phase]
            print(f'{phase} Loss: {epoch_loss:.4f} Acc: {epoch_acc:.4f}')

            if phase == 'train': scheduler_s2.step()
            if phase == 'val' and epoch_acc > best_acc:
                best_acc = epoch_acc
                best_model_wts = copy.deepcopy(model.state_dict())
                torch.save(model.state_dict(), SAVE_PATH)
                print(f"✨ New best model saved! (Acc: {best_acc:.4f})")

    print(f'\nFinished training. Best val Acc: {best_acc:4f}')
    model.load_state_dict(best_model_wts)
    return model, class_names

def evaluate(model, class_names):
    print("\n🔍 Final Evaluation on Test Set...")
    transforms_dict = get_transforms()
    test_dataset = datasets.ImageFolder(os.path.join(DATA_DIR, 'test'), transforms_dict['test'])
    test_loader = DataLoader(test_dataset, batch_size=BATCH_SIZE, shuffle=False)
    
    model.eval()
    all_preds, all_labels = [], []
    with torch.no_grad():
        for inputs, labels in test_loader:
            inputs = inputs.to(device)
            outputs = model(inputs)
            _, preds = torch.max(outputs, 1)
            all_preds.extend(preds.cpu().numpy())
            all_labels.extend(labels.numpy())

    print("\n📈 [EfficientNet-B0] Classification Report")
    print(classification_report(all_labels, all_preds, target_names=class_names, digits=4))

if __name__ == "__main__":
    best_model, class_names = train_model()
    evaluate(best_model, class_names)
