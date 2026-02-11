from ultralytics import YOLO
import argparse
import os
import platform
import glob
from pathlib import Path
import yaml

# =============================================================================
# [Configuration] RunPod Optimized Settings
# =============================================================================
BASE_MODEL = "yolo11m.pt"

# [Path Config] RunPod과 로컬 환경 자동 감지
RUNPOD_DATA_PATH = "/workspace/large_data"
LOCAL_DATA_PATH = "ai/data"
DATA_ROOT = RUNPOD_DATA_PATH if os.path.exists(RUNPOD_DATA_PATH) else LOCAL_DATA_PATH

# [Environment Config] 환경 변수로 제어 가능
DEFAULT_BATCH_SIZE = int(os.getenv("BATCH_SIZE", "16"))
DEFAULT_IMG_SIZE = int(os.getenv("IMG_SIZE", "640"))
WORKERS = 4 if platform.system() != "Windows" else 0

# RunPod 환경 감지
IS_RUNPOD = os.path.exists(RUNPOD_DATA_PATH)
CACHE = False  # RunPod에서는 cache 비활성화

def train_exterior_model(mode="train", epochs=10, batch_size=None, imgsz=None, workers=None, device=0):
    if batch_size is None: batch_size = DEFAULT_BATCH_SIZE
    if imgsz is None: imgsz = DEFAULT_IMG_SIZE
    if workers is None: workers = WORKERS

    # 1. Project & Data Setup
    project_path = os.path.join("ai", "weights", "exterior", "unified_v1")
    runs_path = os.path.join("runs", "detect", project_path)
    data_yaml = os.path.join(DATA_ROOT, "yolo", "exterior", "data.yaml")

    if not os.path.exists(BASE_MODEL):
        print(f"[Error] Base model not found: {BASE_MODEL}")
        print(f"Please download from: https://github.com/ultralytics/assets/releases/download/v8.1.0/{BASE_MODEL}")
        return

    if not os.path.exists(data_yaml):
        print(f"[Error] No data.yaml found at: {data_yaml}")
        return

    if mode == "train":
        print(f"\n🚀 Starting YOLOv11M Training for Exterior Damage")
        model = YOLO(BASE_MODEL)
        model.train(
            data=data_yaml,
            epochs=epochs,
            imgsz=imgsz,
            batch=batch_size,
            device=device,
            project=project_path,
            name="train",
            exist_ok=True,
            plots=True,
            cache=CACHE,
            workers=workers,
            amp=True
        )
        print(f"\n✅ Training Completed. Best weights: {project_path}/train/weights/best.pt")

    elif mode in ["val", "test"]:
        print(f"\n🔍 Starting YOLO Evaluation ({mode} mode)")

        best_weights = os.path.join(runs_path, "train", "weights", "best.pt")
        if not os.path.exists(best_weights):
            print(f"   ⚠️ [Error] Trained weights not found: {best_weights}")
            return

        model = YOLO(best_weights)

        # ------------------------
        # Step 1: Standard Validation
        # ------------------------
        metrics = model.val(
            data=data_yaml,
            split=mode,
            workers=0,
            project=project_path,
            name=f"val_{mode}",
            exist_ok=True
        )

        names = model.names
        maps = metrics.box.maps

        print("\n" + "="*70)
        print(f"🎯 Per-class mAP50-95 Results:")
        print("-" * 70)
        print(f"{'ID':<3} | {'Class Name':<30} | {'mAP50-95':<12}")
        print("-" * 70)
        for i, name in names.items():
            m_val = maps[i] if i < len(maps) else 0.0
            print(f"{i:<3} | {name:<30} | {m_val:<12.4f}")
        print("-" * 70)

        # ------------------------
        # Step 2: Severity Accuracy
        # ------------------------
        severity_map = {
            0: 2, 1: 2, 3: 2, 6: 2, 7: 2,  # Critical
            2: 1, 4: 1, 8: 1, 9: 1, 11: 1, 12: 1, 14: 1, 17: 1, 18: 1, 19: 1, 21: 1,  # Warning
            5: 0, 10: 0, 13: 0, 15: 0, 16: 0, 20: 0  # Normal
        }

        # data.yaml에서 이미지 폴더 읽기
        with open(data_yaml, 'r') as f:
            data_cfg = yaml.safe_load(f)
        img_dir = data_cfg.get(mode, None)
        if img_dir is not None:
            # data.yaml에 상대 경로로 되어 있으면 DATA_ROOT 기준 절대 경로로 변경
            img_dir = os.path.join(DATA_ROOT, "yolo", "exterior", img_dir)
        else:
            img_dir = os.path.join(DATA_ROOT, "yolo", "exterior", mode, "images")
        
        # 레이블 폴더도 절대 경로
        label_dir = os.path.join(DATA_ROOT, "yolo", "exterior", mode, "labels")

        print(f"🔥 Using img_dir: {img_dir}")
        print(f"🔥 Using label_dir: {label_dir}")

        img_files = [f for f in glob.glob(os.path.join(img_dir, "*")) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        print(f"   Processing {len(img_files)} images for severity mapping...")

        total_images = 0
        correct_severity = 0
        y_true_sev = []
        y_pred_sev = []

        for img_path in img_files:
            total_images += 1

            # Ground Truth Severity
            label_path = os.path.join(label_dir, Path(img_path).stem + ".txt")
            gt_sev = 0
            if os.path.exists(label_path):
                with open(label_path, 'r') as f:
                    for line in f:
                        parts = line.strip().split()
                        if not parts: continue
                        cls_id = int(parts[0])
                        gt_sev = max(gt_sev, severity_map.get(cls_id, 0))

            # Prediction Severity
            res = model.predict(img_path, verbose=False, conf=0.25)[0]
            pred_sev = 0
            if len(res.boxes) > 0:
                for box in res.boxes:
                    cls_id = int(box.cls[0])
                    pred_sev = max(pred_sev, severity_map.get(cls_id, 0))

            y_true_sev.append(gt_sev)
            y_pred_sev.append(pred_sev)
            if gt_sev == pred_sev:
                correct_severity += 1

        acc = correct_severity / total_images if total_images > 0 else 0

        print("\n" + "="*70)
        print(f"📊 Severity Accuracy Results:")
        print(f"   Total Images:      {total_images}")
        print(f"   Correct Severity:  {correct_severity}")
        print(f"   Accuracy:          {acc:.4f} (NORMAL/WARNING/CRITICAL)")
        print("-" * 70)
        print(f"📈 Results & Plots Saved at: {os.path.join(project_path, f'val_{mode}')}")
        print(f"   [Confusion Matrix] {os.path.join(project_path, f'val_{mode}', 'confusion_matrix.png')}")
        print("="*70 + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", type=str, default="train", choices=["train", "val", "test"])
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch", type=int, default=None)
    parser.add_argument("--imgsz", type=int, default=640, help="Image size")
    parser.add_argument("--workers", type=int, default=WORKERS, help="Dataloader workers")
    parser.add_argument("--device", type=int, default=0, help="CUDA device")
    args = parser.parse_args()

    train_exterior_model(
        mode=args.mode,
        epochs=args.epochs,
        batch_size=args.batch,
        imgsz=args.imgsz,
        workers=args.workers,
        device=args.device
    )
