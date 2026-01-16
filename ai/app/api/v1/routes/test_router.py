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

class FileUrlRequest(BaseModel):
    file_url: str

@router.post("/visual", response_model=VisualResponse)
async def analyze_visual_local(request: FileUrlRequest):
    """
    [Local Test] 이미지 URL 수신 -> 파일 다운로드 -> Mock 응답 반환
    """
    import httpx
    import os
    
    # URL에서 파일명 추출
    filename = request.file_url.split("/")[-1]
    uploads_dir = os.path.join(os.path.dirname(__file__), "../../../../uploads")
    os.makedirs(uploads_dir, exist_ok=True)
    file_path = os.path.join(uploads_dir, filename)
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(request.file_url)
            content = response.content
            # 파일 저장 (덮어쓰기)
            with open(file_path, "wb") as f:
                f.write(content)
    except Exception:
        # URL 접근 실패 시에도 Mock 응답 반환 (테스트용)
        content = b"mock_image_data"
    
    return await process_visual_mock(content)

@router.post("/audio", response_model=AudioResponse)
async def analyze_audio_local(request: FileUrlRequest):
    """
    [Local Test] 오디오 URL 수신 -> 파일 다운로드 -> Mock 응답 반환
    """
    import httpx
    import os
    
    # URL에서 파일명 추출
    filename = request.file_url.split("/")[-1]
    uploads_dir = os.path.join(os.path.dirname(__file__), "../../../../uploads")
    os.makedirs(uploads_dir, exist_ok=True)
    file_path = os.path.join(uploads_dir, filename)
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(request.file_url)
            content = response.content
            # 파일 저장 (덮어쓰기)
            with open(file_path, "wb") as f:
                f.write(content)
    except Exception:
        # URL 접근 실패 시에도 Mock 응답 반환 (테스트용)
        content = b"mock_audio_data"
    
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
    anomaly = data.get("anomalyAnalysis")
    vehicle_info = data.get("vehicleInfo")
    consumables_status = data.get("consumablesStatus")
    
    # 데이터 유무 확인 로그
    log_msg = f"[Comprehensive] Request received for vehicle: {vehicle_id}\n"
    log_msg += f"- Visual: {'YES' if visual else 'NO'}\n"
    log_msg += f"- Audio: {'YES' if audio else 'NO'}\n"
    log_msg += f"- Anomaly: {'YES' if anomaly else 'NO'}\n"
    log_msg += f"- VehicleInfo: {'YES' if vehicle_info else 'NO'}\n"
    log_msg += f"- Consumables: {'YES' if consumables_status else 'NO'} ({len(consumables_status) if consumables_status else 0} items)"
    print(log_msg)
    
    # 데이터 부족 시 추가 요청 반환 (자동 진단 시에는 무시될 수 있음)
    if not audio and not visual and not anomaly:
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

@router.post("/wear-factor")
async def predict_wear_factor_mock(data: dict):
    """
    [Local Test] XGBoost 마모율 예측 Mock 응답 반환
    실제 모델 연동 전 테스트용
    """
    target_item = data.get("targetItem", "ENGINE_OIL")
    
    # Mock 마모율 계산 (0.8 ~ 1.5 범위)
    import random
    wear_factor = round(random.uniform(0.8, 1.5), 2)
    
    return {
        "predictedWearFactor": wear_factor,
        "targetItem": target_item,
        "modelVersion": "xgboost-mock-0.1.0",
        "message": f"{target_item} 마모율이 계산되었습니다."
    }
