# ai/app/services/anomaly_service.py
"""
PatchCore 기반 이상 탐지 서비스 (Anomaly Detection Core)

[역할]
1. 미세 결함 탐지: 정상 데이터만으로 학습된 모델이 새로운 이미지에서 비정상(Anomaly) 패턴을 찾아냅니다.
2. 부품별 특화 모델: 엔진룸의 각 부품별로 최적화된 임계값(Threshold)과 가중치를 관리합니다.
3. 히트맵 데이터 생성: 결함의 위치와 정도를 수치화된 맵(Heatmap)으로 반환합니다.

[주요 기능]
- 모델 로드 및 관리 (_load_models)
- 실제 이상 탐지 추론 (_real_detect)
- 학습 전 시뮬레이션을 위한 Mock 모드 (_mock_detect)
"""
import torch
import numpy as np
from PIL import Image
from typing import Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path
import json
import random
import pickle

from torchvision import transforms, models


@dataclass
class AnomalyResult:
    score: float
    is_anomaly: bool
    heatmap: np.ndarray
    threshold: float


class AnomalyDetector:
    def __init__(
        self,
        config_path: str = "ai/config/anomaly_thresholds.json",
        weights_dir: str = None  # None이면 자동 계산
    ):
        self.thresholds = self._load_thresholds(config_path)
        
        # 절대경로로 변환 (실행 위치 무관)
        base_dir = Path(__file__).parent.parent.parent
        if weights_dir is None:
            self.weights_dir = base_dir / "weights" / "anomaly"
        else:
            self.weights_dir = Path(weights_dir)
        
        # config_path가 상대경로인 경우 처리
        self.config_path = base_dir / config_path.replace("ai/", "") if "ai/" in config_path else Path(config_path)
        self.thresholds = self._load_thresholds(str(self.config_path))
        
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        self.models = self._load_models()
        
        if self.models:
            self.backbone = self._load_backbone()
            self.transform = self._get_transform()
            print(f"[AnomalyDetector] 실제 모델 모드 (Device: {self.device})")
        else:
            self.backbone = None
            self.transform = None
            print("[AnomalyDetector] Mock 모드. 학습 필요:")
            print("  python ai/scripts/train_anomaly.py --part engine_bay --simple")

    def _load_thresholds(self, path: str) -> Dict[str, float]:
        """부품별 Threshold 설정 로드"""
        try:
            # 상대경로 → 절대경로 변환
            abs_path = Path(__file__).parent.parent.parent / path.replace("ai/", "")
            if not abs_path.exists():
                abs_path = Path(path)
            with open(abs_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"[Warning] Threshold config not found. Using defaults.")
            return {"default": 0.7}

    def _load_models(self) -> Dict[str, Any]:
        """학습된 모델 로드 (pkl 파일)"""
        models_dict = {}
        if not self.weights_dir.exists():
            print(f"[Warning] Weights not found: {self.weights_dir}")
            return models_dict
        
        for part_dir in self.weights_dir.iterdir():
            if part_dir.is_dir():
                pkl_path = part_dir / "patchcore_simple.pkl"
                if pkl_path.exists():
                    try:
                        with open(pkl_path, 'rb') as f:
                            models_dict[part_dir.name.lower()] = pickle.load(f)
                        print(f"[Model Loaded] {part_dir.name}")
                    except Exception as e:
                        print(f"[Error] Load failed {pkl_path}: {e}")
        
        # engine_bay 통합 모델을 general fallback으로 사용
        if "engine_bay" in models_dict:
            models_dict["_general"] = models_dict["engine_bay"]
        
        return models_dict

    def _load_backbone(self):
        """Feature 추출용 backbone 로드 (deprecated pretrained 수정)"""
        backbone = models.wide_resnet50_2(weights='IMAGENET1K_V1').to(self.device)
        backbone.eval()
        
        # Hook for intermediate features
        self.features = {}
        def hook_fn(module, input, output):
            self.features['layer2'] = output
        
        backbone.layer2.register_forward_hook(hook_fn)
        return backbone

    def _get_transform(self):
        """이미지 전처리 Transform"""
        return transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ])

    def get_threshold(self, part_name: str) -> float:
        """부품별 Threshold 반환 (대소문자 무시, 부분 일치)"""
        key = part_name.lower()
        if key in self.thresholds:
            return self.thresholds[key]
        for k, v in self.thresholds.items():
            if k in key:
                return v
        return self.thresholds.get("default", 0.7)

    async def detect(self, crop_image: Image.Image, part_name: str) -> AnomalyResult:
        """
        이상 탐지 수행
        - 부품별 모델 → General 모델 → Mock 순서로 시도
        """
        threshold = self.get_threshold(part_name)
        key = part_name.lower()
        
        # 부품별 모델 → General 모델 → Mock 순서
        if key in self.models:
            return self._real_detect(crop_image, key, threshold)
        if "_general" in self.models:
            return self._real_detect(crop_image, "_general", threshold)
        return self._mock_detect(threshold)

    def _real_detect(self, crop_image: Image.Image, model_key: str, threshold: float) -> AnomalyResult:
        """실제 PatchCore 추론"""
        model_data = self.models[model_key]
        knn = model_data['knn']
        
        # 이미지 전처리
        img_tensor = self.transform(crop_image.convert("RGB")).unsqueeze(0).to(self.device)
        
        # Feature 추출
        with torch.no_grad():
            _ = self.backbone(img_tensor)
            feat = self.features['layer2'].cpu().numpy()
            b, c, h, w = feat.shape
            feat = feat.reshape(b, c, -1).transpose(0, 2, 1).reshape(-1, c)
        
        # KNN 거리 계산 (이상 점수)
        distances, _ = knn.kneighbors(feat)
        anomaly_scores = distances.mean(axis=1)
        
        # Score 정규화 (TODO: 실제 데이터로 threshold 튜닝 필요)
        score = min(anomaly_scores.max() / 10.0, 1.0)
        
        # Heatmap 생성 (feature map 크기 → 224x224 resize)
        heatmap = anomaly_scores.reshape(h, w)
        heatmap = (heatmap - heatmap.min()) / (heatmap.max() - heatmap.min() + 1e-8)
        heatmap = np.array(Image.fromarray((heatmap * 255).astype(np.uint8)).resize((224, 224))) / 255.0
        
        return AnomalyResult(
            score=score,
            is_anomaly=score > threshold,
            heatmap=heatmap.astype(np.float32),
            threshold=threshold
        )

    def _mock_detect(self, threshold: float) -> AnomalyResult:
        """Mock 모드 (학습 전 테스트용)"""
        mock_score = random.uniform(0.2, 0.9)
        
        # Heatmap Mock with Gaussian hotspot
        mock_heatmap = np.random.rand(224, 224).astype(np.float32)
        cx, cy = 112, 112
        x, y = np.meshgrid(np.arange(224), np.arange(224))
        gaussian = np.exp(-((x - cx)**2 + (y - cy)**2) / (60.0**2))
        mock_heatmap = 0.5 * mock_heatmap + 0.5 * gaussian
        
        return AnomalyResult(
            score=mock_score,
            is_anomaly=mock_score > threshold,
            heatmap=mock_heatmap,
            threshold=threshold
        )
