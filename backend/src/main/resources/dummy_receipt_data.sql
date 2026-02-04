-- 1. 더미 데이터 삽입 스크립트 (사용자 'aaa@aaa.com' 기준)
DO $$
DECLARE
    v_user_id UUID;
    v_vehicle_id UUID;
    v_model_name VARCHAR;
    v_item_id BIGINT;
BEGIN
    -- [1] 사용자 ID 조회
    SELECT user_id INTO v_user_id 
    FROM users 
    WHERE email = 'aaa@aaa.com';

    -- [2] 차량 ID 조회 (Sonata 우선, 없으면 첫 번째 차량)
    SELECT vehicles_id, model_name INTO v_vehicle_id, v_model_name
    FROM vehicles 
    WHERE user_id = v_user_id 
    ORDER BY CASE WHEN model_name LIKE '%Sonata%' OR model_name LIKE '%쏘나타%' THEN 0 ELSE 1 END, created_at DESC
    LIMIT 1;

    -- [3] 소모품(엔진오일) ID 조회
    SELECT id INTO v_item_id 
    FROM consumable_items 
    WHERE code = 'ENGINE_OIL';

    -- [4] 데이터 삽입
    IF v_vehicle_id IS NOT NULL THEN
        RAISE NOTICE 'Target Vehicle: %', v_model_name;
        
        INSERT INTO maintenance_logs (
            maintenance_id,
            vehicle_id,
            maintenance_date,
            mileage_at_maintenance,
            consumable_item_id,
            is_standardized,
            shop_name,
            cost,
            ocr_data,
            memo,
            created_at,
            updated_at
        ) VALUES (
            gen_random_uuid(),
            v_vehicle_id,
            '2024-03-15',
            54000,
            v_item_id,
            true,
            '블루핸즈 역삼점',
            85000,
            '{"shopName": "블루핸즈 역삼점", "date": "2024-03-15", "items": [{"name": "엔진오일 세트", "cost": 85000}]}',
            '엔진오일 교체 (재시도)',
            NOW(),
            NOW()
        );
        RAISE NOTICE '더미 데이터가 [%] 차량에 추가되었습니다.', v_model_name;
    ELSE
        RAISE NOTICE '해당 사용자의 차량을 찾을 수 없습니다.';
    END IF;
END $$;
