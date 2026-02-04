# ai/app/api/v1/routes/wear_factor.py
"""
마모 계수 예측 API 라우터 (Phase 2 - Dummy Logic)
"""
from fastapi import APIRouter, HTTPException
from ai.app.schemas.wear_factor import (
    WearFactorRequest, 
    WearFactorResponse,
    TargetItem
)
from typing import Dict

router = APIRouter()


def calculate_dummy_wear_factors(req: WearFactorRequest) -> Dict[str, float]:
    """
    Dummy 마모 계수 계산 로직
    - Week 1: 간단한 수식 기반
    - Week 2+: XGBoost 모델로 교체 예정
    """
    driving = req.driving_summary
    total_mileage = req.vehicle_metadata.total_mileage_km
    
    # 소모품별 km_since_replacement 계산을 위한 매핑
    mileage_map = {
        ctx.item_code.value: ctx.last_replaced_mileage 
        for ctx in req.consumables_context
    }
    
    wear_factors = {}
    
    # --------------------------------
    # ENGINE_OIL: 공회전 비율 기반
    # --------------------------------
    if TargetItem.ENGINE_OIL.value in mileage_map:
        km_since = total_mileage - mileage_map[TargetItem.ENGINE_OIL.value]
        km_factor = km_since / 10000  # 일반적 오일 수명: 10,000km
        idle_penalty = 1.0 + (driving.idle_ratio * 0.5)
        rpm_penalty = 1.0 + max(0, (driving.max_rpm - 3000) / 5000) if driving.max_rpm else 1.0
        wear_factors["ENGINE_OIL"] = round(min(3.0, km_factor * idle_penalty * rpm_penalty), 2)
    else:
        wear_factors["ENGINE_OIL"] = 1.0
    
    # --------------------------------
    # AIR_FILTER: MAF 효율 기반
    # --------------------------------
    if TargetItem.AIR_FILTER.value in mileage_map:
        km_since = total_mileage - mileage_map[TargetItem.AIR_FILTER.value]
        km_factor = km_since / 15000  # 일반적 에어필터 수명: 15,000km
        # MAF 기준값 대비 효율 (간단한 더미 계산)
        baseline_maf = 20.0
        maf_efficiency = min(1.0, driving.avg_maf / baseline_maf) if driving.avg_maf > 0 else 1.0
        wear_factors["AIR_FILTER"] = round(min(3.0, km_factor * (2.0 - maf_efficiency)), 2)
    else:
        wear_factors["AIR_FILTER"] = 1.1  # 기본값
    
    # --------------------------------
    # COOLANT: 과열 여부 기반
    # --------------------------------
    if TargetItem.COOLANT.value in mileage_map:
        km_since = total_mileage - mileage_map[TargetItem.COOLANT.value]
        km_factor = km_since / 40000  # 일반적 냉각수 수명: 40,000km
        
        if driving.overheat_duration_sec > 0:
            # Arrhenius 법칙 간소화: 과열 시간에 따른 급격한 열화
            overheat_minutes = driving.overheat_duration_sec / 60
            overheat_damage = min(3.0, 1.0 + overheat_minutes * 0.5)
            wear_factors["COOLANT"] = round(km_factor * overheat_damage, 2)
        else:
            # 과열 없음: 주행거리 기반만
            temp_penalty = max(0, (driving.avg_coolant_temp - 90) * 0.02) if driving.avg_coolant_temp else 0
            wear_factors["COOLANT"] = round(min(3.0, km_factor + temp_penalty), 2)
    else:
        wear_factors["COOLANT"] = 1.0 if driving.overheat_duration_sec == 0 else 3.5
    
    # --------------------------------
    # TIRE: 급가속/급제동 기반
    # --------------------------------
    if TargetItem.TIRE.value in mileage_map:
        km_since = total_mileage - mileage_map[TargetItem.TIRE.value]
        km_factor = km_since / 50000  # 일반적 타이어 수명: 50,000km
        
        # 주행 거리당 공격적 운전 지수
        if driving.trip_distance_km > 0:
            aggression = (driving.hard_accel_count * 0.6 + driving.hard_brake_count * 0.4) / driving.trip_distance_km
        else:
            aggression = 0
        
        wear_factors["TIRE"] = round(min(3.0, km_factor * (1 + aggression * 3.0)), 2)
    else:
        wear_factors["TIRE"] = round(1.0 + (driving.hard_accel_count * 0.03), 2)
    
    # --------------------------------
    # BRAKE_PAD: 급제동 + 속도 기반
    # --------------------------------
    if TargetItem.BRAKE_PAD.value in mileage_map:
        km_since = total_mileage - mileage_map[TargetItem.BRAKE_PAD.value]
        km_factor = km_since / 60000  # 일반적 브레이크 패드 수명: 60,000km
        
        # 제동 에너지 지수 (속도² 비례)
        braking_energy = driving.hard_brake_count * (driving.avg_speed_kmh ** 2) / 10000 if driving.avg_speed_kmh else 0
        
        # 시내 주행 배수 (저속 = 잦은 제동)
        city_multiplier = 1.3 if driving.avg_speed_kmh < 30 else 1.0
        
        wear_factors["BRAKE_PAD"] = round(min(3.0, km_factor * (1 + braking_energy) * city_multiplier), 2)
    else:
        wear_factors["BRAKE_PAD"] = round(1.0 + (driving.hard_brake_count * 0.04), 2)
    
    # 모든 값이 최소 0.1 이상이 되도록 보정
    for key in wear_factors:
        wear_factors[key] = max(0.1, wear_factors[key])
    
    return wear_factors


@router.post("/predict/wear-factor", response_model=WearFactorResponse)
def predict_wear_factor(req: WearFactorRequest):
    """
    소모품 마모 계수 예측 엔드포인트
    
    - 5개 소모품(ENGINE_OIL, AIR_FILTER, COOLANT, TIRE, BRAKE_PAD)의 마모 계수 반환
    - 마모 계수: 1.0 = 표준, 1.5 = 50% 가속 마모, 0.5 = 절반 속도 마모
    """
    # 입력 검증: 주행거리 일관성
    for ctx in req.consumables_context:
        if req.vehicle_metadata.total_mileage_km < ctx.last_replaced_mileage:
            raise HTTPException(
                status_code=400,
                detail=f"total_mileage_km({req.vehicle_metadata.total_mileage_km}) must be >= "
                       f"last_replaced_mileage({ctx.last_replaced_mileage}) for {ctx.item_code.value}"
            )
    
    # Dummy 계산 로직 호출
    wear_factors = calculate_dummy_wear_factors(req)
    
    return WearFactorResponse(
        wear_factors=wear_factors,
        model_version="dummy-v1.0.0"
    )
