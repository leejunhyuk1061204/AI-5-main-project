"""
Audio Diagnosis Router - YAMNet 기반 오디오 분석 API
엔진/부품 소리를 분석하여 이상 유무 및 원인을 판별합니다.
"""

from fastapi import APIRouter, UploadFile, File, Depends
from ai.app.schemas.audio import AudioResponse
from ai.app.services.audio_service import AudioService

# 1. URL: /predict/audio 가 되도록 설정
router = APIRouter(prefix="/predict", tags=["Audio Analysis"])


# --- API 엔드포인트 ---
@router.post("/audio", response_model=AudioResponse)
async def analyze_audio(
    file: UploadFile = File(...),
    service: AudioService = Depends()
):
    """
    엔진/부품 소리를 분석하여 이상 유무 및 원인 판별
    
    - **file**: 오디오 파일 (.wav, .m4a, .mp3, .flac, .ogg)
    - **Returns**: 진단 결과 (상태, 부품, 상세정보, 신뢰도, 긴급 여부)
    
    ---
    
    ### YAMNet 모델 정보
    - Google의 사전학습된 오디오 분류 모델
    - AudioSet 데이터셋 기반 521개 클래스 분류 가능
    - Mel-Spectrogram 변환 후 분석 수행
    """
    return await service.predict_audio(file)


# --- 추가 엔드포인트: 정상 상태 Mock ---
@router.post("/audio/test-normal", response_model=AudioResponse)
async def analyze_audio_normal_mock(
    file: UploadFile = File(...),
    service: AudioService = Depends()
):
    """
    테스트용 정상 상태 반환 엔드포인트
    
    개발/테스트 시 정상 케이스를 확인하기 위한 Mock 엔드포인트입니다.
    """
    return await service.get_mock_normal_data(file)
