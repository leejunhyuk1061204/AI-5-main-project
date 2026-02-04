# ai/scripts/local_yolo_test.py
"""
YOLO 로컬 독립 테스트 도구 (Local YOLO Sandbox)

[역할]
1. 샌드박스 테스트: S3나 DB 등 외부 인프라 연결 없이, 로컬 이미지와 라벨만으로 YOLO 모델의 학습 및 추론을 즉시 테스트합니다.
2. 퀵 가이드: 새로운 데이터셋이 들어왔을 때, 모델이 정상적으로 학습되는지 소량의 데이터(예: 10장)로 빠르게 검증할 때 사용합니다.
3. 시각화: 추론 결과를 로컬 디렉토리(ai/runs/local_test)에 저장하여 감지 결과를 육안으로 확인합니다.

[사용법]

4. 추론:
   python ai/scripts/local_yolo_test.py --infer --image path/to/image.jpg

5. 결과 확인:
   ai/runs/local_test/에 결과 저장
"""
import argparse
import os
import shutil
from pathlib import Path

# =============================================================================
# Configuration
# =============================================================================
BASE_DIR = Path(__file__).parent.parent  # ai/
DATA_DIR = BASE_DIR / "data" / "engine_bay"
WEIGHTS_DIR = BASE_DIR / "weights" / "engine"
RESULTS_DIR = BASE_DIR / "runs" / "local_test"

# 최소 학습 설정 (10장용)
EPOCHS = 50
BATCH_SIZE = 4  # 이미지 10장이면 배치 4가 적당
IMG_SIZE = 640


def setup_local_data():
    """로컬 테스트용 디렉토리 구조 생성"""
    dirs = [
        DATA_DIR / "train" / "images",
        DATA_DIR / "train" / "labels",
        DATA_DIR / "valid" / "images",
        DATA_DIR / "valid" / "labels",
    ]
    
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    
    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    
    print(f"[✓] 디렉토리 생성 완료")
    print(f"\n📁 이미지를 다음 폴더에 넣으세요:")
    print(f"   학습: {DATA_DIR / 'train' / 'images'}")
    print(f"   검증: {DATA_DIR / 'valid' / 'images'}")
    print(f"\n📝 라벨을 다음 폴더에 넣으세요:")
    print(f"   학습: {DATA_DIR / 'train' / 'labels'}")
    print(f"   검증: {DATA_DIR / 'valid' / 'labels'}")


def check_data():
    """데이터 준비 상태 확인"""
    train_images = list((DATA_DIR / "train" / "images").glob("*"))
    train_labels = list((DATA_DIR / "train" / "labels").glob("*.txt"))
    valid_images = list((DATA_DIR / "valid" / "images").glob("*"))
    valid_labels = list((DATA_DIR / "valid" / "labels").glob("*.txt"))
    
    print("\n📊 데이터 현황:")
    print(f"   학습 이미지: {len(train_images)}개")
    print(f"   학습 라벨: {len(train_labels)}개")
    print(f"   검증 이미지: {len(valid_images)}개")
    print(f"   검증 라벨: {len(valid_labels)}개")
    
    if len(train_images) < 5:
        print("\n⚠️ 학습 이미지가 너무 적습니다! 최소 5장 이상 권장")
        return False
    
    if len(train_labels) < len(train_images):
        print("\n⚠️ 라벨 파일이 부족합니다! 모든 이미지에 라벨이 필요합니다")
        return False
    
    return True


def train_local(epochs: int = EPOCHS):
    """로컬 YOLO 학습"""
    print("\n" + "="*60)
    print(f"[YOLO] 로컬 학습 시작 (epochs={epochs})")
    print("="*60)
    
    if not check_data():
        print("\n❌ 데이터가 준비되지 않았습니다. --setup으로 디렉토리 생성 후 이미지를 넣어주세요.")
        return
    
    from ultralytics import YOLO
    
    # data.yaml 확인
    data_yaml = DATA_DIR / "data.yaml"
    if not data_yaml.exists():
        print(f"\n[Info] data.yaml이 없습니다. 기본 설정을 사용합니다.")
        # 기본 1클래스 (Battery) 생성
        create_simple_data_yaml()
    
    print(f"[Info] data.yaml: {data_yaml}")
    
    # 모델 로드 (yolov8n - 가장 가벼움)
    model = YOLO(str(BASE_DIR / "weights" / "yolov8n.pt"))
    
    # 학습 시작
    results = model.train(
        data=str(data_yaml),
        epochs=epochs,
        imgsz=IMG_SIZE,
        batch=BATCH_SIZE,
        device="0",  # GPU 사용 (CPU는 "cpu")
        project=str(RESULTS_DIR),
        name="train",
        exist_ok=True,
        patience=10,
        verbose=True,
    )
    
    # 베스트 모델 저장
    best_model = RESULTS_DIR / "train" / "weights" / "best.pt"
    if best_model.exists():
        target = WEIGHTS_DIR / "best.pt"
        shutil.copy(best_model, target)
        print(f"\n[✓] 모델 저장: {target}")
    
    print("\n✅ 학습 완료!")


