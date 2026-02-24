# ai/app/main.py
"""
Car-Sentry AI 서비스 메인 진입점 (FastAPI Application)

[역할]
1. API 서버 구동: 차량 진단 요청을 수신하고 결과를 반환하는 REST API 서버를 실행합니다.
2. AI 모델 관리: Router, YOLO, AST 등 다양한 AI 모델의 수명 주기(Lifespan)와 지연 로딩(Lazy Loading)을 관리합니다.
3. 보안 및 설정: CORS 환경 설정 및 글로벌 환경 변수를 관리합니다.

[주요 엔드포인트]
- /health: 서버 상태 확인
- /v1/visual/diagnosis: 통합 시각 기반 차량 진단
- /v1/audio/diagnosis: 통합 오디오 기반 차량 진단
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
import asyncio
from ultralytics import settings, YOLO
from dotenv import load_dotenv, find_dotenv

# .env 파일 로드 (루트 디렉토리 우선 탐색)
# find_dotenv()는 현재 디렉토리부터 상위로 올라가며 .env를 찾습니다.
env_path = find_dotenv()
if env_path:
    print(f"[Config] Loading settings from: {env_path}")
    load_dotenv(env_path, override=True)

# [S3 Mapping] 사용자 .env의 S3_ACCESS_KEY -> AWS_ACCESS_KEY_ID 매핑
# boto3는 표준 환경변수명을 사용하므로, 다른 이름으로 저장된 경우 보정해줍니다.
if os.getenv("S3_ACCESS_KEY") and not os.getenv("AWS_ACCESS_KEY_ID"):
    os.environ["AWS_ACCESS_KEY_ID"] = os.getenv("S3_ACCESS_KEY")
if os.getenv("S3_SECRET_KEY") and not os.getenv("AWS_SECRET_ACCESS_KEY"):
    os.environ["AWS_SECRET_ACCESS_KEY"] = os.getenv("S3_SECRET_KEY")
if os.getenv("S3_REGION") and not os.getenv("AWS_DEFAULT_REGION"):
    os.environ["AWS_DEFAULT_REGION"] = os.getenv("S3_REGION")

# Ultralytics 전역 가중치 경로 설정
settings.update({'weights_dir': os.path.join(os.getcwd(), 'ai', 'weights')})

from ai.app.api.v1.routes.health import router as health_router
from ai.app.api.v1.routes.router import router as predict_router
from ai.app.api.v1.routes.visual_router import router as visual_router
from ai.app.api.v1.routes.audio_router import router as audio_router
from ai.app.api.v1.routes.obd_anomaly_router import router as obd_anomaly_router
from ai.app.api.v1.routes.wear_factor import router as wear_factor_router
from ai.app.api.v1.routes.embedding_router import router as embedding_router

# =============================================================================
# Model Loading Functions
# =============================================================================

def load_ast_model():
    """AST 오디오 모델 로드"""
    print("[Model] Loading AST Audio Model...")
    from transformers import ASTForAudioClassification, ASTFeatureExtractor
    
    # [User Request] 기본 경로를 hybrid_cnn14/cnn14.pt로 변경 (나중에 바뀔 수도 있음)
    model_path = os.path.join("ai", "weights", "audio", "hybrid_cnn14", "cnn14.pt") 
    
    # [Fallback] 만약 요청된 경로가 없거나 파일인 경우 (Transformers는 폴더 필요) 기존 경로들 체크
    if not os.path.exists(model_path) or not os.path.isdir(model_path):
        for alt_path in [
            os.path.join("ai", "weights", "audio", "best_ast_model"),
            os.path.join("ai", "weights", "audio", "hybrid_ast")
        ]:
            if os.path.exists(alt_path) and os.path.isdir(alt_path):
                print(f"[Info] 지정된 경로가 없거나 파일입니다. 대체 AST 폴더 사용: {alt_path}")
                model_path = alt_path
                break

    # 최종 체크: 여전히 폴더가 아니면 기본 모델(Online)로 폴백
    if not os.path.isdir(model_path):
        print(f"[Warning] AST 가중치 폴더를 찾을 수 없음 (현재 경로: {model_path})")
        print("[Warning] 기본 모델(MIT/ast-finetuned-audioset)을 로드하여 서버 중단을 방지합니다.")
        model_name = "MIT/ast-finetuned-audioset-10-10-0.4593"
        model = ASTForAudioClassification.from_pretrained(model_name)
        feature_extractor = ASTFeatureExtractor.from_pretrained(model_name)
    else:
        print(f"[Model] 학습된 AST 모델 로드: {model_path}")
        model = ASTForAudioClassification.from_pretrained(model_path)
        feature_extractor = ASTFeatureExtractor.from_pretrained(model_path)

    return {"model": model, "feature_extractor": feature_extractor}


def load_router_model():
    """MobileNetV3-Small 라우터 모델 로드"""
    print("[Model] Loading Router Model (MobileNetV3-Small)...")
    from ai.app.services.visual.router_service import RouterService
    
    model_path = os.path.join("ai", "weights", "router", "best.pt")
    router = RouterService(model_path)
    
    if router.mock_mode:
        print("[Warning] Router: Mock 모드 활성화 (가중치 없음)")
    else:
        print(f"[Model] Router 모델 로드 완료: {model_path}")
    
    return router


def load_engine_yolo_model():
    """YOLOv8 엔진룸 부품 감지 모델 로드 (26종)"""
    print("[Model] Loading Engine YOLO Model (26 parts)...")
    
    model_path = os.path.join("ai", "weights", "engine", "best.pt")
    
    if not os.path.exists(model_path):
        print(f"[Warning] Engine YOLO 가중치 없음: {model_path}")
        fallback = os.path.join("ai", "weights", "yolov8n.pt")
        if os.path.exists(fallback):
            print(f"[Warning] Fallback 모델 사용: {fallback}")
            return YOLO(fallback)
        return None
    
    print(f"[Model] Engine YOLO 로드: {model_path}")
    return YOLO(model_path)


def load_dashboard_yolo_model():
    """Dashboard 경고등 YOLO 모델 로드 (10종)"""
    print("[Model] Loading Dashboard YOLO Model (10 warnings)...")
    
    model_path = os.path.join("ai", "weights", "dashboard", "best.pt")
    
    if not os.path.exists(model_path):
        print(f"[Warning] Dashboard YOLO 가중치 없음: {model_path}")
        return None
    
    print(f"[Model] Dashboard YOLO 로드: {model_path}")
    return YOLO(model_path)


def load_exterior_yolo_model():
    """외관 분석용 통합 YOLO 모델 로드 (Unified 22 Classes)"""
    print("[Model] Loading Exterior Unified YOLO Model...")
    
    # 1. 표준화된 경로 (사용자가 옮긴 위치)
    model_path = os.path.join("ai", "weights", "exterior", "best.pt")
    
    # 2. 하위 호환: 학습 직후의 깊은 경로
    if not os.path.exists(model_path):
        deep_path = os.path.join("ai", "weights", "exterior", "unified_v1", "train", "weights", "best.pt")
        if os.path.exists(deep_path):
            model_path = deep_path
        else:
            # 3. Fallback: 학습 직후 runs 폴더에 있는 경우
            fallback_path = os.path.join("runs", "detect", "ai", "weights", "exterior", "unified_v1", "train", "weights", "best.pt")
            if os.path.exists(fallback_path):
                print(f"[Info] Default path missing. Using fallback: {fallback_path}")
                model_path = fallback_path
            else:
                print(f"[Warning] Unified Exterior YOLO 가중치 없음: {model_path}")
                return None

    print(f"[Model] Exterior Unified YOLO 로드: {model_path}")
    return YOLO(model_path)


def load_tire_yolo_model():
    """타이어 상태 YOLO 모델 로드"""
    print("[Model] Loading Tire YOLO Model...")
    
    model_path = os.path.join("ai", "weights", "tire", "best.pt")
    
    if not os.path.exists(model_path):
        print(f"[Warning] Tire YOLO 가중치 없음: {model_path}")
        return None
    
    print(f"[Model] Tire YOLO 로드: {model_path}")
    return YOLO(model_path)


def load_anomaly_detector():
    """PatchCore 엔진룸 이상 탐지 모델 로드"""
    print("[Model] Loading Anomaly Detector (PatchCore)...")
    from ai.app.services.visual.domains.engine.engine_anomaly_service import AnomalyDetector
    return AnomalyDetector()


# =============================================================================
# Lifespan Context Manager
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    앱 수명 주기 관리
    - 모델 로딩은 Lazy Loading 방식으로 변경 (첫 요청 시 로드)
    """
    # 초기 상태 설정 (None으로 초기화해야 Getter에서 인식 가능)
    app.state.ast_model = None
    app.state.router_model = None
    app.state.engine_yolo_model = None
    app.state.dashboard_yolo_model = None
    app.state.exterior_yolo_model = None
    app.state.tire_yolo_model = None
    app.state.anomaly_detector_model = None

    # [지연 해결 로직] 서버 시작 시 모델을 미리 로드하는 Eager Loading 지원
    if os.getenv("EAGER_MODEL_LOADING", "false").lower() == "true":
        print("\n" + "="*60)
        print("[Warmup] Eager Model Loading 시작... (잠시만 기다려주세요)")
        print("="*60)
        try:
            # Getter를 통해 모델 로드 강제 실행
            app.state.get_router()
            app.state.get_engine_yolo()
            app.state.get_ast_model() # [Add] AST 모델도 Eager Loading에 포함
            print("[Warmup] 주요 모델(Router, Engine YOLO, AST) 로드 완료!")
        except Exception as e:
            print(f"[Warmup Error] 모델 로딩 중 오류 발생: {e}")
            import traceback
            traceback.print_exc()

    try:
        yield
    except asyncio.CancelledError:
        print("[Info] Server shutdown cancelled (Normal behavior during forced exit)")
    finally:
        print("🛑 AI Server 종료 중...")


