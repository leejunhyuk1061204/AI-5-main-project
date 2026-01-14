from pydantic import BaseModel
from typing import List, Optional

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
