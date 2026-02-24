-- 1. 필수 확장 기능 활성화
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

CREATE EXTENSION IF NOT EXISTS vector;

-- 2. ENUM 타입 정의
DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_level') THEN CREATE TYPE user_level AS ENUM ('FREE', 'PREMIUM', 'BUSINESS');

END IF;

END $$;

DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'fuel_type') THEN CREATE TYPE fuel_type AS ENUM ('GASOLINE', 'DIESEL', 'EV', 'HEV', 'LPG'); END IF; END $$;

DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'registration_source') THEN CREATE TYPE registration_source AS ENUM ('MANUAL', 'OBD', 'CLOUD'); END IF; END $$;

DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'charging_status') THEN CREATE TYPE charging_status AS ENUM ('DISCONNECTED', 'CHARGING', 'FULL', 'ERROR'); END IF; END $$;

DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'diag_trigger_type') THEN CREATE TYPE diag_trigger_type AS ENUM ('AUTO', 'DATA', 'VISUAL', 'AUDIO','DTC','ROUTINE'); END IF; END $$;

DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'diag_status') THEN CREATE TYPE diag_status AS ENUM ('PENDING', 'PROCESSING', 'REPLY_PROCESSING', 'DONE', 'FAILED'); END IF; END $$;

DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'risk_level') THEN CREATE TYPE risk_level AS ENUM ('LOW', 'MID', 'HIGH', 'CRITICAL'); END IF; END $$;

DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'media_type') THEN CREATE TYPE media_type AS ENUM ('AUDIO', 'IMAGE', 'SNAPSHOT'); END IF; END $$;

DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'evidence_status') THEN CREATE TYPE evidence_status AS ENUM ('REQUESTED', 'UPLOADED', 'FAILED'); END IF; END $$;

DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'dtc_type') THEN CREATE TYPE dtc_type AS ENUM ('STORED', 'PENDING', 'PERMANENT', 'FREEZE_FRAME'); END IF; END $$;

DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'dtc_status') THEN CREATE TYPE dtc_status AS ENUM ('ACTIVE', 'RESOLVED', 'CLEARED', 'PENDING', 'STORED'); END IF; END $$;

DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'dtc_resolution_type') THEN CREATE TYPE dtc_resolution_type AS ENUM ('AUTO', 'MANUAL', 'OBD_CLEAR'); END IF; END $$;

DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'noti_type') THEN CREATE TYPE noti_type AS ENUM ('ALARM', 'RECALL', 'INFO', 'REPORT'); END IF; END $$;

DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'insight_category') THEN CREATE TYPE insight_category AS ENUM ('ECO_DRIVING', 'SAFETY', 'MAINTENANCE'); END IF; END $$;

DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'recall_status') THEN CREATE TYPE recall_status AS ENUM ('OPEN', 'CLOSED'); END IF; END $$;

DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'inspection_type') THEN CREATE TYPE inspection_type AS ENUM ('REGULAR', 'TOTAL'); END IF; END $$;

-- 3. 테이블 생성 (Core)

-- 사용자 (2.1.1)
CREATE TABLE IF NOT EXISTS users (
    user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4 (),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255),
    nickname VARCHAR(50),
    fcm_token VARCHAR(255),
    user_level user_level DEFAULT 'FREE',
    membership_expiry TIMESTAMP,
    last_login_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    deleted_at TIMESTAMP,
    profile_image OID,
    kakao_sid VARCHAR(255)
);

ALTER TABLE users ADD COLUMN IF NOT EXISTS kakao_sid VARCHAR(255);

-- 사용자 설정 (2.1.2)
CREATE TABLE IF NOT EXISTS user_settings (
    user_id UUID PRIMARY KEY REFERENCES users (user_id),
    noti_maintenance BOOLEAN DEFAULT TRUE,
    noti_anomaly BOOLEAN DEFAULT TRUE, -- AI 진단 리포트 알림 (Post-Trip report) 수신 여부
    noti_dtc_tts BOOLEAN DEFAULT TRUE,
    noti_marketing BOOLEAN DEFAULT FALSE,
    night_push_allowed BOOLEAN DEFAULT FALSE
);

