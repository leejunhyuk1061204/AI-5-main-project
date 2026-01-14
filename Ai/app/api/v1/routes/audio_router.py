"""
Audio Diagnosis Router - YAMNet 기반 오디오 분석 API
엔진/부품 소리를 분석하여 이상 유무 및 원인을 판별합니다.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import Optional

# 1. URL: /predict/audio 가 되도록 설정 (visual_router와 동일한 패턴)
router = APIRouter(prefix="/predict", tags=["Audio Analysis"])


# --- 명세서에 맞춘 Output 구조 ---
class AudioDetail(BaseModel):
    """진단 상세 정보"""
    diagnosed_label: str        # "SLIP_NOISE", "KNOCKING", "NORMAL" 등
    description: str            # "구동 벨트 장력 부족 의심"


class AudioResponse(BaseModel):
    """오디오 진단 응답 모델 (API 명세서 기준)"""
    primary_status: str         # "FAULTY" | "NORMAL"
    component: str              # "ENGINE_BELT", "ENGINE", "BEARING" 등
    detail: AudioDetail         # 진단 상세
    confidence: float           # 0.0 ~ 1.0
    is_critical: bool           # 긴급 정비 필요 여부


# --- 지원 파일 확장자 ---
SUPPORTED_AUDIO_EXTENSIONS = {".wav", ".m4a", ".mp3", ".flac", ".ogg"}


def validate_audio_file(filename: str) -> bool:
    """오디오 파일 확장자 검증"""
    if not filename:
        return False
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in SUPPORTED_AUDIO_EXTENSIONS


# --- API 엔드포인트 ---
@router.post("/audio", response_model=AudioResponse)
async def analyze_audio(file: UploadFile = File(...)):
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
    # 파일 확장자 검증
    if not validate_audio_file(file.filename):
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 파일 형식입니다. 지원 형식: {', '.join(SUPPORTED_AUDIO_EXTENSIONS)}"
        )
    
    print(f"[Audio Router] Received audio file: {file.filename}")
    
    # TODO: 실제 YAMNet 모델 연동 시 아래 로직 구현
    # 1. 오디오 파일을 16kHz로 리샘플링
    # 2. Mel-Spectrogram 변환
    # 3. YAMNet 모델로 추론
    # 4. 차량 관련 클래스 필터링 및 결과 매핑
    
    # [Mock Data] 명세서와 동일한 형태의 가짜 데이터 리턴
    return AudioResponse(
        primary_status="FAULTY",
        component="ENGINE_BELT",
        detail=AudioDetail(
            diagnosed_label="SLIP_NOISE",
            description="구동 벨트 장력 부족 의심"
        ),
        confidence=0.88,
        is_critical=False
    )


# --- 추가 엔드포인트: 정상 상태 Mock ---
@router.post("/audio/test-normal", response_model=AudioResponse)
async def analyze_audio_normal_mock(file: UploadFile = File(...)):
    """
    테스트용 정상 상태 반환 엔드포인트
    
    개발/테스트 시 정상 케이스를 확인하기 위한 Mock 엔드포인트입니다.
    """
    print(f"[Audio Router] Test normal - Received: {file.filename}")
    
    return AudioResponse(
        primary_status="NORMAL",
        component="ENGINE",
        detail=AudioDetail(
            diagnosed_label="NORMAL",
            description="정상적인 엔진 작동음입니다"
        ),
        confidence=0.95,
        is_critical=False
    )
