from fastapi import FastAPI
from Ai.app.api.v1.routes.health import router as health_router
from Ai.app.api.v1.routes.router import router as predict_router

#프론트엔드 / 모바일 앱에서 API 호출 가능하게 해줌
from fastapi.middleware.cors import CORSMiddleware
#서버 시작/종료 시 실행할 코드 정의용
from contextlib import asynccontextmanager

# 만약 아직 정의하지 않으셨다면 임시로라도 정의가 필요합니다.
def load_ast_model(sr=16000):
    print(f"Loading AST Model with SR={sr}...")
    return "AST_MODEL_OBJECT"
def load_yolo_model():
    print("Loading YOLOv8 Model...")
    return "YOLO_MODEL_OBJECT"

# [추가] 서버 시작 시 모델을 로드하고, 끌 때 메모리를 해제하는 로직
@asynccontextmanager
# lifespan: 서버 시작/종료 시 실행할 코드 정의용(startup/shutdown)
async def lifespan(app: FastAPI):
    app.state.ast_model = load_ast_model(sr=16000)
    app.state.yolo_model = load_yolo_model()
    print("AI Models (YOLOv8, AST) loaded at 16,000Hz specification.")
    yield
    # 서버 종료 시 로직 (필요 시)
    print("AI Models unloaded.")

def create_app() -> FastAPI:
    app = FastAPI(title="OBD AI API", description="차량 파손 및 엔진 소리 진단을 위한 AI API", 
                version="1.0.0", lifespan=lifespan)


    # --- [추가] CORS 설정: API 담당자와의 원활한 통신을 위해 ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 실제 배포 시에는 특정 도메인만 허용하도록 수정
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router, prefix="/api/v1", tags=["health"])
    app.include_router(predict_router, prefix="/api/v1", tags=["predict"])

    return app

app = create_app()
