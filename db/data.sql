-- Seed data for consumable_items
-- car_model_master is seeded by seed_car_models.sql

-- 1. Consumable Items Master Data
INSERT INTO consumable_items (code, name, default_interval_mileage, description) VALUES 
('ENGINE_OIL', '엔진 오일', 10000, '엔진 내부 윤활 및 이물질 제거'),
('TIRE_FRONT', '앞 타이어', 40000, '전륜 구동축 타이어'),
('TIRE_REAR', '뒤 타이어', 50000, '후륜 타이어'),
('BRAKE_PAD_FRONT', '앞 브레이크 패드', 30000, '전륜 제동 장치 마찰재'),
('BRAKE_PAD_REAR', '뒤 브레이크 패드', 40000, '후륜 제동 장치 마찰재'),
('BATTERY_12V', '12V 배터리', 60000, '차량 시동 및 전장용 납축전지'),
('CABIN_FILTER', '에어컨 필터', 15000, '실내 공기 정화 필터'),
('COOLANT', '냉각수', 40000, '엔진 과열 방지'),
('BRAKE_FLUID', '브레이크 오일', 40000, '유압 제동 전달'),
('SPARK_PLUG', '점화 플러그', 100000, '가솔린 엔진 점화 장치 (백금 기준)');

-- Auto-generated Seed Data for car_model_master removed (using seed_car_models.sql)
