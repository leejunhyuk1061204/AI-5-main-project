-- 1. 필수 확장 기능 활성화
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

CREATE EXTENSION IF NOT EXISTS vector;

-- 2. ENUM 타입 정의
DO $$ BEGIN
    CREATE TYPE user_level AS ENUM ('FREE', 'PREMIUM', 'ADMIN');

CREATE TYPE fuel_type AS ENUM ('GASOLINE', 'DIESEL', 'EV', 'HEV', 'LPG');

CREATE TYPE registration_source AS ENUM ('MANUAL', 'OBD', 'CLOUD');

CREATE TYPE charging_status AS ENUM ('DISCONNECTED', 'CHARGING', 'FULL', 'ERROR');

CREATE TYPE diag_trigger_type AS ENUM ('AUTO', 'DATA', 'VISUAL', 'AUDIO', 'DTC', 'ROUTINE');

CREATE TYPE diag_status AS ENUM ('PENDING', 'PROCESSING', 'REPLY_PROCESSING', 'DONE', 'FAILED');

CREATE TYPE risk_level AS ENUM ('LOW', 'MID', 'HIGH', 'CRITICAL');

CREATE TYPE media_type AS ENUM ('AUDIO', 'IMAGE', 'SNAPSHOT');

CREATE TYPE evidence_status AS ENUM ('REQUESTED', 'UPLOADED', 'FAILED');

CREATE TYPE dtc_type AS ENUM ('STORED', 'PENDING', 'PERMANENT');

CREATE TYPE dtc_status AS ENUM ('ACTIVE', 'RESOLVED', 'CLEARED');

CREATE TYPE dtc_resolution_type AS ENUM ('AUTO', 'MANUAL', 'OBD_CLEAR');

CREATE TYPE noti_type AS ENUM ('ALARM', 'RECALL', 'INFO', 'REPORT');

CREATE TYPE insight_category AS ENUM ('ECO_DRIVING', 'SAFETY', 'MAINTENANCE');

CREATE TYPE recall_status AS ENUM ('OPEN', 'CLOSED');

CREATE TYPE inspection_type AS ENUM ('REGULAR', 'TOTAL');

EXCEPTION WHEN duplicate_object THEN null;

END $$;

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
    deleted_at TIMESTAMP
);

-- 사용자 설정 (2.1.2)
CREATE TABLE IF NOT EXISTS user_settings (
    user_id UUID PRIMARY KEY REFERENCES users (user_id),
    noti_maintenance BOOLEAN DEFAULT TRUE,
    noti_anomaly BOOLEAN DEFAULT TRUE,
    noti_recall BOOLEAN DEFAULT TRUE,
    noti_marketing BOOLEAN DEFAULT FALSE,
    night_push_allowed BOOLEAN DEFAULT FALSE
);

-- 클라우드 계정 (2.1.3)
CREATE TABLE IF NOT EXISTS cloud_accounts (
    account_id UUID PRIMARY KEY DEFAULT uuid_generate_v4 (),
    user_id UUID REFERENCES users (user_id),
    provider VARCHAR(50),
    provider_user_id VARCHAR(255),
    access_token TEXT,
    refresh_token TEXT,
    expires_at TIMESTAMP,
    last_synced_at TIMESTAMP
);

-- 차량 (2.1.4)
CREATE TABLE IF NOT EXISTS vehicles (
    vehicles_id UUID PRIMARY KEY DEFAULT uuid_generate_v4 (),
    user_id UUID REFERENCES users (user_id),
    vin VARCHAR(255) UNIQUE,
    car_number VARCHAR(20),
    manufacturer VARCHAR(50),
    model_name VARCHAR(100),
    model_year INT,
    fuel_type fuel_type,
    total_mileage FLOAT DEFAULT 0,
    is_primary BOOLEAN DEFAULT FALSE,
    registration_source registration_source,
    cloud_linked BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    deleted_at TIMESTAMP
);

-- 차량 모델 마스터 (2.1.5 - Track B Reference)
CREATE TABLE IF NOT EXISTS car_model_master (
    model_id SERIAL PRIMARY KEY,
    manufacturer VARCHAR(50),
    model_name VARCHAR(100),
    model_year INT,
    fuel_type VARCHAR(20),
    displacement INT,
    spec_json JSONB
);

