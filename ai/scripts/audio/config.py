# ai/scripts/audio/config.py
"""
[파일 용도] 오디오 학습 공통 설정 (Config)
오디오 모델 학습 및 추론에 필요한 모든 상수, 경로, 하이퍼파라미터(Epochs, Batch size, LR 등)를 정의합니다.
모든 스크립트에서 이 파일을 import하여 설정을 공유합니다. "Single Source of Truth" 역할을 합니다.
"""
import os, json, time, random
import torch
import numpy as np

# ──────────── 레이블 정의 ────────────
# Head 1: abnormal (binary)
ABNORMAL_LABELS = ["normal", "abnormal"]

# Head 2: sound_type (GT-Abnormal only)
# [Strict v3.7] Starter(0), Engine(1), Brake(2), Other(3)
TYPE_LABELS = ["starter", "engine", "brake", "other"]
NUM_TYPE_CLASSES = len(TYPE_LABELS)
type2id = {l: i for i, l in enumerate(TYPE_LABELS)}
id2type = {i: l for i, l in enumerate(TYPE_LABELS)}

# Inference threshold for "other" (Unknown abnormality)
OTHER_THRESHOLD = 0.45 # [v4.6.2] Final lower threshold
ABNORMAL_THRESHOLD = 0.8  # Primary Head (Normal vs Abnormal)

# ──────────── 하이퍼 파라미터 ────────────
COMMON_CONFIG = {
    "sr": 16000,
    "audio_length": 5,           # 5초 고정
    "batch_size": 32,            # [v4.5] User requested 32
    "lr_baseline": 1e-3,         # Head만
    "lr_finetune": 3e-5,         # [Added] Standard Fine-tune LR
    "lr_lora_backbone": 4e-5,    # [v4.8] Lightweight Tuning
    "lr_lora_head": 1.8e-4,      # [v4.5] Aggressive Tuning
    "optimizer": "AdamW",
    "baseline_epochs": 2,        # [v4.8] Minimal Baseline (Pure Head)
    "finetune_epochs": 8,        # [v4.8] Optimal LoRA fine-tune
    "warmup_ratio": 0.1,         # [v4.8] Slightly longer warmup
    "early_stop_patience": 8,    # Matches total epochs
    "early_stop_min_epochs": 4,  
    "grad_accum": 2,
    "lambda_type": 2.0,          # [v4.6.2] Increased Type Loss Emphasis
    "max_grad_norm": 1.0,        
    "aug_intensity": "high",     
    "samples_per_class": 0,      
    "use_focal_loss": True,      
    "focal_gamma": 1.3,          
    "use_mixup": True,           
    "mixup_alpha": 0.2,          # [v4.8] Reduced Mixup (prev: 0.35)
    "label_smoothing": 0.1,      
    "use_swa": True,             
}

# ──────────── Class Weights (Inverse Frequency) ────────────
# counts: starter=90, engine=334(≈274 train), brake=132(≈120 train)
# 여기서는 train_split 이후 동적으로 계산하므로 placeholder
# 실제 가중치는 data_loader에서 계산

# ──────────── 경로 ────────────
RUNPOD_DATA_PATH = "/workspace/large_data"
LOCAL_DATA_PATH = "./ai/data"
DATA_ROOT = RUNPOD_DATA_PATH if os.path.exists(RUNPOD_DATA_PATH) else LOCAL_DATA_PATH

TRAIN_DATA_DIR = os.path.join(DATA_ROOT, "audio/train")
TEST_DATA_DIR = os.path.join(DATA_ROOT, "audio/test")
NOISE_DATA_DIR = os.path.join(DATA_ROOT, "audio/noises")

SAVE_ROOT = "./ai/runs/dry_run" if os.environ.get("BENCHMARK_DRY_RUN") == "1" else "./ai/runs"
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
IS_RUNPOD = os.path.exists(RUNPOD_DATA_PATH)

# ──────────── Seed 완전 고정 ────────────
def set_seed(seed=42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False

# ──────────── Metrics 저장 ────────────
def save_metrics(model_name, mode, metrics: dict):
    """학습 결과를 metrics.json으로 저장 (소수점 3자리)"""
    # Dry-run 모드에서는 저장하지 않음
    if os.environ.get("BENCHMARK_DRY_RUN") == "1":
        print(f"⏭️  [DRY-RUN] Metrics 저장 건너뜀", flush=True)
        return
    # 모든 float 값을 소수점 3자리로 반올림
    rounded = {k: round(v, 3) if isinstance(v, float) else v for k, v in metrics.items()}
    save_dir = os.path.join(SAVE_ROOT, f"{model_name}_{mode}")
    os.makedirs(save_dir, exist_ok=True)
    path = os.path.join(save_dir, "metrics.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rounded, f, indent=2, ensure_ascii=False)
    print(f"📁 Metrics saved to {path}", flush=True)

# ──────────── 추론 속도 측정 ────────────
def measure_latency(model, sample_input, device, n_warmup=10, n_runs=100):
    """
    실제 추론 속도 측정 (batch_size=1)
    - AMP 끄고 fp32로 측정 (ONNX/실배포 latency와 일치)
    - torch.cuda.synchronize()로 GPU 비동기 실행 보정
    """
    model.eval()
    if isinstance(sample_input, dict):
        sample_input = {k: v.to(device) for k, v in sample_input.items()}
    elif isinstance(sample_input, torch.Tensor):
        sample_input = sample_input.to(device)

    # Warm-up
    with torch.no_grad(), torch.amp.autocast('cuda', enabled=False):
        for _ in range(n_warmup):
            if isinstance(sample_input, dict):
                model(**sample_input)
            else:
                model(sample_input)

    # 동기화 후 측정
    if torch.cuda.is_available():
        torch.cuda.synchronize()

    times = []
    with torch.no_grad(), torch.amp.autocast('cuda', enabled=False):
        for _ in range(n_runs):
            if torch.cuda.is_available():
                torch.cuda.synchronize()
            start = time.perf_counter()

            if isinstance(sample_input, dict):
                model(**sample_input)
            else:
                model(sample_input)

            if torch.cuda.is_available():
                torch.cuda.synchronize()
            elapsed = (time.perf_counter() - start) * 1000  # ms
            times.append(elapsed)

    avg = sum(times) / len(times)
    gpu_name = torch.cuda.get_device_name() if torch.cuda.is_available() else "CPU"
    print(f"⚡ Latency: {avg:.1f}ms (avg of {n_runs} runs, Device: {gpu_name})", flush=True)
    return avg

# ──────────── Early Stopping ────────────
class EarlyStopping:
    """macro_f1 기준 Early Stopping (min_epochs 이전에는 작동 안 함)"""
    def __init__(self, patience=5, min_epochs=8):
        self.patience = patience
        self.min_epochs = min_epochs
        self.best_score = -1
        self.counter = 0
        self.best_epoch = 0

    def step(self, score, epoch):
        if epoch < self.min_epochs:
            if score > self.best_score:
                self.best_score = score
                self.best_epoch = epoch
            return False  # 절대 중단 안 함

        if score > self.best_score:
            self.best_score = score
            self.best_epoch = epoch
            self.counter = 0
            return False
        else:
            self.counter += 1
            if self.counter >= self.patience:
                print(f"🛑 Early Stopping at epoch {epoch+1} (best: epoch {self.best_epoch+1}, score: {self.best_score:.4f})", flush=True)
                return True
            return False
