-- 현대오일뱅크 주유 영수증 OCR 시뮬레이션 등록 데이터
-- 대상 차량 ID를 모르므로, 첫 번째 차량을 찾아 등록하는 스크립트 예시 (또는 UUID 직접 지정 필요)

-- 1. 현대오일뱅크 주유 내역 등록 (2026-02-06, 75,000원, 휘발유)
INSERT INTO fueling_logs (
    fueling_id, 
    vehicle_id, 
    fuel_type, 
    fuel_amount, 
    unit_price, 
    total_cost, 
    fueling_date, 
    mileage_at_fueling, 
    shop_name, 
    created_at, 
    updated_at
)
SELECT 
    gen_random_uuid(), 
    vehicle_id, 
    'GASOLINE', 
    45.45, 
    1650, 
    75000, 
    '2026-02-06', 
    55000.0, -- 시뮬레이션 주행거리
    '현대오일뱅크 강남점', 
    NOW(), 
    NOW()
FROM vehicles 
LIMIT 1;

-- 2. GS칼텍스 주유 내역 등록 (2026-02-06, 50,000원, 휘발유)
INSERT INTO fueling_logs (
    fueling_id, 
    vehicle_id, 
    fuel_type, 
    fuel_amount, 
    unit_price, 
    total_cost, 
    fueling_date, 
    mileage_at_fueling, 
    shop_name, 
    created_at, 
    updated_at
)
SELECT 
    gen_random_uuid(), 
    vehicle_id, 
    'GASOLINE', 
    30.30, 
    1650, 
    50000, 
    '2026-02-06', 
    55100.0, 
    'GS칼텍스 서초주유소', 
    NOW(), 
    NOW()
FROM vehicles 
LIMIT 1;
