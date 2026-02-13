-- Consumable items master seed (총 15개, 대표 소모품만)
-- 시드: db/seed_consumable.sql  |  차량모델: db/seed_car_models.sql  |  DTC: db/seed_dtc_data.sql

INSERT INTO consumable_items (code, name, default_interval_mileage, description) VALUES
('ENGINE_OIL', '엔진 오일', 10000, '엔진 내부 윤활 및 이물질 제거'),
('TIRE_FL', '앞왼쪽 타이어', 50000, '전륜 좌측'),
('TIRE_FR', '앞오른쪽 타이어', 50000, '전륜 우측'),
('TIRE_RL', '뒤왼쪽 타이어', 50000, '후륜 좌측'),
('TIRE_RR', '뒤오른쪽 타이어', 50000, '후륜 우측'),
('BRAKE_PAD_FRONT', '앞 브레이크 패드', 30000, '전륜 제동 장치 마찰재'),
('BRAKE_PAD_REAR', '뒤 브레이크 패드', 40000, '후륜 제동 장치 마찰재'),
('BATTERY_12V', '12V 배터리', 60000, '차량 시동 및 전장용 납축전지'),
('COOLANT', '냉각수', 40000, '엔진 과열 방지'),
('AIR_FILTER', '에어클리너', 20000, '엔진 흡기 필터'),
('BRAKE_FLUID', '브레이크 오일', 40000, '유압 제동 전달'),
('SPARK_PLUG', '점화 플러그', 100000, '가솔린 엔진 점화 장치 (백금 기준)'),
('MISSION_OIL', '미션 오일', 80000, '변속기 윤활 및 유압 제어'),
('FUEL_FILTER', '연료 필터', 40000, '연료 내 불순물 제거'),
('OTHER', '기타 정비', 0, '분류되지 않은 일반 정비')
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    default_interval_mileage = EXCLUDED.default_interval_mileage,
    description = EXCLUDED.description;
