from fastapi import APIRouter, HTTPException
from ai.app.schemas.wear_factor import WearFactorRequest, WearFactorResponse
from datetime import date
import random

router = APIRouter()

@router.post("/predict/wear-factor", response_model=WearFactorResponse)
def predict_wear_factor(req: WearFactorRequest):
    total_mileage = req.vehicle_metadata.total_mileage
    replaced_mileage = req.last_replaced.mileage

    if total_mileage < replaced_mileage:
        raise HTTPException(
            status_code=400,
            detail="vehicle_metadata.total_mileage must be >= last_replaced.mileage",
        )

    # 전처리 최소 구현(feature)
    usage_mileage = total_mileage - replaced_mileage
    days_since_last_replaced = (date.today() - req.last_replaced.replaced_date).days
    wear_factor = round(random.uniform(0.8, 1.5), 2)

    return WearFactorResponse(
        predicted_wear_factor=wear_factor,
        model_version="mock-0.1.0",
    )