-- 클라우드 계정 (2.1.3)
CREATE TABLE IF NOT EXISTS cloud_accounts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4 (),
    user_id UUID NOT NULL REFERENCES users (user_id),
    provider VARCHAR(50) NOT NULL,
    provider_user_id VARCHAR(255),
    access_token TEXT,
    refresh_token TEXT,
    expires_at TIMESTAMP,
    last_synced_at TIMESTAMP,
    status VARCHAR(50) NOT NULL DEFAULT 'DISCONNECTED',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 차량 (2.1.4)
-- 기존 DB에 obd_device_id 컬럼이 있으면: ALTER TABLE vehicles DROP COLUMN IF EXISTS obd_device_id;
CREATE TABLE IF NOT EXISTS vehicles (
    vehicles_id UUID PRIMARY KEY DEFAULT uuid_generate_v4 (),
    user_id UUID REFERENCES users (user_id),
    vin VARCHAR(255) UNIQUE,
    car_number VARCHAR(20),
    manufacturer_ko VARCHAR(50),
    manufacturer_en VARCHAR(50),
    model_name_ko VARCHAR(100),
    model_name_en VARCHAR(100),
    model_year INT,
    fuel_type fuel_type,
    total_mileage FLOAT DEFAULT 0,
    is_primary BOOLEAN DEFAULT FALSE,
    registration_source registration_source,
    cloud_linked BOOLEAN DEFAULT FALSE,
    nickname VARCHAR(50),
    memo TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    deleted_at TIMESTAMP
);

-- 차량 모델 마스터 (2.1.5 - Track B Reference)
CREATE TABLE IF NOT EXISTS car_model_master (
    model_id BIGSERIAL PRIMARY KEY,
    manufacturer_ko VARCHAR(50),
    manufacturer_en VARCHAR(50),
    model_name_ko VARCHAR(100),
    model_name_en VARCHAR(100),
    model_year INT,
    fuel_type VARCHAR(20),
    displacement INT,
    spec_json JSONB,
    CONSTRAINT unique_car_model UNIQUE (
        manufacturer_ko,
        model_name_ko,
        model_year,
        fuel_type
    )
);

-- 4. 텔레메트리 (Telemetry)

-- OBD 장치 목록 (2.2.0) - 사용자 소유 OBD 어댑터
CREATE TABLE IF NOT EXISTS obd_devices (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4 (),
    user_id UUID NOT NULL REFERENCES users (user_id),
    device_id VARCHAR(255) NOT NULL,
    device_type VARCHAR(20) NOT NULL,
    name VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP,
    UNIQUE (user_id, device_id)
);

-- OBD 장치-차량 연결 히스토리 (CALID/CVN, 마지막 연결)
CREATE TABLE IF NOT EXISTS obd_device_vehicle_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4 (),
    obd_device_id UUID NOT NULL REFERENCES obd_devices (id),
    vehicles_id UUID NOT NULL REFERENCES vehicles (vehicles_id),
    calid VARCHAR(255),
    cvn VARCHAR(255),
    last_connected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_obd_history_device_last ON obd_device_vehicle_history (
    obd_device_id,
    last_connected_at DESC
);

CREATE INDEX IF NOT EXISTS idx_obd_history_device_calid_cvn ON obd_device_vehicle_history (obd_device_id, calid, cvn);

-- OBD 실시간 로그 (2.2.1) - TimescaleDB
CREATE TABLE IF NOT EXISTS obd_logs (
    time TIMESTAMPTZ NOT NULL,
    vehicles_id UUID NOT NULL REFERENCES vehicles (vehicles_id),
    rpm FLOAT,
    speed FLOAT,
    voltage FLOAT,
    coolant_temp FLOAT,
    engine_load FLOAT,
    fuel_trim_short FLOAT,
    fuel_trim_long FLOAT,
    intake_temp FLOAT,
    map FLOAT,
    maf FLOAT,
    throttle_pos FLOAT,
    engine_runtime INT,
    json_extra JSONB
);
-- 시계열 테이블로 변환
SELECT create_hypertable (
        'obd_logs', 'time', if_not_exists => TRUE
    );
