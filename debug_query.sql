-- [사용 방법] 전체를 선택해서 실행하거나, Run을 누르세요.
SELECT 
    v.manufacturer AS 제조사,
    v.model_name AS 모델명,
    v.vin AS 차대번호,
    ct.last_synced_at AS 마지막_동기화,
    ct.odometer AS 주행거리_km,
    ct.fuel_level AS 연료량_퍼센트,
    ct.battery_soc AS 배터리_퍼센트,
    ct.engine_oil_life AS 엔진오일_수명,
    ct.charging_status AS 전기차_충전상태,
    ct.battery_capacity AS 배터리_용량,
    ct.charge_limit AS 충전_제한,
    ct.tire_pressure_fl AS 타이어_앞왼쪽,
    ct.tire_pressure_fr AS 타이어_앞오른쪽,
    ct.tire_pressure_rl AS 타이어_뒤왼쪽,
    ct.tire_pressure_rr AS 타이어_뒤오른쪽,
    ct.latitude AS 위도,
    ct.longitude AS 경도,
    ct.door_lock_status AS 문_잠김상태,
    ct.trunk_open_status AS 트렁크_열림,
    ct.hood_open_status AS 보닛_열림
FROM public.cloud_telemetry ct
JOIN public.vehicles v ON ct.vehicles_id = v.vehicles_id
ORDER BY ct.last_synced_at DESC;
