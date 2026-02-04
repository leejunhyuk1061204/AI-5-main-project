# ai/scripts/train_anomaly.py
"""
PatchCore 엔진 부품 이상 탐지 학습 도구 (Anomaly Trainer)

[역할]
1. 미세 결함 학습: 정상(Good) 데이터만을 학습하여 엔진 부품의 미세한 균열, 누유, 부식을 잡아내는 PatchCore 모델을 생성합니다.
2. 부품별 모델 생성: 오일 캡, 배터리 등 26종 개별 부품에 최적화된 이상 탐지 가중치를 각각 생성합니다.
3. 고성능 아키텍처: RTX 4090 환경에 최적화된 배치 사이즈와 백본(WideResNet50) 설정을 제공합니다.

[사용법]
- 특정 부품 학습: python ai/scripts/train_anomaly.py --part Battery
- 전체 부품 학습: python ai/scripts/train_anomaly.py --all
- 디렉토리 구조 생성: python ai/scripts/train_anomaly.py --mode setup
"""
import argparse
import os
import sys
from pathlib import Path

# =============================================================================
# Configuration
# =============================================================================
BASE_DIR = Path(__file__).parent.parent  # ai/
DATA_DIR = BASE_DIR / "data" / "anomaly"
WEIGHTS_DIR = BASE_DIR / "weights" / "anomaly"
RESULTS_DIR = BASE_DIR / "runs" / "anomaly"

# 엔진룸 부품 목록 (26개 + engine_bay 통합)
ENGINE_PARTS = [
    "Inverter_Coolant_Reservoir", "Battery", "Radiator_Cap",
    "Windshield_Wiper_Fluid", "Fuse_Box", "Power_Steering_Reservoir",
    "Brake_Fluid", "Engine_Oil_Fill_Cap", "Engine_Oil_Dip_Stick",
    "Air_Filter_Cover", "ABS_Unit", "Alternator", "Engine_Coolant_Reservoir",
    "Radiator", "Engine_Cover", "Cold_Air_Intake",
    "Transmission_Oil_Dip_Stick",
    "Intercooler_Coolant_Reservoir", "Oil_Filter_Housing", "ATF_Oil_Reservoir",
    "Secondary_Coolant_Reservoir", "Oil_Filter",
    "engine_bay"  # 전체 엔진룸 통합 학습용
]

# 데이터 경로 매핑 (engine_bay는 다른 구조 사용)
DATA_PATH_MAP = {
    "engine_bay": BASE_DIR / "data" / "engine_bay"
}

# Training Config (RTX 4090 최적화)
IMAGE_SIZE = 224
BATCH_SIZE = 32
BACKBONE = "wide_resnet50_2"  # PatchCore 권장
NUM_WORKERS = 8

# =============================================================================
# 디렉토리 생성
# =============================================================================
def ensure_dirs():
    """필요한 디렉토리 구조 생성"""
    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # 각 부품별 데이터 디렉토리 생성
    for part in ENGINE_PARTS:
        (DATA_DIR / part / "train" / "good").mkdir(parents=True, exist_ok=True)
        (DATA_DIR / part / "test" / "good").mkdir(parents=True, exist_ok=True)
        (DATA_DIR / part / "test" / "defect").mkdir(parents=True, exist_ok=True)
    
    print(f"[✓] 디렉토리 구조 생성 완료: {DATA_DIR}")


