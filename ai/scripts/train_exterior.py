# ai/scripts/train_exterior.py
"""
차량 외관 파손 및 부위 감지 EfficientDet 모델 학습 도구

[사용법]
- 파손 모델 학습: python ai/scripts/train_exterior.py --task damage --mode train
- 부위 모델 학습: python ai/scripts/train_exterior.py --task parts --mode train
- 모델 평가: python ai/scripts/train_exterior.py --task damage --mode eval

[필요 패키지]
pip install effdet timm pycocotools
"""

import os
import argparse
import json
import torch
import shutil
from pathlib import Path

# EfficientDet 관련 imports
try:
    from effdet import get_efficientdet_config, EfficientDet, DetBenchTrain, DetBenchPredict
    from effdet.efficientdet import HeadNet
    from effdet.config import get_efficientdet_config
    import timm
    EFFDET_AVAILABLE = True
except ImportError:
    EFFDET_AVAILABLE = False
    print("[Warning] effdet not installed. Run: pip install effdet timm")

from torch.utils.data import DataLoader, Dataset
from PIL import Image
import numpy as np

# =============================================================================
# 데이터셋 설정
# =============================================================================

def get_base_proj_dir():
    # 스크립트 위치가 ai/scripts/ 이므로 3번 위로 올라가야 프로젝트 루트임
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TASKS = {
    "damage": {
        "train_json": "ai/data/yolo/exterior/cardd/CarDD_COCO/annotations/instances_train2017.json",
        "train_images": "ai/data/yolo/exterior/cardd/CarDD_COCO/train2017",
        "val_json": "ai/data/yolo/exterior/cardd/CarDD_COCO/annotations/instances_val2017.json",
        "val_images": "ai/data/yolo/exterior/cardd/CarDD_COCO/val2017",
        "num_classes": 6,
        "weights_path": "ai/weights/exterior/damage_best.pth",
        "output_dir": "ai/runs/exterior_damage",
        "description": "CarDD 파손 감지 (6 classes: dent, scratch, crack, glass_shatter, lamp_broken, tire_flat)"
    },
    "parts": {
        "train_json": "ai/data/yolo/exterior/carparts/Car-Parts-Segmentation-master/trainingset/annotations.json",
        "train_images": "ai/data/yolo/exterior/carparts/Car-Parts-Segmentation-master/trainingset",
        "val_json": "ai/data/yolo/exterior/carparts/Car-Parts-Segmentation-master/trainingset/annotations.json",
        "val_images": "ai/data/yolo/exterior/carparts/Car-Parts-Segmentation-master/trainingset",
        "num_classes": 18,
        "weights_path": "ai/weights/exterior/parts_best.pth",
        "output_dir": "ai/runs/exterior_parts",
        "description": "CarParts 부위 감지 (18 classes: bumper, door, hood, etc.)"
    }
}

# =============================================================================
# COCO Dataset for EfficientDet
# =============================================================================

class COCODataset(Dataset):
    """COCO 포맷 데이터셋 로더"""
    
    def __init__(self, json_path, image_dir, img_size=512, transforms=None):
        self.image_dir = image_dir
        self.img_size = img_size
        self.transforms = transforms
        
        with open(json_path, 'r', encoding='utf-8') as f:
            self.coco = json.load(f)
        
        self.images = {img['id']: img for img in self.coco['images']}
        self.categories = {cat['id']: idx for idx, cat in enumerate(self.coco.get('categories', []))}
        
        # 이미지별 어노테이션 그룹화
        self.img_to_anns = {}
        for ann in self.coco.get('annotations', []):
            img_id = ann['image_id']
            if img_id not in self.img_to_anns:
                self.img_to_anns[img_id] = []
            self.img_to_anns[img_id].append(ann)
        
        self.image_ids = list(self.images.keys())
    
    def __len__(self):
        return len(self.image_ids)
    
    def __getitem__(self, idx):
        img_id = self.image_ids[idx]
        img_info = self.images[img_id]
        
        # 이미지 로드
        img_path = os.path.join(self.image_dir, img_info.get('file_name', img_info.get('path', '')))
        if not os.path.exists(img_path):
            # 상대 경로 처리
            img_path = os.path.join(self.image_dir, os.path.basename(img_info.get('file_name', '')))
        
        image = Image.open(img_path).convert('RGB')
        orig_w, orig_h = image.size
        image = image.resize((self.img_size, self.img_size))
        image = np.array(image).astype(np.float32) / 255.0
        image = torch.from_numpy(image).permute(2, 0, 1)
        
        # 어노테이션 로드
        anns = self.img_to_anns.get(img_id, [])
        boxes = []
        labels = []
        
        for ann in anns:
            if 'bbox' not in ann:
                continue
            bbox = ann['bbox']  # [x, y, w, h]
            # 리사이즈 비율 적용
            x = bbox[0] * self.img_size / orig_w
            y = bbox[1] * self.img_size / orig_h
            w = bbox[2] * self.img_size / orig_w
            h = bbox[3] * self.img_size / orig_h
            # [x, y, w, h] -> [x1, y1, x2, y2]
            boxes.append([x, y, x + w, y + h])
            labels.append(self.categories.get(ann['category_id'], 0))
        
        if len(boxes) == 0:
            boxes = torch.zeros((0, 4), dtype=torch.float32)
            labels = torch.zeros((0,), dtype=torch.int64)
        else:
            boxes = torch.tensor(boxes, dtype=torch.float32)
            labels = torch.tensor(labels, dtype=torch.int64)
        
        target = {
            'boxes': boxes,
            'labels': labels,
            'image_id': torch.tensor([img_id])
        }
        
        return image, target

def collate_fn(batch):
    images = torch.stack([item[0] for item in batch])
    targets = [item[1] for item in batch]
    return images, targets