# =============================================================================
# App Factory
# =============================================================================

def create_app() -> FastAPI:
    app = FastAPI(
        title="Car-Sentry AI Server",
        description="차량 시각/청각 진단 통합 AI API (Router Model 기반)",
        version="2.0.0",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 라우터 등록
    # app.include_router(health_router, prefix="/api/v1", tags=["health"])
    # app.include_router(predict_router, prefix="/api/v1", tags=["predict"])
    # app.include_router(visual_router, prefix="/api/v1", tags=["visual"])
    # app.include_router(audio_router, prefix="/api/v1", tags=["audio"])
    # app.include_router(wear_factor_router, prefix="/api/v1", tags=["wear-factor"])
    # app.include_router(obd_anomaly_router, prefix="/api/v1", tags=["anomaly"])
    # app.include_router(embedding_router, prefix="/api/v1", tags=["embedding"])
    # [Clean-up] 개별 라우터들을 하나하나 수동으로 등록하기보다,
    # 통합 라우터(predict_router) 하나만 /api/v1 접두어로 등록하여 중복을 방지합니다.
    app.include_router(predict_router, prefix="/api/v1")
    
    # 테스트 라우터 (별도 유지)


    # 테스트 라우터
    from ai.app.api.v1.routes.test_router import router as test_router
    from ai.app.api.v1.routes.test_router import connect_router
    app.include_router(test_router, prefix="/api/v1", tags=["test"])
    app.include_router(connect_router, prefix="/api/v1", tags=["connect"])

    # Model Manager (Lazy Loading 지원용) 추가 예정
    _setup_model_getters(app)

    return app


def _setup_model_getters(app: FastAPI):
    """
    필요할 때만 모델을 로드하는 Getter 함수들을 app.state에 등록
    """
    def get_router():
        if app.state.router_model is None:
            app.state.router_model = load_router_model()
        return app.state.router_model

    def get_engine_yolo():
        if app.state.engine_yolo_model is None:
            app.state.engine_yolo_model = load_engine_yolo_model()
        return app.state.engine_yolo_model

    def get_dashboard_yolo():
        if app.state.dashboard_yolo_model is None:
            app.state.dashboard_yolo_model = load_dashboard_yolo_model()
        return app.state.dashboard_yolo_model

    def get_exterior_yolo():
        if app.state.exterior_yolo_model is None:
            app.state.exterior_yolo_model = load_exterior_yolo_model()
        return app.state.exterior_yolo_model

    def get_tire_yolo():
        if app.state.tire_yolo_model is None:
            app.state.tire_yolo_model = load_tire_yolo_model()
        return app.state.tire_yolo_model

    def get_ast_model():
        if app.state.ast_model is None:
            app.state.ast_model = load_ast_model()
        return app.state.ast_model

    def get_anomaly_detector():
        if app.state.anomaly_detector_model is None:
            app.state.anomaly_detector_model = load_anomaly_detector()
        return app.state.anomaly_detector_model

    app.state.get_router = get_router
    app.state.get_engine_yolo = get_engine_yolo
    app.state.get_dashboard_yolo = get_dashboard_yolo
    app.state.get_exterior_yolo = get_exterior_yolo
    app.state.get_tire_yolo = get_tire_yolo
    app.state.get_ast_model = get_ast_model
    app.state.get_anomaly_detector = get_anomaly_detector


app = create_app()


@app.get("/")
def root():
    return {"status": "ok", "message": "Car-Sentry AI Server v2.0 (Router Model)"}
