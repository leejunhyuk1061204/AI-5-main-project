from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv, find_dotenv

# 루트 폴더(.env)를 명시적으로 찾아서 로드
load_dotenv(find_dotenv())

from ai.app.api.v1.routes.health import router as health_router
from ai.app.api.v1.routes.router import router as predict_router
from ai.app.api.v1.routes.visual_router import router as visual_router
from ai.app.api.v1.routes.audio_router import router as audio_router



def load_ast_model(sr=16000):
    print(f"Loading AST Model with SR={sr}...")
    return "AST_MODEL_OBJECT"

def load_yolo_model():
    print("Loading YOLOv8 Model...")
    return "YOLO_MODEL_OBJECT"



@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.ast_model = load_ast_model(sr=16000)
    app.state.yolo_model = load_yolo_model()
    print("AI Models (YOLOv8, AST) loaded at 16,000Hz specification.")
    yield
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

    # [Test] 로컬 환경일 경우 테스트 라우터 등록
    import os
    if os.getenv("APP_ENV") == "local":
        from ai.app.api.v1.routes.test_router import router as test_router
        app.include_router(test_router, prefix="/api/v1", tags=["test"])
        print("✅ Local Test Router Registered (/api/v1/test/predict/...)")

    return app


app = create_app()


# 루트(/) 응답: 있으면 브라우저에서 Not Found 안 떠서 편함
@app.get("/")
def root():
    return {"status": "ok", "message": "Car-Sentry AI Server is running!"}
