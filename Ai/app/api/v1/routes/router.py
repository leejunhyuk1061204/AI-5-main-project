from fastapi import APIRouter
from Ai.app.schemas.preprocess import AnomalyRequest, AnomalyResponse
import random

router = APIRouter()

@router.post("/anomaly", response_model=AnomalyResponse)
def predict_anomaly(req: AnomalyRequest):
    score = round(random.random(), 4)
    threshold = 0.7

    return AnomalyResponse(
        vehicle_id=req.vehicle_id,
        anomaly_score=score,
        threshold=threshold,
        is_anomaly=(score >= threshold),
        model_version="mock-0.0.1",
    )
