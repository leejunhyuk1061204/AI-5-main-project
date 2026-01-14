from fastapi import UploadFile
from ai.app.schemas.vision import VisionResponse, DetectionItem

class VisionService:
    """비전 분석 및 진단을 담당하는 서비스 클래스"""

    async def predict_vision(self, file: UploadFile) -> VisionResponse:
        """
        이미지 파일을 분석하여 파손 여부 및 상세 정보를 반환합니다.
        현재는 Mock 데이터를 반환하며, 추후 YOLOv8 모델이 연동될 예정입니다.
        """
        print(f"[Vision Service] Processing image: {file.filename}")
        
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
