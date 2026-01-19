# ai/app/services/anomaly_service.py
import torch
import numpy as np
from PIL import Image
from typing import Dict, Optional
from dataclasses import dataclass
import os
import json
import random

@dataclass
class AnomalyResult:
    score: float
    is_anomaly: bool
    heatmap: np.ndarray
    threshold: float

class AnomalyDetector:
    def __init__(self, config_path: str = "ai/config/anomaly_thresholds.json"):
        self.thresholds = self._load_thresholds(config_path)
        # 추후 실제 모델 로딩 로직 추가: self.models = {}

    def _load_thresholds(self, path: str) -> Dict[str, float]:
        """부품별 Threshold 설정 로드"""
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"[Warning] Threshold config not found at {path}. Using defaults.")
            return {"default": 0.7}

    def get_threshold(self, part_name: str) -> float:
        """
        부품별 Threshold 반환. 
        대소문자 무시 (Lower casing) 및 부분 일치 검색으로 유연하게 처리.
        """
        key = part_name.lower()
        # 정확히 일치하는 키가 있으면 반환
        if key in self.thresholds:
            return self.thresholds[key]
        
        # 키에 포함된 단어로 검색 (예: 'engine_battery' -> 'battery')
        for k, v in self.thresholds.items():
            if k in key:
                return v
                
        # Fallback (보수적 적용)
        return self.thresholds.get("default", 0.7)

    async def detect(
        self,
        crop_image: Image.Image,
        part_name: str
    ) -> AnomalyResult:
        """
        이상 탐지 수행 (Mock Mode)
        
        실제 PatchCore 구현 시:
        1. crop_image -> transforms -> tensor
        2. model(tensor) -> score, heatmap
        """
        threshold = self.get_threshold(part_name)

        # =========================================================
        # [MOCK LOGIC]
        # 랜덤하게 점수를 생성하여 파이프라인 테스트
        # 0.2 ~ 0.9 사이 랜덤 점수 생성
        # =========================================================
        mock_score = random.uniform(0.2, 0.9)
        
        # Heatmap Mock (224x224)
        # 실제 모델 출력: [224, 224] float numpy array (0~1 normalized)
        # 연결성 테스트를 위해 그럴싸한 Gaussian Noise 생성
        mock_heatmap = np.random.rand(224, 224).astype(np.float32)
        
        # 중앙부에 가짜 Hotspot 생성 (LLM 테스트용 가이드)
        # (실제 학습 전에는 무의미하지만, 이미지 파이프라인 무결성 확인용)
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
