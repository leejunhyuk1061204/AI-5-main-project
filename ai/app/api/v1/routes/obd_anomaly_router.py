from fastapi import APIRouter, HTTPException

from ai.app.schemas.obd_anomaly_schema import ObdAnomalyRequest, ObdAnomalyResponse
from ai.app.services.obd_anomaly.obd_anomaly_service import ObdAnomalyService

router = APIRouter()

svc = ObdAnomalyService()


@router.post("/predict/anomaly", response_model=ObdAnomalyResponse)
def predict_anomaly(req: ObdAnomalyRequest) -> ObdAnomalyResponse:
    try:
        return svc.run(req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"internal error: {e}")
