# app/api/v1/routes/visual_router.py
"""
통합 시각 분석 API 라우터

[엔드포인트]
- POST /visual: 통합 분석 (Router가 자동 분기)
- POST /engine: 엔진룸 전용 분석 (직접 호출용, 하위 호환)

[흐름]
Image → Router(MobileNetV3) → 장면 분류 → 전문 파이프라인
"""
from fastapi import APIRouter, Request, HTTPException
from typing import Dict, Any

from ai.app.schemas.visual_schema import (
    VisualResponse, 
    VisualRequest, 
    EngineAnalysisRequest, 
    EngineAnalysisResponse
)
from ai.app.services.visual_service import get_smart_visual_diagnosis
from ai.app.services.engine_anomaly_service import EngineAnomalyPipeline

router = APIRouter(prefix="/predict", tags=["Visual Analysis"])


@router.post("/visual")
async def analyze_visual(request_body: VisualRequest, request: Request):
    """
    통합 시각 분석 API (Router 기반 자동 분기)
    
    - Router가 이미지를 ENGINE/DASHBOARD/EXTERIOR/TIRE로 분류
    - 각 장면에 맞는 전문 분석 파이프라인 실행
    - Confidence 낮으면 LLM Fallback
    
    Response:
        {
            "status": "WARNING",
            "analysis_type": "SCENE_ENGINE",
            "category": "ENGINE_ROOM",
            "data": {...}
        }
    """
    s3_url = request_body.imageUrl
    print(f"[Visual API] 요청 수신: {s3_url}")
    
    # 모델들을 Getter를 통해 지연 로딩 (필요할 때만 로드)
    models = {
        "router": request.app.state.get_router(),
        "engine_yolo": request.app.state.get_engine_yolo(),
        "dashboard_yolo": request.app.state.get_dashboard_yolo(),
        "cardd_yolo": request.app.state.get_exterior_yolo()["cardd"],
        "carparts_yolo": request.app.state.get_exterior_yolo()["carparts"],
        "tire_yolo": request.app.state.get_tire_yolo(),
    }
    
    try:
        result = await get_smart_visual_diagnosis(s3_url, models)
        
        # content가 VisualResponse 객체인 경우
        content = result.get("content")
        if hasattr(content, "dict"):
            return content
        elif isinstance(content, dict):
            return content
        else:
            return result
            
    except Exception as e:
        print(f"[Visual API Error] {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/engine", response_model=EngineAnalysisResponse)
async def analyze_engine(request_body: EngineAnalysisRequest, request: Request):
    """
    엔진룸 전용 정밀 분석 (직접 호출용)
    
    - Router를 거치지 않고 직접 Engine 분석
    - YOLO → Crop → PatchCore → LLM
    """
    engine_model = request.app.state.get_engine_yolo()
    pipeline = EngineAnomalyPipeline()
    
    try:
        result = await pipeline.analyze(
            s3_url=request_body.imageUrl,
            yolo_model=engine_model
        )
        
        return EngineAnalysisResponse(
            status=result.get("status", "SUCCESS"),
            data=result
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[Engine API Error] {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
    finally:
        await pipeline.close()
