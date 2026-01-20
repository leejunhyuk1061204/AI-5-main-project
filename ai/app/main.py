from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
from ultralytics import settings
from dotenv import load_dotenv, find_dotenv

# 루트 폴더(.env)를 명시적으로 찾아서 로드
load_dotenv(find_dotenv())

# Ultralytics 전역 가중치 경로 설정
settings.update({'weights_dir': os.path.join(os.getcwd(), 'ai', 'weights')})

from ai.app.api.v1.routes.health import router as health_router
from ai.app.api.v1.routes.router import router as predict_router
from ai.app.api.v1.routes.visual_router import router as visual_router
from ai.app.api.v1.routes.audio_router import router as audio_router




def load_ast_model():
    """AST 오디오 모델 로드"""
    print("Loading AST Model...")
    from transformers import ASTForAudioClassification, ASTFeatureExtractor
    
    # 모델 경로 (상대 경로로 설정)
    model_path = os.path.join("ai", "weights", "audio", "best_ast_model")
    
    # 로컬에 학습된 가중치가 없으면 기본 모델 사용 (에러 방지용)
    if not os.path.exists(model_path):
        print(f"[Warning] 학습된 모델을 찾을 수 없습니다: {model_path}")
        print("기본 모델(MIT/ast-finetuned-audioset-10-10-0.4593)을 로드합니다.")
        model_name = "MIT/ast-finetuned-audioset-10-10-0.4593"
        model = ASTForAudioClassification.from_pretrained(model_name)
        feature_extractor = ASTFeatureExtractor.from_pretrained(model_name)
    else:
        print(f"학습된 AST 모델 로드 중: {model_path}")
        model = ASTForAudioClassification.from_pretrained(model_path)
        feature_extractor = ASTFeatureExtractor.from_pretrained(model_path)

    return {"model": model, "feature_extractor": feature_extractor}


def load_engine_yolo_model():
    """YOLOv8 엔진룸 부품 감지 모델 로드"""
    print("Loading YOLOv8 Engine Model...")
    from ultralytics import YOLO
    
    model_path = os.path.join("ai", "weights", "engine", "best.pt")
    
    if not os.path.exists(model_path):
        print(f"[Warning] 엔진 YOLO 가중치를 찾을 수 없습니다: {model_path}")
        print("기본 모델(ai/weights/yolov8n.pt)을 사용합니다. 엔진 부품 감지 정확도가 낮을 수 있습니다.")
        model = YOLO(os.path.join("ai", "weights", "yolov8n.pt"))
    else:
        print(f"학습된 엔진 YOLO 모델 로드 중: {model_path}")
        model = YOLO(model_path)
        
    return model


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 0. 초기화
    app.state.ast_model = None
    app.state.engine_yolo_model = None  # 엔진 분석용 모델 (Dashboard YOLO 제거됨)

    # 1. 모델 로드
    try:
        app.state.ast_model = load_ast_model()
        app.state.engine_yolo_model = load_engine_yolo_model()
        print("✅ AI Models (YOLOv8 Engine, AST) loaded successfully.")
    except Exception as e:
        print(f"❌ Critical Error loading models: {e}")
    
    yield
    
    # 2. 종료 시 정리
    print("AI Models unloaded.")



def create_app() -> FastAPI:
    # HEAD의 description + lifespan 유지, main의 title도 반영해서 통합
    app = FastAPI(
        title="Car-Sentry AI Server",
        description="차량 파손 및 엔진 소리 진단을 위한 AI API",
        version="1.0.0",
        lifespan=lifespan,
    )

    # ---- CORS (HEAD 유지) ----
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 배포 시 특정 도메인만 허용 권장
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---- 라우터 등록(기존 OBD + Vision + Audio) ----
    app.include_router(health_router, prefix="/api/v1", tags=["health"])
    app.include_router(predict_router, prefix="/api/v1", tags=["predict"])
    app.include_router(visual_router, prefix="/api/v1", tags=["visual"])
    app.include_router(audio_router, prefix="/api/v1", tags=["audio"])

    # [Test] 테스트 라우터 등록 (개발/테스트용)
    from ai.app.api.v1.routes.test_router import router as test_router
    from ai.app.api.v1.routes.test_router import connect_router
    app.include_router(test_router, prefix="/api/v1", tags=["test"])
    app.include_router(connect_router, prefix="/api/v1", tags=["connect"])
    print("✅ Test Router Registered (/api/v1/test/... + /api/v1/connect/...)")

    return app


app = create_app()


# 루트(/) 응답: 있으면 브라우저에서 Not Found 안 떠서 편함
@app.get("/")
def root():
    return {"status": "ok", "message": "Car-Sentry AI Server is running!"}
