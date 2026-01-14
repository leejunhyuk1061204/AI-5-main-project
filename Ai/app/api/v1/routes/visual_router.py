from fastapi import APIRouter, UploadFile, File
from pydantic import BaseModel
from typing import List, Optional

# 1. URL 맞추기: /predict/vision이 되도록 설정
router = APIRouter(prefix="/predict", tags=["Vision Analysis"])

# --- 명세서에 맞춘 Output 구조 ---
class DetectionItem(BaseModel):
    label: str          # "SCRATCH" (대문자)
    confidence: float   # 0.92
    bbox: List[int]     # [x, y, w, h]
    # damage_area_px는 여기서 빠지고 전체 요약으로 이동했습니다.

class VisionResponse(BaseModel):
    status: str         # "DAMAGED" (대문자)
    damage_area_px: int # 전체 파손 면적 (Root 레벨로 이동)
    detections: List[DetectionItem]
    processed_image_url: Optional[str] = None # S3 주소 (없을 수도 있으니 Optional)

# --- API 엔드포인트 ---
@router.post("/vision", response_model=VisionResponse) # 최종 주소: /predict/vision
async def analyze_vision(file: UploadFile = File(...)):
    print(f"Received image: {file.filename}")
    
    # [Mock Data] 명세서와 똑같은 가짜 데이터 리턴
    return VisionResponse(
        status="DAMAGED",       # 명세서는 대문자 원함
        damage_area_px=4500,    # 전체 파손 면적
        detections=[
            DetectionItem(
                label="SCRATCH",
                confidence=0.92,
                bbox=[120, 45, 200, 150]
            )
        ],
        processed_image_url="s3://car-sentry-bucket/processed/img_001.jpg" # 임시 주소
    )