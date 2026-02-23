from fastapi import APIRouter, Depends, HTTPException, Request
from ai.app.schemas.audio_schema import AudioResponse, AudioRequest
from ai.app.services.audio.audio_service import AudioService

# 백엔드 AiClient가 /api/v1/predict/audio 로 호출하므로 prefix 필요
router = APIRouter(prefix="/predict", tags=["Audio Analysis"])

@router.post("/audio", response_model=AudioResponse)
async def analyze_audio(
    request_body: AudioRequest,  # Request Body로 변경
    request: Request,
    service: AudioService = Depends()
):
    """
    엔진/부품 소리 2단계 정밀 분석 (AST + LLM)
    
    1. **S3 URL**: 분석할 오디오 파일의 주소
    2. **AST (1차)**: 엔진 소음 여부 및 기초 분류
    3. **LLM (2차)**: 미세 소음 정밀 진단 및 정비 권고
    """
    s3_url = request_body.audioUrl
    vehicle_id = request_body.vehicleId
    session_id = request_body.sessionId
    
    print(f"[Audio API] 요청 수신 - Vehicle: {vehicle_id}, Session: {session_id}, URL: {s3_url}")

    if not s3_url.startswith("http"):
        raise HTTPException(status_code=400, detail="유효한 S3 URL이 아닙니다.")
    
    # Safe Access (Lazy Loading)
    ast_model = request.app.state.get_ast_model()
        
    result = await service.predict_audio_smart(s3_url, ast_model=ast_model)
    print(f"[Audio API Response] 분석 완료 - Result: {result}")
    return result



@router.post("/audio/test-normal", response_model=AudioResponse)
async def analyze_audio_normal_mock(
    service: AudioService = Depends()
):
    """테스트용 정상 데이터 반환"""
    return await service.get_mock_normal_data()