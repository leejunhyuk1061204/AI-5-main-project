# app/api/v1/routes/test_router.py
from fastapi import APIRouter, UploadFile, File, HTTPException
from ai.app.services.local_service import process_visual_mock, process_audio_mock
from ai.app.schemas.visual_schema import VisualResponse
from ai.app.schemas.audio_schema import AudioResponse
from pydantic import BaseModel
from typing import List, Dict

router = APIRouter(prefix="/test/predict", tags=["Local Test"])

class OBDDataPoint(BaseModel):
    rpm: float
    load: float
    coolant: float
    voltage: float

class AnomalyRequest(BaseModel):
    time_series: List[Dict]

class AnomalyResponse(BaseModel):
    is_anomaly: bool
    anomaly_score: float
    threshold: float
    contributing_factors: List[str]

@router.post("/visual", response_model=VisualResponse)
async def analyze_visual_local(file: UploadFile = File(...)):
    """
    [Local Test] 이미지 파일 직접 수신 -> Mock 응답 반환
    """
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Invalid image file type")
    
    content = await file.read()
    return await process_visual_mock(content)

@router.post("/audio", response_model=AudioResponse)
async def analyze_audio_local(file: UploadFile = File(...)):
    """
    [Local Test] 오디오 파일 직접 수신 -> Mock 응답 반환
    """
    if not file.content_type.startswith("audio/"):
        # 오디오 타입 체크 완화 (wav, mp3, m4a 등)
        pass 
    
    content = await file.read()
    return await process_audio_mock(content)

@router.post("/anomaly", response_model=AnomalyResponse)
async def analyze_anomaly_local(request: AnomalyRequest):
    """
    [Local Test] LSTM 시계열 이상 탐지 Mock 응답 반환
    """
    # Mock 데이터 반환 (실제 모델 연결 없음)
    data_count = len(request.time_series)
    
    return AnomalyResponse(
        is_anomaly=data_count >= 10,  # 10개 이상 데이터면 이상 징후로 가정 (테스트용)
        anomaly_score=0.75 if data_count >= 10 else 0.25,
        threshold=0.70,
        contributing_factors=["RPM", "VOLTAGE"] if data_count >= 10 else []
    )

@router.post("/embedding")
async def get_dummy_embedding(data: dict):
    """
    [Local Test] 더미 임베딩 반환 (1024차원)
    """
    text = data.get("text", "")
    # 테스트를 위한 1024차원 더미 벡터 생성 (0.01로 채움)
    dummy_vector = [0.01] * 1024
    
    return {
        "embedding": dummy_vector,
        "model": "mxbai-embed-large-dummy"
    }

@router.post("/comprehensive")
async def unified_comprehensive_mock(data: dict):
    """
    [Local Test] 종합 진단 Mock 응답 반환 (OpenAI 연동 전단계)
    실제 프롬프트 엔지니어링 전 테스트용
    
    Status 종류:
    - SUCCESS: 진단 완료
    - NEED_MORE_DATA: 추가 증거 필요 (사진/녹음 요청)
    """
    vehicle_id = data.get("vehicleId", "unknown")
    audio = data.get("audioAnalysis")
    visual = data.get("visualAnalysis")
    lstm = data.get("lstmAnalysis")
    
    # 데이터 부족 시 추가 요청 반환
    if not audio and not visual:
        return {
            "status": "NEED_MORE_DATA",
            "vehicleId": vehicle_id,
            "mission": {
                "type": "PHOTO_OR_AUDIO",
                "message": "정확한 진단을 위해 차량 사진 또는 엔진 소리 녹음이 필요합니다.",
                "options": [
                    {"type": "PHOTO", "guide": "엔진룸 또는 이상 부위를 촬영해 주세요."},
                    {"type": "AUDIO", "guide": "시동을 건 상태에서 10초간 녹음해 주세요."}
                ]
            },
            "model": "gpt-4o-mock"
        }
    
    if not audio:
        return {
            "status": "NEED_MORE_DATA",
            "vehicleId": vehicle_id,
            "mission": {
                "type": "AUDIO",
                "message": "소리 분석 데이터가 없습니다. 엔진 소리를 녹음해 주세요.",
                "guide": "시동을 건 상태에서 10초간 녹음해 주세요."
            },
            "model": "gpt-4o-mock"
        }
    
    if not visual:
        return {
            "status": "NEED_MORE_DATA",
            "vehicleId": vehicle_id,
            "mission": {
                "type": "PHOTO",
                "message": "사진 분석 데이터가 없습니다. 차량 사진을 촬영해 주세요.",
                "guide": "엔진룸 또는 이상 부위를 촬영해 주세요."
            },
            "model": "gpt-4o-mock"
        }
    
    # 모든 데이터가 있으면 SUCCESS
    return {
        "status": "SUCCESS",
        "vehicleId": vehicle_id,
        "diagnosis": {
            "summary": "차량 전반적인 상태는 양호합니다.",
            "issues": [
                {
                    "category": visual.get("category", "일반") if visual else "일반",
                    "severity": "LOW",
                    "description": "경미한 점검 필요"
                }
            ],
            "recommendations": [
                "정기 점검을 권장합니다.",
                "엔진 오일 상태를 확인해 주세요."
            ]
        },
        "confidence": 0.85,
        "model": "gpt-4o-mock"
    }
