# ai/app/services/router_service.py
"""
AI 분석 장면 분류 서비스 (Scene Router)

[역할]
1. 자동 장면 판별: 입력된 이미지가 차량의 어느 부분(엔진룸, 계기판, 외관, 타이어)인지 분류합니다.
2. 분석 경로 최적화: 분류 결과에 따라 가장 적합한 전문 분석 파이프라인으로 요청을 전달합니다.
3. MobileNetV3 기반: 가볍고 빠른 경량 모델을 사용하여 실시간 처리를 지원합니다.

[주요 기능]
- 이미지 장면 분류 (classify)
- 비정상 이미지 필터링 (Confidence 기반)
"""
import os
import time
import httpx
from enum import Enum
from typing import Optional, Union, Tuple
from io import BytesIO
from PIL import Image

# =============================================================================
# Scene Type Enum
# =============================================================================
class SceneType(str, Enum):
    """라우터가 분류하는 4가지 장면 타입"""
    SCENE_ENGINE = "SCENE_ENGINE"
    SCENE_DASHBOARD = "SCENE_DASHBOARD"
    SCENE_EXTERIOR = "SCENE_EXTERIOR"
    SCENE_TIRE = "SCENE_TIRE"


# =============================================================================
# Confidence Threshold (이 값 이하면 LLM Fallback)
# 초기 모델의 불안정성을 고려하여 0.85로 상향
CONFIDENCE_THRESHOLD = 0.85


# =============================================================================
# Router Service Class
# =============================================================================
class RouterService:
    """
    MobileNetV3-Small 기반 Scene Classifier
    
    Usage:
        router = RouterService()
        scene, confidence = await router.classify("https://s3.../image.jpg")
    """
    
    def __init__(self, model_path: str = None):
        """
        Args:
            model_path: MobileNetV3 가중치 경로. None이면 Mock 모드.
        """
        self.model = None
        self.mock_mode = True
        self.device = "cpu"
        
        # 기본 경로
        if model_path is None:
            model_path = os.path.join("ai", "weights", "router", "best.pt")
            # 윈도우/리눅스 호환성을 위해 절대경로로 변환 시도
            if not os.path.exists(model_path):
                # 다른 경로 시도 (app 기준으로 실행될 때)
                model_path = os.path.join(os.getcwd(), "ai", "weights", "router", "best.pt")
        
        # 모델 로드 시도
        if os.path.exists(model_path):
            try:
                self._load_model(model_path)
                self.mock_mode = False
                print(f"[Router] ✅ MobileNetV3 모델 로드 완료: {model_path}")
            except Exception as e:
                print(f"[Router] ⚠️ 모델 로드 실패, Mock 모드로 전환: {e}")
                self.mock_mode = True
        else:
            print(f"[Router] ⚠️ 가중치 없음, Mock 모드 활성화: {model_path}")
            self.mock_mode = True
    
    def _load_model(self, model_path: str):
        """MobileNetV3-Small 모델 로드"""
        import torch
        import torchvision.models as models
        
        # MobileNetV3-Small 구조 생성
        self.model = models.mobilenet_v3_small(weights=None)
        
        # 출력층을 4개 클래스로 수정
        num_classes = 4  # ENGINE, DASHBOARD, EXTERIOR, TIRE
        self.model.classifier[-1] = torch.nn.Linear(
            self.model.classifier[-1].in_features, 
            num_classes
        )
        
        # 가중치 로드
        state_dict = torch.load(model_path, map_location=self.device)
        self.model.load_state_dict(state_dict)
        self.model.eval()
        
        # 클래스 매핑 (훈련 데이터 폴더의 알파벳 순서와 정확히 일치해야 함)
        # 0: dashboard, 1: engine, 2: exterior, 3: tire
        self.class_names = [
            SceneType.SCENE_DASHBOARD,
            SceneType.SCENE_ENGINE,
            SceneType.SCENE_EXTERIOR,
            SceneType.SCENE_TIRE
        ]
    
    async def classify(self, image: Union[str, Image.Image]) -> Tuple[SceneType, float]:
        """
        이미지를 분류하여 장면 타입과 신뢰도 반환
        
        Args:
            image: S3 이미지 URL 또는 PIL Image 객체
            
        Returns:
            (SceneType, confidence): 분류된 장면과 신뢰도 (0.0~1.0)
        """
        start_time = time.time()
        
        # URL이 들어오면 내부적으로 로드 (하위 호환성)
        if isinstance(image, str):
            image_obj = await self._load_image_from_url(image)
            url_context = image
        else:
            image_obj = image
            url_context = "pre-loaded-image"
        
        if self.mock_mode:
            result = self._mock_classify(url_context)
        else:
            result = await self._real_classify(image_obj)
        
        elapsed = time.time() - start_time
        print(f"[Router] 분류 완료: {result[0].value} (신뢰도: {result[1]:.2f}, 시간: {elapsed:.3f}s)")
        
        return result
    
    def _mock_classify(self, image_url: str) -> tuple[SceneType, float]:
        """
        Mock 모드: URL 패턴 기반 규칙 분류
        (실제 모델 없이 테스트용)
        """
        url_lower = image_url.lower()
        
        # URL에 포함된 키워드로 분류
        if any(kw in url_lower for kw in ["engine", "hood", "motor", "엔진"]):
            return (SceneType.SCENE_ENGINE, 0.85)
        elif any(kw in url_lower for kw in ["dashboard", "warning", "계기판", "경고등"]):
            return (SceneType.SCENE_DASHBOARD, 0.85)
        elif any(kw in url_lower for kw in ["exterior", "bumper", "door", "외관", "범퍼"]):
            return (SceneType.SCENE_EXTERIOR, 0.85)
        elif any(kw in url_lower for kw in ["tire", "wheel", "타이어"]):
            return (SceneType.SCENE_TIRE, 0.85)
        else:
            # 기본값: 가장 일반적인 EXTERIOR로 분류
            return (SceneType.SCENE_EXTERIOR, 0.5)
    
    async def _real_classify(self, image: Image.Image) -> Tuple[SceneType, float]:
        """
        실제 MobileNetV3 모델로 분류 (pre-loaded image 사용)
        """
        import torch
        import torchvision.transforms as transforms
        
        # 2. 전처리 (MobileNetV3 표준)
        preprocess = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            )
        ])
        input_tensor = preprocess(image).unsqueeze(0)
        
        # 3. 추론
        with torch.no_grad():
            outputs = self.model(input_tensor)
            probabilities = torch.nn.functional.softmax(outputs, dim=1)
            confidence, predicted = torch.max(probabilities, 1)
        
        scene_type = self.class_names[predicted.item()]
        conf_value = confidence.item()
        
        return (scene_type, conf_value)
    
    async def _load_image_from_url(self, url: str) -> Image.Image:
        """S3 URL에서 이미지 로드"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            return Image.open(BytesIO(response.content)).convert("RGB")
    
    def is_low_confidence(self, confidence: float) -> bool:
        """신뢰도가 임계값 이하인지 확인 (LLM Fallback 여부 결정)"""
        return confidence < CONFIDENCE_THRESHOLD


# =============================================================================
# 전역 인스턴스 (Lazy Loading)
# =============================================================================
_router_instance: Optional[RouterService] = None

def get_router_service() -> RouterService:
    """RouterService 싱글톤 인스턴스 반환"""
    global _router_instance
    if _router_instance is None:
        _router_instance = RouterService()
    return _router_instance