def infer_local(image_path: str):
    """로컬 이미지로 추론"""
    print("\n" + "="*60)
    print(f"[YOLO] 추론: {image_path}")
    print("="*60)
    
    from ultralytics import YOLO
    from PIL import Image
    
    # 모델 로드
    model_path = WEIGHTS_DIR / "best.pt"
    if not model_path.exists():
        print(f"[Error] 학습된 모델이 없습니다: {model_path}")
        print("먼저 --train으로 학습을 실행하세요.")
        return
    
    model = YOLO(str(model_path))
    
    # 이미지 확인
    if not os.path.exists(image_path):
        print(f"[Error] 이미지를 찾을 수 없습니다: {image_path}")
        return
    
    # 추론
    results = model.predict(
        source=image_path,
        conf=0.25,
        save=True,
        project=str(RESULTS_DIR),
        name="infer",
        exist_ok=True,
    )
    
    # 결과 출력
    print("\n📋 감지 결과:")
    for r in results:
        for box in r.boxes:
            label_idx = int(box.cls[0])
            label_name = model.names[label_idx]
            conf = float(box.conf[0])
            bbox = box.xyxy[0].tolist()
            
            print(f"   - {label_name}: {conf:.2%} @ {[int(b) for b in bbox]}")
    
    if len(results[0].boxes) == 0:
        print("   (감지된 객체 없음)")
    
    print(f"\n[✓] 결과 이미지: {RESULTS_DIR / 'infer'}")


def create_simple_data_yaml():
    """간단한 data.yaml 생성 (1클래스: Battery)"""
    yaml_content = f"""# 로컬 테스트용 간단 설정
path: {DATA_DIR.as_posix()}
train: train/images
val: valid/images

# 1클래스만 테스트
names:
  0: Battery
"""
    
    yaml_path = DATA_DIR / "data.yaml"
    with open(yaml_path, 'w') as f:
        f.write(yaml_content)
    
    print(f"[✓] data.yaml 생성: {yaml_path}")


def create_sample_labels():
    """샘플 라벨 파일 생성 방법 안내"""
    print("""
📝 라벨 파일 생성 방법:

1. LabelImg 사용 (추천):
   pip install labelImg
   labelImg

2. 라벨 형식 (YOLO format):
   - 파일명: 이미지와 동일 (예: image1.jpg → image1.txt)
   - 내용: class_id x_center y_center width height
   - 좌표는 0~1 사이 (이미지 크기로 정규화)

3. 예시 (image1.txt):
   0 0.5 0.5 0.3 0.2
   ↑ ↑   ↑   ↑   ↑
   │ │   │   │   └── 높이 (20%)
   │ │   │   └────── 너비 (30%)
   │ │   └────────── y 중심 (50%)
   │ └────────────── x 중심 (50%)
   └──────────────── 클래스 ID (0=Battery)

4. Roboflow에서 라벨링 후 YOLO 포맷으로 내보내기도 가능
""")


# =============================================================================
# Main
# =============================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YOLO Local Test (No LLM/S3)")
    parser.add_argument("--setup", action="store_true", help="디렉토리 생성")
    parser.add_argument("--check", action="store_true", help="데이터 상태 확인")
    parser.add_argument("--train", action="store_true", help="학습 실행")
    parser.add_argument("--infer", action="store_true", help="추론 실행")
    parser.add_argument("--epochs", type=int, default=EPOCHS, help="학습 epochs")
    parser.add_argument("--image", type=str, help="추론할 이미지 경로")
    parser.add_argument("--label-help", action="store_true", help="라벨 생성 방법 안내")
    
    args = parser.parse_args()
    
    print("\n🔧 YOLO 로컬 테스트 스크립트 (LLM/S3 없음)")
    
    if args.setup:
        setup_local_data()
    
    elif args.check:
        check_data()
    
    elif args.train:
        train_local(epochs=args.epochs)
    
    elif args.infer:
        if not args.image:
            print("[Error] --image 경로를 지정하세요")
            print("예: python local_yolo_test.py --infer --image test.jpg")
        else:
            infer_local(args.image)
    
    elif args.label_help:
        create_sample_labels()
    
    else:
        print("""
사용법:
  1. 디렉토리 생성:
     python local_yolo_test.py --setup
     
  2. 라벨 생성 방법 확인:
     python local_yolo_test.py --label-help
     
  3. 데이터 상태 확인:
     python local_yolo_test.py --check
     
  4. 학습 (50 epochs):
     python local_yolo_test.py --train --epochs 50
     
  5. 추론:
     python local_yolo_test.py --infer --image path/to/image.jpg
""")
