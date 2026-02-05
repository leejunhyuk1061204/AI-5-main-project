# ai/scripts/train_tire.py
"""
타이어 상태 분석 YOLO 모델 학습 도구 (Tire YOLO Trainer)

[역할]
1. 결함 탐지 학습: 타이어의 고무 상태(정상, 마모, 균열) 및 측면 파손 등을 감지하는 YOLOv8 모델을 학습합니다.
2. 미세 패턴 식별: 타이어 패턴의 세밀한 변화를 학습할 수 있도록 고해상도(imgsz 640/1280) 설정을 지원합니다.
3. 데이터셋 연동: ai/data/tire 구조에 저장된 이미지와 라벨을 사용하여 학습을 진행합니다.

[사용법]
python ai/scripts/train_tire.py --mode train --epochs 150
"""
import argparse
import os
import shutil
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import classification_report, confusion_matrix, roc_curve, auc
from ultralytics import YOLO

# =============================================================================
# [Configuration] 
# =============================================================================
BASE_MODEL = "yolo11m-cls.pt"

# [Path Config] RunPod과 로컬 환경 자동 감지
RUNPOD_DATA_PATH = "/workspace/large_data"
LOCAL_DATA_PATH = "ai/data"
DATA_ROOT = RUNPOD_DATA_PATH if os.path.exists(RUNPOD_DATA_PATH) else LOCAL_DATA_PATH

DATA_DIR = os.path.join(DATA_ROOT, "yolo/tire")
OUTPUT_DIR = "ai/runs/tire_model"
SAVE_PATH = "ai/weights/tire/best.pt"

DEFAULT_EPOCHS = 100
BATCH_SIZE = 2  # 1280 + Medium 모델에는 8도 큼 -> 2로 초저하향 (OOM 방지)
IMG_SIZE = 1280   # YOLO 분류 모델 표준 사이즈

def train_model(epochs=DEFAULT_EPOCHS):
    print(f"\n[Tire Classification] 학습 시작 ({epochs} epochs)...")
    if not os.path.exists(DATA_DIR):
        print(f"[Error] 데이터 디렉토리 {DATA_DIR} 가 없습니다.")
        return
    
    model = YOLO(BASE_MODEL)
    
    # [Weight Management] 기존 가중치가 있다면 백업 (누적 방지용)
    if os.path.exists(SAVE_PATH):
        old_path = SAVE_PATH.replace(".pt", "_old.pt")
        import shutil
        shutil.copy(SAVE_PATH, old_path)
        print(f"📦 기존 가중치를 백업했습니다: {old_path}")

    results = model.train(
        data=DATA_DIR,
        epochs=epochs,
        imgsz=1280,
        batch=32,          # 런팟 상향 조정 (기존 2)
        project=OUTPUT_DIR,
        name="run",
        exist_ok=True,     # 기존 폴더 덮어쓰기 (run1, run2... 누적 방지)
        device=0,
        workers=8          # 리눅스 환경 상향 조정 (기존 0)
    )
    
    # 가중치 저장 - 실제 저장 경로를 동적으로 추적
    if hasattr(results, 'save_dir'):
        best_path = os.path.join(results.save_dir, "weights", "best.pt")
    else:
        best_path = os.path.join(OUTPUT_DIR, "run", "weights", "best.pt")

    if os.path.exists(best_path):
        os.makedirs(os.path.dirname(SAVE_PATH), exist_ok=True)
        shutil.copy(best_path, SAVE_PATH)
        print(f"[✓] 분류 모델이 저장되었습니다: {SAVE_PATH}")
    else:
        print(f"[Warning] Best model weight file not found at: {best_path}")

