# verify_hybrid_flow.py
import asyncio
import logging
import os
import sys

# 프로젝트 루트를 경로에 추가
sys.path.append(os.getcwd())

from ai.app.services.audio.audio_service import AudioService
from ai.app.schemas.audio_schema import AudioResponse

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VerifyHybrid")

async def test_hybrid_flow():
    service = AudioService()
    
    # 1. 테스트용 S3 URL (정상 샘플)
    mock_url = "https://ai5-car-sound.s3.ap-northeast-2.amazonaws.com/test/normal_idle_1_01.wav"
    
    print("\n" + "="*60)
    print("🚀 Starting Hybrid Diagnosis Pipeline Test")
    print("="*60)
    
    try:
        # 실제 S3 다운로드를 피하기 위해 _safe_load_audio와 preprocess를 모킹하거나 
        # 실제 파일이 있는 경우 그것을 사용하도록 시뮬레이션
        from unittest.mock import MagicMock, patch
        
        # 실제 파일 로드 (로컬에 있는 파일 활용)
        test_file = "ai/data/audio/train/normal/normal_idle_1_01.wav"
        if not os.path.exists(test_file):
            print(f"❌ Test file not found at {test_file}")
            return

        with open(test_file, "rb") as f:
            audio_bytes = f.read()

        # AudioService의 다운로드/전처리 단계를 모킹하여 로컬 파일을 사용하게 함
        with patch.object(AudioService, '_safe_load_audio', return_value=audio_bytes):
            # 전처리는 실제 로직을 타게 두거나, 바이트를 그대로 반환하게 모킹
            # 여기서는 실제 전처리 로직의 의존성(ffmpeg 등)이 없을 수 있으므로 간단히 모킹
            from ai.app.services.audio.audio_preprocessing import preprocess_audio_pipeline
            with patch('ai.app.services.audio.audio_service.preprocess_audio_pipeline', return_value=(audio_bytes, 0.05)):
                
                # AST 추론 모킹 (AI 결과 시뮬레이션)
                mock_ast_res = AudioResponse(
                    status="NORMAL",
                    analysis_type="AST",
                    category="ENGINE",
                    detail={"diagnosed_label": "NORMAL_SOUND"},
                    confidence=0.95
                )
                with patch('ai.app.services.audio.audio_service.run_ast_inference', return_value=mock_ast_res):
                    
                    print("🛠 Running predict_audio_smart...")
                    result = await service.predict_audio_smart(mock_url)
                    
                    print(f"\n✅ Diagnostic Result:")
                    print(f"  - Status: {result.status}")
                    print(f"  - Category: {result.category}")
                    print(f"  - Analysis Type: {result.analysis_type}")
                    print(f"  - Confidence: {result.confidence:.4f}")
                    
                    if hasattr(result.detail, 'additional_metrics') and result.detail.additional_metrics:
                        print(f"\n📊 Hybrid Rule Metrics:")
                        for k, v in result.detail.additional_metrics.items():
                            print(f"    - {k}: {v}")
                    
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_hybrid_flow())
