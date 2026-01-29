from fastapi import APIRouter

router = APIRouter(tags=["obd-engine-anomaly"])


@router.post("/predict/anomaly")
def predict_anomaly(payload: dict):
    """
    임시(부트스트랩) 엔드포인트:
    - 라우터 마운트/경로/서버 기동 확인용
    - 다음 단계에서 schema + service 연결로 교체
    """
    return {
        "core": {
            "score": 0.0,
            "threshold": 0.5,
            "is_anomaly": False,
            "data_quality": {"status": "BOOTSTRAP"},
            "top_signals": [],
        },
        "extensions": {
            "electrical": "SKIPPED",
            "brake": "SKIPPED",
            "tire": "SKIPPED",
            "idle": "SKIPPED",
        },
        "debug": {"received_keys": list(payload.keys())},
    }