def evaluate_model():
    print(f"\n[Tire Classification] 상세 테스트 시작...")
    if not os.path.exists(SAVE_PATH):
        print(f"[Error] 학습된 모델이 없습니다: {SAVE_PATH}")
        return
    
    model = YOLO(SAVE_PATH)
    test_dir = os.path.join(DATA_DIR, "test")
    
    # Ensure output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    if not os.path.exists(test_dir):
        print(f"[Error] 테스트 데이터 디렉토리가 없습니다: {test_dir}")
        return

    # YOLOv8 top-1, top-5 metrics
    results_val = model.val(data=DATA_DIR, split='test', imgsz=1280)
    
    # Custom Detailed Metrics (Binary Classification Focus)
    y_true = []
    y_pred = []
    y_scores = [] # Probabilities for 'cracked' (Danger class)
    
    # class_names: {0: 'cracked', 1: 'normal'} - YOLO folders are alphabetical usually
    # But let's get it from the model
    names = model.names
    print(f"[Info] Identifed Classes: {names}")
    
    # Find index for 'cracked' (Danger class)
    danger_idx = next((k for k, v in names.items() if v == 'cracked'), 0)
    normal_idx = next((k for k, v in names.items() if v == 'normal'), 1)

    print(f"   Danger Class: {names[danger_idx]}, Normal Class: {names[normal_idx]}")

    import glob
    from PIL import Image

    for class_name in names.values():
        class_folder = os.path.join(test_dir, class_name)
        if not os.path.exists(class_folder): continue
        
        img_paths = glob.glob(os.path.join(class_folder, "*"))
        for img_path in img_paths:
            if not img_path.lower().endswith(('.png', '.jpg', '.jpeg')): continue
            
            res = model.predict(img_path, verbose=False)[0]
            probs = res.probs.data.cpu().numpy() # [prob_class0, prob_class1, ...]
            
            # True label
            true_label = danger_idx if class_name == names[danger_idx] else normal_idx
            y_true.append(true_label)
            
            # Pred label
            pred_label = np.argmax(probs)
            y_pred.append(pred_label)
            
            # Score for ROC (Probability of 'cracked')
            y_scores.append(probs[danger_idx])

    # 1. Classification Report
    print("\n" + "="*50)
    print("📋 Classification Report")
    print("="*50)
    print(classification_report(y_true, y_pred, target_names=[names[i] for i in range(len(names))]))

    # 2. Confusion Matrix
    cm = confusion_matrix(y_true, y_pred)
    plt.figure(figsize=(8, 6))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', 
                xticklabels=[names[i] for i in range(len(names))], 
                yticklabels=[names[i] for i in range(len(names))])
    plt.title("Tire Classification Confusion Matrix")
    plt.xlabel("Predicted Labels")
    plt.ylabel("True Labels")
    cm_path = os.path.join(OUTPUT_DIR, "confusion_matrix.png")
    plt.savefig(cm_path)
    print(f"📊 Confusion Matrix saved to: {cm_path}")

    # 3. ROC Curve & AUC
    fpr, tpr, thresholds = roc_curve(y_true, y_scores, pos_label=danger_idx)
    roc_auc = auc(fpr, tpr)
    
    plt.figure(figsize=(8, 6))
    plt.plot(fpr, tpr, color='darkorange', lw=2, label=f'ROC curve (area = {roc_auc:.2f})')
    plt.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--')
    plt.xlim([0.0, 1.0])
    plt.ylim([0.0, 1.05])
    plt.xlabel('False Positive Rate (FPR)')
    plt.ylabel('True Positive Rate (TPR)')
    plt.title('Tire Condition ROC Curve')
    plt.legend(loc="lower right")
    roc_path = os.path.join(OUTPUT_DIR, "roc_curve.png")
    plt.savefig(roc_path)
    print(f"📈 ROC Curve saved to: {roc_path}")
    print(f"🎯 AUC Score: {roc_auc:.4f}")
    print("="*50 + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tire Status Analysis Training")
    parser.add_argument("--mode", type=str, default="train", choices=["train", "test"])
    parser.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS)
    args = parser.parse_args()
    
    if args.mode == "train":
        train_model(args.epochs)
    elif args.mode == "test":
        evaluate_model()