# =============================================================================
# PatchCore 학습 (anomalib 사용)
# =============================================================================
def train_patchcore(part_name: str):
    """단일 부품에 대한 PatchCore 모델 학습"""
    print("\n" + "="*60)
    print(f"[PatchCore] Training for: {part_name}")
    print("="*60)
    
    try:
        from anomalib.data import Folder
        from anomalib.models import Patchcore
        from anomalib.engine import Engine
        from anomalib.deploy import ExportType
    except ImportError:
        print("[Error] anomalib이 설치되지 않았습니다.")
        print("        pip install anomalib")
        return False
    
    # engine_bay는 다른 경로 구조 사용
    if part_name == "engine_bay":
        data_path = DATA_PATH_MAP.get(part_name, DATA_DIR / part_name)
        train_dir = data_path / "train" / "images"
    else:
        data_path = DATA_DIR / part_name
        train_dir = data_path / "train" / "good"
    
    # 데이터 확인
    train_images = list(train_dir.glob("*.jpg")) + list(train_dir.glob("*.png"))
    
    if len(train_images) < 10:
        print(f"[Warning] {part_name}: 학습 이미지가 부족합니다 ({len(train_images)}개)")
        print(f"         최소 10장 이상 권장 (이상적: 100~500장)")
        return False
    
    print(f"[Info] 학습 이미지: {len(train_images)}개")
    
    # 데이터 모듈 생성
    datamodule = Folder(
        name=part_name,
        root=str(data_path),
        normal_dir="train/good",
        abnormal_dir="test/defect",
        normal_test_dir="test/good",
        image_size=IMAGE_SIZE,
        train_batch_size=BATCH_SIZE,
        eval_batch_size=BATCH_SIZE,
        num_workers=NUM_WORKERS,
    )
    
    # PatchCore 모델 생성
    model = Patchcore(
        backbone=BACKBONE,
        layers=["layer2", "layer3"],  # 중간 레이어 특징 추출
        coreset_sampling_ratio=0.1,   # 메모리 효율
    )
    
    # 학습 엔진
    engine = Engine(
        default_root_dir=str(RESULTS_DIR / part_name),
        max_epochs=1,  # PatchCore는 epoch 1로 충분
        devices=1,
        accelerator="gpu",
    )
    
    # 학습
    print("[Info] 학습 시작...")
    engine.fit(datamodule=datamodule, model=model)
    
    # 테스트
    print("[Info] 테스트 중...")
    test_results = engine.test(datamodule=datamodule, model=model)
    
    # 모델 저장
    save_path = WEIGHTS_DIR / part_name
    save_path.mkdir(parents=True, exist_ok=True)
    
    engine.export(
        model=model,
        export_type=ExportType.TORCH,
        export_root=str(save_path),
    )
    
    print(f"\n[✓] 모델 저장 완료: {save_path}")
    return True


