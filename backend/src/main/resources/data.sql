INSERT INTO
    consumable_items (
        code,
        name,
        default_interval_mileage,
        default_interval_months,
        description
    )
VALUES (
        'ENGINE_OIL',
        '엔진오일',
        10000,
        12,
        '엔진 내부의 마찰 감소 및 냉각, 청정 작용을 하는 오일'
    ),
    (
        'TIRE',
        '타이어',
        50000,
        48,
        '차량의 주행 성능과 안전에 직결되는 타이어 (위치 교환 포함)'
    ),
    (
        'BRAKE_PAD',
        '브레이크 패드',
        30000,
        NULL,
        '제동 시 마찰을 일으켜 차량을 멈추게 하는 패드'
    ),
    (
        'BRAKE_FLUID',
        '브레이크 오일',
        40000,
        24,
        '브레이크 페달의 힘을 캘리퍼로 전달하는 유압 오일'
    ),
    (
        'COOLANT',
        '냉각수',
        40000,
        24,
        '엔진 과열을 막아주는 냉각 액체 (부동액 포함)'
    ),
    (
        'AIR_CON_FILTER',
        '에어컨 필터',
        10000,
        6,
        '차량 실내로 유입되는 공기를 정화하는 필터'
    ),
    (
        'WIPER',
        '와이퍼',
        NULL,
        12,
        '비나 눈이 올 때 시야를 확보해주는 와이퍼 블레이드'
    ),
    (
        'BATTERY',
        '배터리',
        NULL,
        36,
        '차량 시동 및 전장 부품에 전력을 공급하는 배터리'
    ),
    (
        'MISSION_OIL',
        '미션 오일',
        80000,
        NULL,
        '변속기의 원활한 작동을 돕는 변속기 오일'
    );