
# ai/scripts/vision/train_router_effnet.py
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
    EfficientNet-B0 Pretrained
    """
    print(f"[Model] Loading EfficientNet-B0...")
    model = models.efficientnet_b0(weights=models.EfficientNet_B0_Weights.IMAGENET1K_V1)
    
    # Modify Classifier
    in_features = model.classifier[1].in_features
    model.classifier[1] = nn.Linear(in_features, num_classes)
    
    return model.to(DEVICE)

def train_model(epochs):
    print(f"🚀 Training EfficientNet-B0 for Router Classification")
    print(f"   Device: {DEVICE}")
    print(f"   Epochs: {epochs}, Batch: {BATCH_SIZE}, Opt: Adam(lr={LEARNING_RATE})")
    
    # 1. Data Config
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
                torch.save(model.state_dict(), "ai/weights/router/efficientnet_b0_best.pt")
                print(f"   💾 Saved Best Model ({best_acc:.4f})")

    print(f'Training complete. Best val Acc: {best_acc:.4f}')
    
    # 5. Load Best & Evaluate Metrics
    model.load_state_dict(best_model_wts)
    
    dummy_input = torch.randn(1, 3, IMG_SIZE, IMG_SIZE).to(DEVICE)
    latency = measure_latency(model, dummy_input, DEVICE)
    size_mb = get_model_size_mb(model)
    params = count_parameters(model)
    
    metrics = {
        "model": "EfficientNet-B0",
        "top1_acc": best_acc.item(),
        "latency_ms": latency,
        "size_mb": size_mb,
        "params": params,
        "flops_g": 0.39 # User provided approx, or use thop
    }
    
    save_metrics("efficientnet_b0", metrics)
    print("="*60)
    print(f"📊 Final Metrics: {metrics}")
    print("="*60)

def run_benchmark():
    print(f"🚀 Benchmarking EfficientNet-B0...")
    
    # 1. Load Model
    # Re-build structure
    model = build_model(num_classes=4) # Assuming 4 classes for router? need to check dataset or pass arg
    # Actually, we should check the dataset to get num_classes if possible, or use a fixed number if known.
    # For safety, let's look at the training directory or assume 4 (as seen in config checks potentially, or standard router)
    # But wait, num_classes is determined by dataset folders in train_model.
    # We need to get class names dynamically or save them.
    # For now, let's rely on data dir existence to get classes.
    
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
    
    weight_path = "ai/weights/router/efficientnet_b0_best.pt"
    if not os.path.exists(weight_path):
        print(f"❌ Best weights not found at {weight_path}")
        return

    model.load_state_dict(torch.load(weight_path))
    model.eval()

    # 2. Measure Latency (Fair)
    dummy_input = torch.randn(1, 3, IMG_SIZE, IMG_SIZE).to(DEVICE)
    latency, meta = measure_latency(model, dummy_input, DEVICE)
    
    # 3. Accuracy (Optional for benchmark if already saved? No, recalculate or load)
    # User said "Epochs=1 if test mode", so let's run validation on val set
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
        "model": "EfficientNet-B0",
        "mode": "benchmark",
        "accuracy": acc, # Unified key
        "latency_ms": latency,
        "size_mb": size_mb,
        "params": params,
        "flops_g": 0.39,
        **meta
    }
    
    save_metrics("efficientnet_b0", metrics)
    print(f"✅ Benchmark Complete: Acc={acc:.4f}, Latency={latency:.2f}ms")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS)
    parser.add_argument("--benchmark", action="store_true", help="Run benchmark only (Lat/Acc) on best model")
    args = parser.parse_args()
    
    if args.benchmark:
        run_benchmark()
    else:
        train_model(args.epochs)
