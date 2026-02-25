# ai/scripts/vision/train_router_mobilenet.py
"""
MobileNetV3-Small 기반 차량 장면 분류(Router) 벤치마크 학습 스크립트
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
from sklearn.metrics import classification_report, confusion_matrix, precision_recall_fscore_support
import numpy as np

# [Config] 감지 및 경로 설정
RUNPOD_DATA_PATH = "/workspace/large_data"
LOCAL_DATA_PATH = "ai/data"
DATA_ROOT = RUNPOD_DATA_PATH if os.path.exists(RUNPOD_DATA_PATH) else LOCAL_DATA_PATH
DATA_DIR = os.path.join(DATA_ROOT, "yolo_router")
SAVE_ROOT = "ai/weights/router"
SAVE_PATH = os.path.join(SAVE_ROOT, "mobilenet_v3_small_best.pth")

# Hyperparameters (User Request)
IMG_SIZE = 224
BATCH_SIZE = 16
EPOCHS_S1 = 2
EPOCHS_S2 = 15
WEIGHT_DECAY = 1e-4

device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

def get_transforms():
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
    print(f"\n🚀 [MobileNetV3-S] Starting Router Benchmark Training")
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

    # Model: MobileNetV3-Small
    model = models.mobilenet_v3_small(weights=models.MobileNet_V3_Small_Weights.DEFAULT)
    num_ftrs = model.classifier[3].in_features
    model.classifier[3] = nn.Linear(num_ftrs, num_classes)
    model = model.to(device)

    criterion = nn.CrossEntropyLoss()
    best_acc = 0.0
    best_model_wts = copy.deepcopy(model.state_dict())

    # [Phase 1] 2 Epochs
    print(f"\n❄️ [Phase 1] Head only (2 Epochs)...")
    for param in model.features.parameters(): param.requires_grad = False
    optimizer_s1 = optim.AdamW(model.classifier.parameters(), lr=1e-3, weight_decay=WEIGHT_DECAY)

    for epoch in range(EPOCHS_S1):
        print(f'Epoch {epoch+1}/{EPOCHS_S1}')
        for phase in ['train', 'val']:
            model.train() if phase == 'train' else model.eval()
            running_loss, running_corrects = 0.0, 0
            
            all_preds = []
            all_labels = []
            
            for inputs, labels in tqdm(dataloaders[phase]):
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
                
                if phase == 'val':
                    all_preds.extend(preds.cpu().numpy())
                    all_labels.extend(labels.cpu().numpy())
                    
            print(f'{phase} Acc: {running_corrects.double()/dataset_sizes[phase]:.4f}')
            
            if phase == 'val':
                print("\n🎯 Validation Classification Report:")
                print(classification_report(all_labels, all_preds, target_names=class_names, digits=4))
                
            if phase == 'val' and (running_corrects.double()/dataset_sizes[phase]) > best_acc:
                best_acc = running_corrects.double()/dataset_sizes[phase]
                best_model_wts = copy.deepcopy(model.state_dict())
                os.makedirs(SAVE_ROOT, exist_ok=True)
                torch.save(model.state_dict(), SAVE_PATH)

    # [Phase 2] 2 Epochs
    print(f"\n🔥 [Phase 2] Full Fine-tuning (15 Epochs)...")
    for param in model.parameters(): param.requires_grad = True
    optimizer_s2 = optim.AdamW(model.parameters(), lr=1e-5, weight_decay=WEIGHT_DECAY)
    scheduler_s2 = optim.lr_scheduler.CosineAnnealingLR(optimizer_s2, T_max=EPOCHS_S2)

    for epoch in range(EPOCHS_S1, EPOCHS_S1 + EPOCHS_S2):
        print(f'Epoch {epoch+1}/{EPOCHS_S1 + EPOCHS_S2}')
        for phase in ['train', 'val']:
            model.train() if phase == 'train' else model.eval()
            running_loss, running_corrects = 0.0, 0
            
            all_preds = []
            all_labels = []
            
            for inputs, labels in tqdm(dataloaders[phase]):
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
                
                if phase == 'val':
                    all_preds.extend(preds.cpu().numpy())
                    all_labels.extend(labels.cpu().numpy())
                    
            acc = running_corrects.double() / dataset_sizes[phase]
            print(f'{phase} Acc: {acc:.4f}')
            
            if phase == 'val':
                print("\n🎯 Validation Classification Report:")
                print(classification_report(all_labels, all_preds, target_names=class_names, digits=4))
                
                # Manually calculate and print micro avg
                micro_p, micro_r, micro_f1, _ = precision_recall_fscore_support(all_labels, all_preds, average='micro')
                print(f"   micro avg     {micro_p:.4f}    {micro_r:.4f}    {micro_f1:.4f}      {len(all_labels)}")
                

            if phase == 'train': scheduler_s2.step()
            if phase == 'val' and acc > best_acc:
                best_acc = acc
                best_model_wts = copy.deepcopy(model.state_dict())
                torch.save(model.state_dict(), SAVE_PATH)
    
    model.load_state_dict(best_model_wts)
    return model, class_names

if __name__ == "__main__":
    best_model, class_names = train_model()
    # evaluate logic same as effnet
