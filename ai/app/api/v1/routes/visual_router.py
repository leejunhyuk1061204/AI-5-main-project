# app/api/v1/routes/visual_router.py
from fastapi import APIRouter
from ai.app.schemas.visual_schema import VisualResponse
from ai.app.services.visual_service import get_smart_visual_diagnosis # 스마트 라우팅 서비스

router = APIRouter(prefix="/predict", tags=["Visual Analysis"])

@router.post("/visual", response_model=VisualResponse)
async def analyze_visual(s3_url: str): # S3 URL을 인자로 받음
    print(f"[Visual Router] Received S3 URL: {s3_url}")
    
    # 이전에 만든 YOLO -> LLM 판단 로직이 담긴 서비스를 호출합니다.
    result = await get_smart_visual_diagnosis(s3_url)
    
    # 서비스 결과(dict)를 Response 모델 형식에 맞춰 반환
    return result["data"]