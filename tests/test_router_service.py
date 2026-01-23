# tests/test_router_service.py
"""
Router Service 유닛 테스트

[테스트 케이스]
1. Mock 모드 동작 확인
2. 분류 결과 타입 검증
3. 신뢰도 임계값 체크
4. 추론 지연시간 확인
"""
import pytest
import asyncio
import time
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ai.app.services.router_service import RouterService, SceneType, CONFIDENCE_THRESHOLD


class TestRouterService:
    """RouterService 테스트 클래스"""
    
    @pytest.fixture
    def router(self):
        """Mock 모드 Router 인스턴스"""
        return RouterService(model_path=None)
    
    @pytest.mark.asyncio
    async def test_mock_mode_enabled(self, router):
        """Mock 모드가 활성화되는지 확인"""
        assert router.mock_mode is True
        print("✅ Mock 모드 활성화 확인")
    
    @pytest.mark.asyncio
    async def test_classify_returns_valid_scene_type(self, router):
        """분류 결과가 유효한 SceneType인지 확인"""
        scene_type, confidence = await router.classify("http://example.com/test.jpg")
        
        assert isinstance(scene_type, SceneType)
        assert scene_type in [
            SceneType.SCENE_ENGINE,
            SceneType.SCENE_DASHBOARD,
            SceneType.SCENE_EXTERIOR,
            SceneType.SCENE_TIRE
        ]
        print(f"✅ 유효한 SceneType 반환: {scene_type.value}")
    
    @pytest.mark.asyncio
    async def test_classify_returns_confidence(self, router):
        """분류 결과에 신뢰도가 포함되는지 확인"""
        scene_type, confidence = await router.classify("http://example.com/test.jpg")
        
        assert isinstance(confidence, float)
        assert 0.0 <= confidence <= 1.0
        print(f"✅ 신뢰도 반환: {confidence}")
    
    @pytest.mark.asyncio
    async def test_mock_classify_engine_keywords(self, router):
        """Mock 분류: 엔진 키워드 인식"""
        scene_type, _ = await router.classify("http://example.com/engine_bay.jpg")
        assert scene_type == SceneType.SCENE_ENGINE
        print("✅ 엔진 키워드 인식")
    
    @pytest.mark.asyncio
    async def test_mock_classify_dashboard_keywords(self, router):
        """Mock 분류: 대시보드 키워드 인식"""
        scene_type, _ = await router.classify("http://example.com/dashboard_warning.jpg")
        assert scene_type == SceneType.SCENE_DASHBOARD
        print("✅ 대시보드 키워드 인식")
    
    @pytest.mark.asyncio
    async def test_mock_classify_exterior_keywords(self, router):
        """Mock 분류: 외관 키워드 인식"""
        scene_type, _ = await router.classify("http://example.com/bumper_damage.jpg")
        assert scene_type == SceneType.SCENE_EXTERIOR
        print("✅ 외관 키워드 인식")
    
    @pytest.mark.asyncio
    async def test_mock_classify_tire_keywords(self, router):
        """Mock 분류: 타이어 키워드 인식"""
        scene_type, _ = await router.classify("http://example.com/tire_check.jpg")
        assert scene_type == SceneType.SCENE_TIRE
        print("✅ 타이어 키워드 인식")
    
    @pytest.mark.asyncio
    async def test_is_low_confidence(self, router):
        """신뢰도 임계값 체크 함수 테스트"""
        assert router.is_low_confidence(0.5) is True
        assert router.is_low_confidence(0.7) is False
        assert router.is_low_confidence(0.8) is False
        print(f"✅ 임계값 체크 정상 (threshold: {CONFIDENCE_THRESHOLD})")
    
    @pytest.mark.asyncio
    async def test_classify_latency(self, router):
        """분류 지연시간이 0.1초 이내인지 확인"""
        start = time.time()
        await router.classify("http://example.com/test.jpg")
        elapsed = time.time() - start
        
        # Mock 모드는 매우 빠르게 동작해야 함
        assert elapsed < 0.1, f"Router too slow: {elapsed:.3f}s"
        print(f"✅ 분류 지연시간: {elapsed:.4f}s")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
