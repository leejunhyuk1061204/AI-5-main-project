import torch
import torch.nn as nn
from torchvision import datasets, models, transforms
from torch.utils.data import DataLoader
import os
import time
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score
from tqdm import tqdm
import argparse

# [Configuration]
RUNPOD_DATA_PATH = "/workspace/large_data"
LOCAL_DATA_PATH = "ai/data"
DATA_ROOT = RUNPOD_DATA_PATH if os.path.exists(RUNPOD_DATA_PATH) else LOCAL_DATA_PATH
TEST_DIR = os.path.join(DATA_ROOT, "yolo_router", "test")
WEIGHTS_ROOT = "ai/weights/router"
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
IMG_SIZE = 224

def get_test_loader_acc(batch_size=16): # 정확도 측정용 (Batch 16 가능)
    test_transform = transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(IMG_SIZE),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])
    if not os.path.exists(TEST_DIR): return None, None
    test_dataset = datasets.ImageFolder(TEST_DIR, test_transform)
    return DataLoader(test_dataset, batch_size=batch_size, shuffle=False, num_workers=4 if os.name != 'nt' else 0), test_dataset.classes

def load_model(model_name, weight_path, num_classes):
    if model_name == "effnet_b0":
        model = models.efficientnet_b0()
        model.classifier[1] = nn.Linear(model.classifier[1].in_features, num_classes)
    elif model_name == "mobilenet_v3":
        model = models.mobilenet_v3_large()
        model.classifier[3] = nn.Linear(model.classifier[3].in_features, num_classes)
    elif model_name == "swin_t":
        model = models.swin_s() # Using Swin-S based on train script
        model.head = nn.Linear(model.head.in_features, num_classes)
    else: return None

    if not os.path.exists(weight_path): return None
    model.load_state_dict(torch.load(weight_path, map_location=DEVICE))
    return model.to(DEVICE).eval()

def count_parameters(model):
    """Trainable parameter count in Millions"""
    return sum(p.numel() for p in model.parameters() if p.requires_grad) / 1e6

def evaluate_accuracy(model, loader):
    """Batch processing for Accuracy/F1"""
    all_preds, all_labels = [], []
    
    with torch.no_grad():
        for inputs, labels in tqdm(loader, desc="  evaluating acc"):
            inputs = inputs.to(DEVICE)
            outputs = model(inputs)
            _, preds = torch.max(outputs, 1)
            all_preds.extend(preds.cpu().numpy())
            all_labels.extend(labels.numpy())

    acc = accuracy_score(all_labels, all_preds)
    f1 = f1_score(all_labels, all_preds, average='macro')
    return acc, f1

def measure_latency(model, shape=(1, 3, 224, 224), repetitions=100):
    """Strict Latency Measurement (Batch=1, Sync)"""
    model.eval()
    dummy_input = torch.randn(shape).to(DEVICE)

    # Warm-up
    with torch.no_grad():
        for _ in range(50):
            _ = model(dummy_input)
    
    if DEVICE.type == 'cuda':
        torch.cuda.synchronize()

    # Measurement
    timings = []
    with torch.no_grad():
        for _ in range(repetitions):
            start_time = time.time()
            _ = model(dummy_input)
            if DEVICE.type == 'cuda':
                torch.cuda.synchronize()
            end_time = time.time()
            timings.append((end_time - start_time) * 1000) # ms

    avg_latency = np.mean(timings)
    std_latency = np.std(timings)
    return avg_latency, std_latency

def run_benchmark(args):
    # Retrieve mock loader if dry-run, else real loader
    loader_func = get_test_loader_acc
    if args.dry_run:
        # Define mock loader locally or use global if patched
        pass 
        
    loader, classes = loader_func(args.batch_size)
    if loader is None:
        print(f"❌ Test set not found at {TEST_DIR}")
        return

    models_info = [
        {"name": "effnet_b0", "file": "efficientnet_b0_best.pt", "label": "EffNet-B0"},
        {"name": "mobilenet_v3", "file": "mobilenet_v3_best.pt", "label": "MobileNetV3-L"},
        {"name": "swin_t", "file": "swin_t_best.pth", "label": "Swin-T (Small)"},
    ]

    results = []
    print(f"\n🚀 Integrated Vision Router Benchmark")
    print(f"   - Device: {DEVICE}")
    print(f"   - Latency Mode: Batch=1, Sync=True, Reps={args.reps}")
    print(f"   - Test Data: {len(loader.dataset)} images")
    print("=" * 60)

    for m in models_info:
        weight_path = os.path.join(WEIGHTS_ROOT, m["file"])
        print(f"\n▶️  Benchmarking {m['label']} ...")
        
        model = load_model(m["name"], weight_path, len(classes))
        if model:
            # 1. Accuracy (Batch 16)
            acc, f1 = evaluate_accuracy(model, loader)
            
            # 2. Latency (Batch 1)
            lat, lat_std = measure_latency(model, shape=(1, 3, IMG_SIZE, IMG_SIZE), repetitions=args.reps)
            
            # 3. Model Stats
            params = count_parameters(model)
            size_mb = os.path.getsize(weight_path) / (1024 * 1024)
            
            results.append({
                "Model": m["label"],
                "Top-1 Acc": acc,
                "Macro F1": f1,
                "Latency (ms)": lat,
                "Params (M)": params,
                "Size (MB)": size_mb,
                "Device": str(DEVICE)
            })
            print(f"   ✅ Done: Acc={acc:.4f} | Lat={lat:.2f}ms | Params={params:.1f}M")
        else:
            print(f"   ❌ Model load failed (check path): {weight_path}")

    if results:
        df = pd.DataFrame(results)
        # Format columns
        df["Top-1 Acc"] = df["Top-1 Acc"].map("{:.4f}".format)
        df["Macro F1"] = df["Macro F1"].map("{:.4f}".format)
        df["Latency (ms)"] = df["Latency (ms)"].map("{:.2f}".format)
        df["Params (M)"] = df["Params (M)"].map("{:.1f}".format)
        df["Size (MB)"] = df["Size (MB)"].map("{:.1f}".format)
        
        print("\n🏆 Final Benchmark Summary")
        print(df.to_markdown(index=False))
        
        # Save CSV
        save_path = "ai/runs/vision_benchmark_result.csv"
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        df.to_csv(save_path, index=False)
        print(f"\n💾 Saved to {save_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Vision Router Benchmark Tool")
    parser.add_argument("--batch-size", type=int, default=16, help="Batch size for accuracy test")
    parser.add_argument("--reps", type=int, default=100, help="Latency measurement repetitions")
    parser.add_argument("--dry-run", action="store_true", help="Run with minimal data/reps for testing")
    args = parser.parse_args()
    
    # Overwrite config for dry-run
    if args.dry_run:
        print("⚠️  DRY RUN MODE: Reduced repetitions and data limit")
        args.reps = 2
        
        # Monkey patch get_test_loader_acc to return small subset
        original_loader_func = get_test_loader_acc
        def mock_loader(batch_size=16):
            loader, classes = original_loader_func(batch_size)
            if loader:
                # Limit dataset
                loader.dataset.samples = loader.dataset.samples[:20]
                loader.dataset.targets = loader.dataset.targets[:20] 
                # Re-create loader
                return DataLoader(loader.dataset, batch_size=batch_size, shuffle=False, num_workers=0), classes
            return None, None
            
        get_test_loader_acc = mock_loader

    run_benchmark(args)
