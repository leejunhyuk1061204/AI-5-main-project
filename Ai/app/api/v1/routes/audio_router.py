from fastapi import APIRouter, Depends, HTTPException
from ai.app.schemas.audio_schema import AudioResponse
from ai.app.services.audio_service import AudioService

# 1. URL: /predict/audio 설정
router = APIRouter(prefix="/predict", tags=["Audio Analysis"])

@router.post("/audio", response_model=AudioResponse)
async def analyze_audio(
    s3_url: str,  # S3 URL을 직접 받도록 수정
    service: AudioService = Depends()
):
    """
    엔진/부품 소리 2단계 정밀 분석 (AST + LLM)
    
    1. **S3 URL**: 분석할 오디오 파일의 주소
    2. **AST (1차)**: 엔진 소음 여부 및 기초 분류
    3. **LLM (2차)**: 미세 소음 정밀 진단 및 정비 권고
    """
    if not s3_url.startswith("http"):
        raise HTTPException(status_code=400, detail="유효한 S3 URL이 아닙니다.")
        
    return await service.predict_audio_smart(s3_url)

@router.post("/audio/test-normal", response_model=AudioResponse)
async def analyze_audio_normal_mock(
    service: AudioService = Depends()
):
    """테스트용 정상 데이터 반환"""
    return await service.get_mock_normal_data()