# =============================================================================
# 간단한 PatchCore 구현 (anomalib 없이)
# =============================================================================
def train_patchcore_simple(part_name: str):
    """
    anomalib 없이 간단한 PatchCore 구현
    (anomalib 설치가 어려운 환경용)
    """
    print("\n" + "="*60)
    print(f"[Simple PatchCore] Training for: {part_name}")
    print("="*60)
    
    try:
        import torch
        import torch.nn as nn
        from torchvision import models, transforms
        from torch.utils.data import DataLoader, Dataset
        from PIL import Image
        import numpy as np
        from sklearn.neighbors import NearestNeighbors
        import pickle
    except ImportError as e:
        print(f"[Error] 필수 라이브러리가 없습니다: {e}")
        return False
    
    # engine_bay는 다른 경로 구조 사용
    if part_name == "engine_bay":
        data_path = DATA_PATH_MAP.get(part_name, DATA_DIR / part_name)
        train_dir = data_path / "train" / "images"
    else:
        data_path = DATA_DIR / part_name
        train_dir = data_path / "train" / "good"
    
    train_images = list(train_dir.glob("*.jpg")) + list(train_dir.glob("*.png"))
    
    if len(train_images) < 10:
        print(f"[Warning] {part_name}: 학습 이미지가 부족합니다 ({len(train_images)}개)")
        return False
    
    print(f"[Info] 학습 이미지: {len(train_images)}개")
    
    # 디바이스 설정
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[Info] Device: {device}")
    
    # Feature Extractor (ResNet50)
    # weights 파라미터 사용 (pretrained는 deprecated)
    backbone = models.wide_resnet50_2(weights='IMAGENET1K_V1').to(device)
    backbone.eval()
    
    # Hook for intermediate features
    features = {}
    def hook_fn(module, input, output):
        features['layer2'] = output
    
    backbone.layer2.register_forward_hook(hook_fn)
    
    # Transform
    transform = transforms.Compose([
        transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])
    
    # Feature 추출
    print("[Info] Feature 추출 중...")
    all_features = []
    
    with torch.no_grad():
        for img_path in train_images:
            img = Image.open(img_path).convert("RGB")
            img_tensor = transform(img).unsqueeze(0).to(device)
            
            _ = backbone(img_tensor)
            feat = features['layer2'].cpu().numpy()
            
            # Flatten spatial dimensions
            b, c, h, w = feat.shape
            feat = feat.reshape(b, c, -1).transpose(0, 2, 1).reshape(-1, c)
            all_features.append(feat)
    
    all_features = np.vstack(all_features)
    print(f"[Info] Feature Bank 크기: {all_features.shape}")
    
    # Coreset Sampling (메모리 효율)
    n_samples = min(10000, len(all_features))
    indices = np.random.choice(len(all_features), n_samples, replace=False)
    coreset = all_features[indices]
    print(f"[Info] Coreset 크기: {coreset.shape}")
    
    # KNN 모델 학습
    knn = NearestNeighbors(n_neighbors=9, metric='euclidean')
    knn.fit(coreset)
    
    # 모델 저장
    save_path = WEIGHTS_DIR / part_name
    save_path.mkdir(parents=True, exist_ok=True)
    
    model_data = {
        'coreset': coreset,
        'knn': knn,
        'backbone': 'wide_resnet50_2',
        'image_size': IMAGE_SIZE,
    }
    
    with open(save_path / "patchcore_simple.pkl", 'wb') as f:
        pickle.dump(model_data, f)
    
    print(f"\n[✓] 모델 저장 완료: {save_path / 'patchcore_simple.pkl'}")
    return True


# =============================================================================
# Main
# =============================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PatchCore Anomaly Detection Training")
    parser.add_argument("--part", type=str, default=None,
                        help="학습할 부품명 (예: Battery)")
    parser.add_argument("--all", action="store_true",
                        help="모든 부품 학습")
    parser.add_argument("--mode", type=str, default="train",
                        choices=["train", "test", "setup"],
                        help="실행 모드")
    parser.add_argument("--simple", action="store_true",
                        help="간단한 구현 사용 (anomalib 없이)")
    
    args = parser.parse_args()
    
    print("\n🔧 PatchCore Anomaly Detection Training Script")
    
    if args.mode == "setup":
        ensure_dirs()
        print("\n[Info] 데이터 준비:")
        print(f"  1. 각 부품의 정상 이미지를 다음 경로에 넣으세요:")
        print(f"     {DATA_DIR}/[part_name]/train/good/")
        print(f"  2. 이상 이미지(선택):")
        print(f"     {DATA_DIR}/[part_name]/test/defect/")
        sys.exit(0)
    
    ensure_dirs()
    
    train_fn = train_patchcore_simple if args.simple else train_patchcore
    
    if args.all:
        print(f"\n[Info] 전체 부품 학습 ({len(ENGINE_PARTS)}개)")
        success = 0
        for part in ENGINE_PARTS:
            if train_fn(part):
                success += 1
        print(f"\n[✓] 완료: {success}/{len(ENGINE_PARTS)} 부품 학습됨")
    
    elif args.part:
        if args.part not in ENGINE_PARTS:
            print(f"[Error] 알 수 없는 부품: {args.part}")
            print(f"[Info] 가능한 부품: {', '.join(ENGINE_PARTS[:5])}...")
            sys.exit(1)
        train_fn(args.part)
    
    else:
        print("[Error] --part 또는 --all 옵션을 지정하세요")
        print("예: python train_anomaly.py --part Battery")
        sys.exit(1)
    
    print("\n✅ 완료!")
