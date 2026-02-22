
# ai/scripts/vision/train_router_mobilenet.py
import torch
import torch.nn as nn
import torch.optim as optim
from torchvision import datasets, transforms, models
from torch.utils.data import DataLoader
import time
import os
import copy
from tqdm import tqdm

from ai.scripts.vision.router_config import (
    DATA_DIR, TRAIN_DIR, VAL_DIR, IMG_SIZE, BATCH_SIZE, NUM_WORKERS,
    MEAN, STD, EPOCHS as DEFAULT_EPOCHS, LEARNING_RATE, WEIGHT_DECAY, DEVICE,
    save_metrics, measure_latency, get_model_size_mb, count_parameters
)

import argparse
import sys

def build_model(num_classes):
    """
    MobileNetV3-Large Pretrained
    """
    print(f"[Model] Loading MobileNetV3-Large...")
    model = models.mobilenet_v3_large(weights=models.MobileNet_V3_Large_Weights.IMAGENET1K_V1)
    
    # Modify Classifier
    # MobileNetV3 classifier is a Sequential block. Last layer is '3'.
    in_features = model.classifier[3].in_features
    model.classifier[3] = nn.Linear(in_features, num_classes)
    
    return model.to(DEVICE)

def train_model(epochs):
    print(f"🚀 Training MobileNetV3-Large for Router Classification")
    print(f"   Device: {DEVICE}")
    print(f"   Epochs: {epochs}, Batch: {BATCH_SIZE}, Opt: Adam(lr={LEARNING_RATE})")
    
    # 1. Data Config (Same as EffNet)
    data_transforms = {
        'train': transforms.Compose([
            transforms.RandomResizedCrop(IMG_SIZE),
            transforms.RandomHorizontalFlip(),
            transforms.ToTensor(),
            transforms.Normalize(MEAN, STD)
        ]),
        'val': transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(IMG_SIZE),
            transforms.ToTensor(),
            transforms.Normalize(MEAN, STD)
        ]),
    }

    image_datasets = {
        x: datasets.ImageFolder(os.path.join(DATA_DIR, x), data_transforms[x])
        for x in ['train', 'val']
    }
    dataloaders = {
        x: DataLoader(image_datasets[x], batch_size=BATCH_SIZE, shuffle=(x=='train'), num_workers=NUM_WORKERS)
        for x in ['train', 'val']
    }
    dataset_sizes = {x: len(image_datasets[x]) for x in ['train', 'val']}
    class_names = image_datasets['train'].classes
    num_classes = len(class_names)
    
    print(f"   Classes: {class_names} ({num_classes})")
    print(f"   Train: {dataset_sizes['train']} images | Val: {dataset_sizes['val']} images")

    # 2. Model Setup
    model = build_model(num_classes)
    
    # 3. Optimizer & Criterion
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE, weight_decay=WEIGHT_DECAY)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    
    # 4. Training Loop
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

            for inputs, labels in tqdm(dataloaders[phase], desc=f"{phase} processing"):
                inputs = inputs.to(DEVICE)
                labels = labels.to(DEVICE)

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
                torch.save(model.state_dict(), "ai/weights/router/mobilenet_v3_best.pt")
                print(f"   💾 Saved Best Model ({best_acc:.4f})")

    print(f'Training complete. Best val Acc: {best_acc:.4f}')
    
    # 5. Load Best & Evaluate Metrics
    model.load_state_dict(best_model_wts)
    
    dummy_input = torch.randn(1, 3, IMG_SIZE, IMG_SIZE).to(DEVICE)
    latency = measure_latency(model, dummy_input, DEVICE)
    size_mb = get_model_size_mb(model)
    params = count_parameters(model)
    
    metrics = {
        "model": "MobileNetV3-Large",
        "top1_acc": best_acc.item(),
        "latency_ms": latency,
        "size_mb": size_mb,
        "params": params,
        "flops_g": 0.22 # Approximate
    }
    
    save_metrics("mobilenet_v3", metrics)
    print("="*60)
    print(f"📊 Final Metrics: {metrics}")
    print("="*60)

def run_benchmark():
    print(f"🚀 Benchmarking MobileNetV3-Large...")
    
    # 1. Load Model
    # Need to infer num_classes from dataset or assume 4
    data_transforms = transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(IMG_SIZE),
            transforms.ToTensor(),
            transforms.Normalize(MEAN, STD)
    ])
    
    val_dataset = datasets.ImageFolder(os.path.join(DATA_DIR, 'val'), data_transforms)
    class_names = val_dataset.classes
    num_classes = len(class_names)
    print(f"   Classes: {class_names} ({num_classes})")
    
    model = build_model(num_classes)
    
    weight_path = "ai/weights/router/mobilenet_v3_best.pt"
    if not os.path.exists(weight_path):
        print(f"❌ Best weights not found at {weight_path}")
        return

    model.load_state_dict(torch.load(weight_path))
    model.eval()

    # 2. Measure Latency (Fair)
    dummy_input = torch.randn(1, 3, IMG_SIZE, IMG_SIZE).to(DEVICE)
    latency, meta = measure_latency(model, dummy_input, DEVICE)
    
    # 3. Accuracy
    val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE, shuffle=False, num_workers=NUM_WORKERS)
    
    correct = 0
    total = 0
    with torch.no_grad():
        for inputs, labels in tqdm(val_loader, desc="Benchmarking Acc"):
            inputs = inputs.to(DEVICE)
            labels = labels.to(DEVICE)
            outputs = model(inputs)
            _, preds = torch.max(outputs, 1)
            correct += (preds == labels).sum().item()
            total += labels.size(0)
            
    acc = correct / total if total > 0 else 0.0
    
    # 4. Save Metrics
    params = count_parameters(model)
    size_mb = get_model_size_mb(model)
    
    metrics = {
        "model": "MobileNetV3-Large",
        "mode": "benchmark",
        "accuracy": acc, 
        "latency_ms": latency,
        "size_mb": size_mb,
        "params": params,
        "flops_g": 0.22,
        **meta
    }
    
    save_metrics("mobilenet_v3", metrics)
    print(f"✅ Benchmark Complete: Acc={acc:.4f}, Latency={latency:.2f}ms")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS, help="Number of epochs")
    parser.add_argument("--benchmark", action="store_true", help="Run benchmark only")
    args = parser.parse_args()

    if args.benchmark:
        run_benchmark()
    else:
        train_model(args.epochs)