-- 리텐션 정책 (7일)
SELECT add_retention_policy (
        'obd_logs', INTERVAL '3 days', if_not_exists => TRUE
    );

-- 클라우드 동기화 데이터 (2.2.2)
CREATE TABLE IF NOT EXISTS cloud_telemetry (
    telemetry_id UUID PRIMARY KEY DEFAULT uuid_generate_v4 (),
    last_synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    vehicles_id UUID NOT NULL REFERENCES vehicles (vehicles_id),

-- 진단 (Diagnostics)
odometer FLOAT, -- 주행거리 (km)
fuel_level FLOAT, -- 연료 잔량 (%)
battery_soc FLOAT, -- 배터리 잔량 (%)
battery_capacity FLOAT, -- EV 배터리 전체 용량 (kWh)
charge_limit FLOAT, -- EV 충전 제한 (%)
engine_oil_life FLOAT, -- 엔진오일 수명 (%)
tire_pressure_fl FLOAT, -- 타이어 공기압 (앞왼쪽)
tire_pressure_fr FLOAT, -- 타이어 공기압 (앞오른쪽)
tire_pressure_rl FLOAT, -- 타이어 공기압 (뒤왼쪽)
tire_pressure_rr FLOAT, -- 타이어 공기압 (뒤오른쪽)

-- 위치 및 환경 (Location & Climate)
latitude FLOAT, -- 위도
longitude FLOAT, -- 경도
inside_temp FLOAT, -- 실내 온도
outside_temp FLOAT, -- 실외 온도

-- 상태 (Status)
door_lock_status VARCHAR(20),    -- 문 잠금 상태 (LOCKED/UNLOCKED)
    window_open_status VARCHAR(20),  -- 창문 열림 상태 (CLOSED/OPEN/PARTIAL)
    trunk_open_status VARCHAR(20),
    hood_open_status VARCHAR(20),
    charging_status charging_status
);

-- 주행 요약 (2.2.3)
CREATE TABLE IF NOT EXISTS trip_summaries (
    start_time TIMESTAMP NOT NULL,
    vehicles_id UUID NOT NULL REFERENCES vehicles (vehicles_id),
    trip_id UUID NOT NULL UNIQUE DEFAULT uuid_generate_v4 (),
    end_time TIMESTAMP,
    distance FLOAT,
    drive_score INT,
    average_speed FLOAT,
    top_speed FLOAT,
    fuel_consumed FLOAT,
    min_battery_voltage FLOAT,
    max_coolant_temp FLOAT,
    avg_fuel_trim FLOAT,
    max_engine_load FLOAT,
    idle_time INT,
    hard_accel_count INT,
    hard_brake_count INT,
    high_rpm_ratio FLOAT,
    avg_rpm FLOAT,
    avg_engine_load FLOAT,
    avg_maf FLOAT,
    avg_throttle_pos FLOAT,
    overheat_duration_sec INT,
    json_extra JSONB, -- 추가적인 주행 데이터 (경로 등)
    PRIMARY KEY (start_time, vehicles_id)
);

-- 5. AI 진단 및 증거 (Diagnosis & AI)

-- 진단 세션 (2.3.1)
CREATE TABLE IF NOT EXISTS diag_sessions (
    diag_session_id UUID PRIMARY KEY DEFAULT uuid_generate_v4 (),
    vehicles_id UUID REFERENCES vehicles (vehicles_id),
    trip_id UUID, -- trip_summaries.trip_id
    trigger_type diag_trigger_type,
    status diag_status,
    progress_message VARCHAR(1000),
    dtc_context_json TEXT, -- DTC 모드 진단 시 사용된 DTC 정보 저장 (JSON)
    created_at TIMESTAMP DEFAULT NOW()
);