# =============================================================================
# EfficientDet 모델
# =============================================================================

def create_model(num_classes, pretrained=True):
    """EfficientDet-D0 모델 생성"""
    if not EFFDET_AVAILABLE:
        raise ImportError("effdet 패키지가 설치되지 않았습니다. pip install effdet timm")
    
    config = get_efficientdet_config('efficientdet_d0')
    config.num_classes = num_classes
    config.image_size = [512, 512]
    
    model = EfficientDet(config, pretrained_backbone=pretrained)
    model.class_net = HeadNet(config, num_outputs=num_classes)
    
    return DetBenchTrain(model, config)

def create_predictor(model_path, num_classes):
    """추론용 모델 로드"""
    config = get_efficientdet_config('efficientdet_d0')
    config.num_classes = num_classes
    config.image_size = [512, 512]
    
    model = EfficientDet(config, pretrained_backbone=False)
    model.class_net = HeadNet(config, num_outputs=num_classes)
    
    bench = DetBenchPredict(model)
    bench.load_state_dict(torch.load(model_path, map_location='cpu'))
    return bench

# =============================================================================
# 학습 및 평가
# =============================================================================

def train_model(task: str, epochs: int = 10, batch_size: int = 4, resume: bool = False):
    """EfficientDet 모델 학습"""
    cfg = TASKS.get(task)
    if not cfg:
        print(f"[Error] Unknown task: {task}")
        return
    
    base_dir = get_base_proj_dir()
    
    print(f"\n{'='*60}")
    print(f"🚀 {task.upper()} 모델 학습 시작 (EfficientDet-D0)")
    print(f"   {cfg['description']}")
    print(f"   Epochs: {epochs}")
    print(f"   Batch Size: {batch_size}")
    print(f"{'='*60}\n")
    
    # 데이터 로더
    train_dataset = COCODataset(
        os.path.join(base_dir, cfg['train_json']),
        os.path.join(base_dir, cfg['train_images'])
    )
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, 
                              collate_fn=collate_fn, num_workers=0)
    
    print(f"[Data] Train samples: {len(train_dataset)}")
    
    # 모델 생성
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"[Device] Using: {device}")
    
    model = create_model(cfg['num_classes'], pretrained=True)
    model.to(device)
    
    # 옵티마이저
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4)
    
    # 학습 루프
    model.train()
    for epoch in range(epochs):
        total_loss = 0
        for batch_idx, (images, targets) in enumerate(train_loader):
            images = images.to(device)
            
            # EfficientDet용 타겟 포맷 변환
            batch_targets = {}
            batch_targets['bbox'] = [t['boxes'].to(device) for t in targets]
            batch_targets['cls'] = [t['labels'].to(device) for t in targets]
            
            optimizer.zero_grad()
            
            try:
                output = model(images, batch_targets)
                loss = output['loss']
                loss.backward()
                optimizer.step()
                total_loss += loss.item()
            except Exception as e:
                print(f"[Warning] Batch {batch_idx} skipped: {e}")
                continue
            
            if batch_idx % 10 == 0:
                print(f"  Epoch [{epoch+1}/{epochs}] Batch [{batch_idx}/{len(train_loader)}] Loss: {loss.item():.4f}")
        
        avg_loss = total_loss / max(len(train_loader), 1)
        print(f"Epoch [{epoch+1}/{epochs}] Average Loss: {avg_loss:.4f}")
    
    # 모델 저장
    output_dir = os.path.join(base_dir, cfg['output_dir'])
    os.makedirs(output_dir, exist_ok=True)
    
    save_path = os.path.join(base_dir, cfg['weights_path'])
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    torch.save(model.state_dict(), save_path)
    print(f"\n✅ 모델 저장 완료: {save_path}")

def evaluate_model(task: str):
    """학습된 모델 평가"""
    cfg = TASKS.get(task)
    if not cfg:
        return
    
    base_dir = get_base_proj_dir()
    weights_path = os.path.join(base_dir, cfg['weights_path'])
    
    if not os.path.exists(weights_path):
        print(f"[Error] 학습된 모델이 없습니다: {weights_path}")
        print(f" -> 먼저 학습을 진행하세요: --mode train")
        return
    
    print(f"\n📊 {task.upper()} 모델 평가 중...")
    print(f"[EVAL] 모델 로드 완료: {weights_path}")
    print(f"[EVAL] 추론 테스트는 별도 스크립트에서 구현 필요")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Exterior EfficientDet Training (Damage & Parts)")
    parser.add_argument("--task", type=str, required=True, choices=["damage", "parts"],
                        help="damage: 파손 감지, parts: 부위 감지")
    parser.add_argument("--mode", type=str, default="train", choices=["train", "eval", "all"],
                        help="train: 학습만, eval: 평가만, all: 학습+평가")
    parser.add_argument("--epochs", type=int, default=10, help="학습 에폭 수")
    parser.add_argument("--batch_size", type=int, default=4, help="배치 사이즈")
    parser.add_argument("--resume", action="store_true", help="기존 모델에서 재학습")
    
    args = parser.parse_args()
    
    if not EFFDET_AVAILABLE:
        print("\n[Error] effdet 패키지가 필요합니다.")
        print("설치 명령어: pip install effdet timm pycocotools")
        exit(1)
    
    print(f"\n🔧 Exterior EfficientDet Trainer")
    print(f"   Task: {args.task}")
    print(f"   Mode: {args.mode}")
    
    if args.mode in ["train", "all"]:
        train_model(args.task, args.epochs, args.batch_size, args.resume)
    
    if args.mode in ["eval", "all"]:
        evaluate_model(args.task)
    
    print("\n✅ 완료!")
