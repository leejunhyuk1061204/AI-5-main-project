from fastapi import APIRouter, UploadFile, File, Depends
from ai.app.schemas.vision import VisionResponse
from ai.app.services.vision_service import VisionService

# 1. URL 맞추기: /predict/vision이 되도록 설정
router = APIRouter(prefix="/predict", tags=["Vision Analysis"])

# --- API 엔드포인트 ---
@router.post("/vision", response_model=VisionResponse) # 최종 주소: /predict/vision
async def analyze_vision(
    file: UploadFile = File(...),
    service: VisionService = Depends()
):
    return await service.predict_vision(file)