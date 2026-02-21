
# ai/scripts/vision/router_config.py
import os
import torch

# =============================================================================
# [Data Configuration]
# =============================================================================
DATA_DIR = "ai/data/yolo_router"
TRAIN_DIR = os.path.join(DATA_DIR, "train")
VAL_DIR = os.path.join(DATA_DIR, "val")
TEST_DIR = os.path.join(DATA_DIR, "test")

IMG_SIZE = 224
BATCH_SIZE = 32
NUM_WORKERS = 4 if os.name != 'nt' else 0

# ImageNet Normalization (Required for Pretrained Models)
MEAN = [0.485, 0.456, 0.406]
STD = [0.229, 0.224, 0.225]

# =============================================================================
# [Training Configuration] (User Requested)
# =============================================================================
EPOCHS = 50
LEARNING_RATE = 1e-3
WEIGHT_DECAY = 1e-4

# Device
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# =============================================================================
# [Utility Functions]
# =============================================================================
def get_device():
    return DEVICE

def save_metrics(model_name, metrics):
    """Save metrics to JSON file"""
    import json
    save_path = f"ai/runs/router_benchmark_{model_name}.json"
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=4)
    print(f"📊 Metrics saved to {save_path}")

def measure_latency(model, input_tensor, device, iterations=1000, warmup=50):
    """Measure average inference latency with metadata"""
    model.eval()
    
    # Metadata
    meta = {
        "latency_device": str(device),
        "latency_precision": "fp32", # Assuming fp32 for now
        "latency_batch": input_tensor.size(0),
        "latency_warmup": warmup,
        "latency_iters": iterations
    }

    with torch.no_grad():
        # Warm-up
        for _ in range(warmup):
            _ = model(input_tensor)
        
        if device.type == "cuda":
            torch.cuda.synchronize()
            
        import time
        start = time.time()
        for _ in range(iterations):
            _ = model(input_tensor)
            
        if device.type == "cuda":
            torch.cuda.synchronize()
            
        end = time.time()
        
    avg_latency = (end - start) / iterations * 1000 # ms
    return avg_latency, meta

def get_model_size_mb(model):
    """Get model size in MB"""
    param_size = 0
    for param in model.parameters():
        param_size += param.nelement() * param.element_size()
    buffer_size = 0
    for buffer in model.buffers():
        buffer_size += buffer.nelement() * buffer.element_size()
        
    size_all_mb = (param_size + buffer_size) / 1024**2
    return size_all_mb

def count_parameters(model):
    """
    Robust parameter counting.
    If model is a YOLO object (Ultralytics), handle it separately if possible,
    but usually this function is called with a PyTorch model (nn.Module).
    """
    try:
        return sum(p.numel() for p in model.parameters())
    except:
        return 0