-- AI 진단 결과 (2.3.2)
CREATE TABLE IF NOT EXISTS diag_results (
    diag_result_id UUID PRIMARY KEY DEFAULT uuid_generate_v4 (),
    diag_session_id UUID REFERENCES diag_sessions (diag_session_id),
    final_report TEXT,
    confidence_level VARCHAR(20), -- HIGH | MEDIUM | LOW
    summary TEXT,
    detected_issues TEXT,
    actions_json TEXT,
    requested_action VARCHAR(30),
    response_mode VARCHAR(20),
    confidence_score FLOAT,
    interactive_json TEXT,
    risk_level risk_level
);

-- AI 진단 증거 및 미션 (2.3.3)
CREATE TABLE IF NOT EXISTS ai_evidences (
    evidence_id UUID PRIMARY KEY DEFAULT uuid_generate_v4 (),
    diag_session_id UUID REFERENCES diag_sessions (diag_session_id),
    evidence_type VARCHAR(20), -- IMAGE, AUDIO, DATA
    file_path TEXT NOT NULL,
    inference_label TEXT,
    confidence FLOAT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 6. 상태 관리 및 히스토리 (Status & History)

-- DTC 고장 코드 마스터 (2.4.0)
CREATE TABLE IF NOT EXISTS dtc_codes (
    code VARCHAR(10),
    manufacturer VARCHAR(50) DEFAULT 'GENERIC',
    description_ko TEXT,
    description_en TEXT,
    summary_ko TEXT,
    summary_en TEXT,
    tts_phrase TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (code, manufacturer)
);

-- DTC 고장 코드 이력 (2.4.1)
CREATE TABLE IF NOT EXISTS dtc_history (
    dtc_id UUID PRIMARY KEY DEFAULT uuid_generate_v4 (),
    vehicles_id UUID NOT NULL REFERENCES vehicles (vehicles_id),
    dtc_code VARCHAR(255) NOT NULL,
    description TEXT,
    dtc_type VARCHAR(50),
    status VARCHAR(50),
    severity VARCHAR(20),
    rag_guide TEXT,
    discovered_at TIMESTAMP,
    resolved_at TIMESTAMP
);

-- DTC 고장 시점 스냅샷 (2.4.2)
CREATE TABLE IF NOT EXISTS dtc_freeze_frames (
    frame_id UUID PRIMARY KEY DEFAULT uuid_generate_v4 (),
    dtc_id UUID UNIQUE REFERENCES dtc_history (dtc_id),
    rpm FLOAT,
    speed FLOAT,
    voltage FLOAT,
    coolant_temp FLOAT,
    engine_load FLOAT,
    fuel_trim_short FLOAT,
    fuel_trim_long FLOAT,
    intake_temp FLOAT,
    map FLOAT,
    maf FLOAT,
    throttle_pos FLOAT,
    engine_runtime INT,
    ambient_temp FLOAT,
    fuel_pressure FLOAT,
    pids_snapshot JSONB
);

-- 2.4.3 소모품 항목 마스터 (consumable_items) - Reference
CREATE TABLE IF NOT EXISTS consumable_items (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL, -- ENGINE_OIL, TIRES...
    name VARCHAR(100) NOT NULL,
    default_interval_mileage INT NOT NULL,
    default_interval_months INT,
    description TEXT
);

-- 2.4.4 차량별 소모품 상태 (vehicle_consumables)
CREATE TABLE IF NOT EXISTS vehicle_consumables (
    vehicle_consumable_id UUID PRIMARY KEY DEFAULT uuid_generate_v4 (),
    vehicles_id UUID REFERENCES vehicles (vehicles_id),
    consumable_item_id BIGINT REFERENCES consumable_items (id),
    wear_factor FLOAT DEFAULT 1.0, -- AI 계산 마모율 (1.0 = 표준)
    last_replaced_at TIMESTAMP,
    last_replaced_mileage FLOAT, -- 교체 시점의 주행거리
    is_inferred BOOLEAN DEFAULT FALSE NOT NULL, -- 시스템 추론 데이터 여부
    remaining_life FLOAT, -- (캐싱용) 잔존 수명 %
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP,
    UNIQUE (
        vehicles_id,
        consumable_item_id
    )
);

-- 정비 차계부 (2.4.4) - MaintenanceHistory 엔티티와 동일
CREATE TABLE IF NOT EXISTS maintenance_logs (
    maintenance_id UUID PRIMARY KEY DEFAULT uuid_generate_v4 (),
    vehicle_id UUID NOT NULL REFERENCES vehicles (vehicles_id),
    maintenance_date DATE NOT NULL DEFAULT CURRENT_DATE,
    mileage_at_maintenance DOUBLE PRECISION NOT NULL,
    consumable_item_id BIGINT REFERENCES consumable_items (id),
    is_standardized BOOLEAN,
    shop_name VARCHAR(100),
    cost INT,
    quantity INT DEFAULT 1,
    ocr_data JSONB,
    receipt_id UUID,
    memo TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 주유 차계부 (2.4.5) - FuelingHistory 엔티티와 동기화 (백엔드가 이 스키마를 단일 소스로 관리)
CREATE TABLE IF NOT EXISTS fueling_logs (
    fueling_id UUID PRIMARY KEY DEFAULT uuid_generate_v4 (),
    vehicle_id UUID NOT NULL REFERENCES vehicles (vehicles_id),
    fuel_type fuel_type NOT NULL,
    fueling_date DATE NOT NULL,
    amount DOUBLE PRECISION,
    unit_price INT,
    total_cost INT NOT NULL,
    mileage_at_fueling DOUBLE PRECISION,
    shop_name VARCHAR(100),
    station_name VARCHAR(100),
    memo TEXT,
    receipt_id UUID,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fueling_logs_vehicle_date ON fueling_logs (vehicle_id, fueling_date DESC);

-- 7. 알림 및 지식 베이스 (Notification & Knowledge)

-- 사용자 알림 (2.5.1)
CREATE TABLE IF NOT EXISTS user_notifications (
    notification_id UUID PRIMARY KEY DEFAULT uuid_generate_v4 (),
    user_id UUID REFERENCES users (user_id),
    type noti_type,
    title VARCHAR(255),
    message TEXT,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 앱 내 알림 엔티티 매핑용 (JPA: kr.co.himedia.entity.Notification)
CREATE TABLE IF NOT EXISTS notification (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users (user_id),
    title VARCHAR(255) NOT NULL,
    body TEXT NOT NULL,
    type VARCHAR(50) NOT NULL,
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT notification_type_check CHECK (
        type IN (
            'MAINTENANCE_ALERT',
            'COMMUNITY_ALERT',
            'SYSTEM_ALERT',
            'DTC_ALERT',
            'DIAG_ALERT',
            'TRIP_START',
            'TRIP_END'
        )
    )
);

-- 지식 베이스 벡터 (2.5.2) - RAG용 매뉴얼 청크 (charm.li)
CREATE TABLE IF NOT EXISTS knowledge_vectors (
    knowledge_id UUID PRIMARY KEY DEFAULT uuid_generate_v4 (),
    content TEXT,
    metadata JSONB, -- { manufacturer, year, model, page_number, chunk_index, total_chunks_in_page, source_file, source_zip, chunk_method }
    embedding VECTOR (768), -- nomic-embed-text (768차원) 대응
    content_hash VARCHAR(64) UNIQUE, -- 중복 방지용 해시
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_knowledge_metadata ON knowledge_vectors USING GIN (metadata);

CREATE INDEX IF NOT EXISTS idx_knowledge_embedding ON knowledge_vectors USING hnsw (embedding vector_cosine_ops);

-- 8. 외부 API 연동 및 상세 정보 (External)

-- 차량 상세 제원 (2.6.1)
CREATE TABLE IF NOT EXISTS vehicle_specs (
    spec_id UUID PRIMARY KEY DEFAULT uuid_generate_v4 (),
    vehicles_id UUID REFERENCES vehicles (vehicles_id),
    length FLOAT,
    width FLOAT,
    height FLOAT,
    displacement INT,
    engine_type VARCHAR(50),
    max_power FLOAT,
    max_torque FLOAT,
    tire_size_front VARCHAR(50),
    tire_size_rear VARCHAR(50),
    official_fuel_economy FLOAT,
    spec_source VARCHAR(20) DEFAULT 'MASTER', -- MASTER, CLOUD, MANUAL
    extra_specs JSONB DEFAULT '{}', -- 가변적인 브랜드별 상세 제원
    last_updated TIMESTAMP DEFAULT NOW()
);

-- 리콜 상세 정보 (2.6.2)
CREATE TABLE IF NOT EXISTS vehicle_recalls (
    recall_id UUID PRIMARY KEY DEFAULT uuid_generate_v4 (),
    vehicles_id UUID REFERENCES vehicles (vehicles_id),
    recall_title VARCHAR(255),
    component VARCHAR(100),
    recall_reason TEXT,
    status recall_status,
    recall_date DATE,
    inspection_center VARCHAR(100)
);

-- 정기 및 종합검사 정보 (2.6.3)
CREATE TABLE IF NOT EXISTS vehicle_inspections (
    inspection_id UUID PRIMARY KEY DEFAULT uuid_generate_v4 (),
    vehicles_id UUID REFERENCES vehicles (vehicles_id),
    inspection_type inspection_type,
    validity_start_date DATE,
    validity_end_date DATE,
    result VARCHAR(50),
    next_inspection_date DATE
);

-- 중고차 성능상태점검 기록 (2.6.4)
CREATE TABLE IF NOT EXISTS used_car_performance_records (
    record_id UUID PRIMARY KEY DEFAULT uuid_generate_v4 (),
    vehicles_id UUID REFERENCES vehicles (vehicles_id),
    inspection_date DATE,
    mileage_at_work FLOAT,
    accident_history BOOLEAN,
    flooding_history BOOLEAN,
    frame_damage JSONB,
    engine_transmission VARCHAR(50), -- ENUM 대신 명세서에 맞춰 처리(양호/보통/불량)
    oil_leak VARCHAR(50),
    inspection_sheet_url TEXT
);

-- 9. 실시간 이상 감지 및 인사이트 (Anomaly & Insight)

-- 실시간 이상 감지 이력 (2.7)
CREATE TABLE IF NOT EXISTS anomaly_records (
    anomaly_id UUID PRIMARY KEY DEFAULT uuid_generate_v4 (),
    vehicles_id UUID REFERENCES vehicles (vehicles_id),
    recorded_at TIMESTAMP,
    anomaly_type VARCHAR(50),
    severity risk_level,
    snapshot_data JSONB
);

-- 개인화 인사이트 (2.8)
CREATE TABLE IF NOT EXISTS user_insights (
    insight_id UUID PRIMARY KEY DEFAULT uuid_generate_v4 (),
    user_id UUID REFERENCES users (user_id),
    trip_id UUID,
    category insight_category,
    title VARCHAR(255),
    content_markdown TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    is_read BOOLEAN DEFAULT FALSE
);
-- 결제 시스템 (Payments)
CREATE TABLE IF NOT EXISTS payments (
    payment_id UUID PRIMARY KEY DEFAULT uuid_generate_v4 (),
    user_id UUID REFERENCES users (user_id),
    tid VARCHAR(20),
    order_id VARCHAR(255) NOT NULL UNIQUE,
    item_name VARCHAR(255),
    amount INT,
    status VARCHAR(20) DEFAULT 'PENDING',
    sid VARCHAR(255),
    approved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

ALTER TABLE payments ADD COLUMN IF NOT EXISTS sid VARCHAR(255);

-- 리프레시 토큰 (Refresh Tokens)
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users (user_id),
    token VARCHAR(1000) NOT NULL UNIQUE,
    expiry_date TIMESTAMP NOT NULL
);