-- 4. 텔레메트리 (Telemetry)

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
    created_at TIMESTAMP DEFAULT NOW()
);

-- AI 진단 결과 (2.3.2)
CREATE TABLE IF NOT EXISTS diag_results (
    diag_result_id UUID PRIMARY KEY DEFAULT uuid_generate_v4 (),
    diag_session_id UUID REFERENCES diag_sessions (diag_session_id),
    final_report TEXT,
    confidence_level VARCHAR(20), -- HIGH | MEDIUM | LOW
    summary TEXT,
    detected_issues JSONB,
    actions_json JSONB,
    requested_actions JSONB,
    risk_level risk_level
);

-- AI 진단 증거 및 미션 (2.3.3)
CREATE TABLE IF NOT EXISTS ai_evidences (
    evidence_id UUID PRIMARY KEY DEFAULT uuid_generate_v4 (),
    diag_session_id UUID REFERENCES diag_sessions (diag_session_id),
    media_type media_type,
    s3_key TEXT,
    ai_analysis JSONB,
    status evidence_status DEFAULT 'UPLOADED',
    request_text TEXT
);

-- 6. 상태 관리 및 히스토리 (Status & History)

-- DTC 고장 코드 이력 (2.4.1)
CREATE TABLE IF NOT EXISTS dtc_history (
    dtc_id UUID PRIMARY KEY DEFAULT uuid_generate_v4 (),
    vehicles_id UUID REFERENCES vehicles (vehicles_id),
    dtc_code VARCHAR(10),
    description TEXT,
    dtc_type dtc_type,
    status dtc_status,
    resolution_type dtc_resolution_type,
    discovered_at TIMESTAMP,
    resolved_at TIMESTAMP
);

-- DTC 고장 시점 스냅샷 (2.4.2)
CREATE TABLE IF NOT EXISTS dtc_freeze_frames (
    frame_id UUID PRIMARY KEY DEFAULT uuid_generate_v4 (),
    dtc_id UUID UNIQUE REFERENCES dtc_history (dtc_id),
    rpm FLOAT,
    speed FLOAT,
    coolant_temp FLOAT,
    engine_load FLOAT,
    ambient_temp FLOAT,
    fuel_pressure FLOAT,
    pids_snapshot JSONB
);

-- 2.4.3 소모품 항목 마스터 (consumable_items) - Reference
CREATE TABLE IF NOT EXISTS consumable_items (
    id SERIAL PRIMARY KEY,
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
    consumable_item_id INT REFERENCES consumable_items (id),
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

-- 정비 차계부 (2.4.4)
CREATE TABLE IF NOT EXISTS maintenance_logs (
    maintenance_id UUID PRIMARY KEY DEFAULT uuid_generate_v4 (),
    vehicles_id UUID REFERENCES vehicles (vehicles_id),
    maintenance_date DATE,
    part_name VARCHAR(50),
    is_standardized BOOLEAN,
    cost INT,
    shop_name VARCHAR(100),
    mileage_at_work FLOAT,
    receipts_s3_key TEXT,
    memo TEXT
);

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

-- 지식 베이스 벡터 (2.5.2)
CREATE TABLE IF NOT EXISTS knowledge_vectors (
    knowledge_id UUID PRIMARY KEY DEFAULT uuid_generate_v4 (),
    category VARCHAR(20),
    content TEXT,
    metadata JSONB, -- { manufacturer, model, year, source, page, dtc_code }
    embedding VECTOR (1024), -- 로컬 AI (mxbai-embed-large) 임베딩 벡터
    content_hash VARCHAR(64) UNIQUE -- 중복 방지용 해시
);

CREATE INDEX IF NOT EXISTS idx_knowledge_metadata ON knowledge_vectors USING GIN (metadata);

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

-- RAG 지식 벡터 저장소 (2.5 - AI/RAG)
-- (Cleaned up duplicate definition)

-- knowledge_vectors 인덱스
CREATE INDEX IF NOT EXISTS idx_knowledge_category ON knowledge_vectors (category);

CREATE INDEX IF NOT EXISTS idx_knowledge_metadata ON knowledge_vectors USING GIN (metadata);