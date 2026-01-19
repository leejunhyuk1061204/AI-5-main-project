# app/api/v1/routes/visual_router.py
"""
시각 분석 라우터
- /visual: LLM 기반 범용 시각 분석 (DASHBOARD 포함)
- /engine: 엔진룸 정밀 진단 (YOLO + PatchCore + LLM)
"""
from fastapi import APIRouter, Request, HTTPException
from typing import Dict, Any

from ai.app.schemas.visual_schema import VisualResponse, VisualRequest, EngineAnalysisRequest, EngineAnalysisResponse
from ai.app.services.visual_service import get_smart_visual_diagnosis
from ai.app.services.engine_anomaly_service import EngineAnomalyPipeline

router = APIRouter(prefix="/predict", tags=["Visual Analysis"])

@router.post("/visual", response_model=VisualResponse)
async def analyze_visual(request_body: VisualRequest, request: Request):
    """
    범용 시각 분석 (LLM Only)
    - DASHBOARD, EXTERIOR, INTERIOR, TIRE, LAMP, ENGINE 모두 LLM이 분류
    """
    s3_url = request_body.imageUrl
    print(f"[Visual Router] Received S3 URL: {s3_url}")
    
    # LLM 기반 분석 (YOLO 제거됨)
    result = await get_smart_visual_diagnosis(s3_url)
    
    return result["content"]


@router.post("/engine", response_model=EngineAnalysisResponse)
async def analyze_engine(request_body: EngineAnalysisRequest, request: Request):
    """
    엔진룸 정밀 결함 진단 (Engine Anomaly Detection)
    - Input: S3 Image URL
    - Process: YOLO -> Crop -> Anomaly(PatchCore) -> LLM
    - Output: 부품별 결함 리포트 (Path A) or 범용 진단 리포트 (Path B)
    """
    engine_model = getattr(request.app.state, "engine_yolo_model", None)
    pipeline = EngineAnomalyPipeline()
    
    try:
        result = await pipeline.analyze(
            s3_url=request_body.imageUrl,
            yolo_model=engine_model
        )
        
        return EngineAnalysisResponse(
            status=result["status"],
            data=result
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[Visual/Engine API Error] {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error during Engine Analysis")
    finally:
        # HTTP 클라이언트 정리 (메모리 누수 방지)
        await pipeline.close()
