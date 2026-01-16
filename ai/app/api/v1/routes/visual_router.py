# app/api/v1/routes/visual_router.py
from fastapi import APIRouter, Request

router = APIRouter(prefix="/predict", tags=["Visual Analysis"])

@router.post("/visual", response_model=VisualResponse)
async def analyze_visual(s3_url: str, request: Request): # Request 객체 추가
    print(f"[Visual Router] Received S3 URL: {s3_url}")
    
    # app.state에서 로드된 모델 가져오기 (Safe Access)
    yolo_model = getattr(request.app.state, "yolo_model", None)
    
    # 이전에 만든 YOLO -> LLM 판단 로직이 담긴 서비스를 호출합니다.

    result = await get_smart_visual_diagnosis(s3_url, yolo_model=yolo_model)

    
    # 서비스 결과(dict)를 Response 모델 형식에 맞춰 반환
    return result["content"]