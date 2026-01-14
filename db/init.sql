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

CREATE TYPE diag_trigger_type AS ENUM ('MANUAL', 'DTC', 'ANOMALY', 'ROUTINE');

CREATE TYPE diag_status AS ENUM ('PENDING', 'PROCESSING', 'DONE', 'FAILED');

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
    last_synced_at TIMESTAMPTZ NOT NULL,
    vehicles_id UUID NOT NULL REFERENCES vehicles (vehicles_id),
    odometer FLOAT,
    fuel_level FLOAT,
    battery_soc FLOAT,
    charging_status charging_status,
    PRIMARY KEY (last_synced_at, vehicles_id)
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
    created_at TIMESTAMP DEFAULT NOW()
);

-- AI 진단 결과 (2.3.2)
CREATE TABLE IF NOT EXISTS diag_results (
    diag_result_id UUID PRIMARY KEY DEFAULT uuid_generate_v4 (),
    diag_session_id UUID REFERENCES diag_sessions (diag_session_id),
    final_report TEXT,
    confidence FLOAT,
    detected_issues JSONB,
    actions_json JSONB,
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

-- 소모품 잔여 수명 (2.4.3)
CREATE TABLE IF NOT EXISTS consumables_state (
    consumable_id UUID PRIMARY KEY DEFAULT uuid_generate_v4 (),
    vehicles_id UUID REFERENCES vehicles (vehicles_id),
    part_name VARCHAR(50),
    current_life FLOAT,
    predicted_date DATE,
    last_updated TIMESTAMP
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
    metadata JSONB, -- 추가분: 제조사, 모델, 연식, 페이지 등 필터링용
    embedding vector (1536)
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
    last_updated TIMESTAMP
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

-- Seed data for car_model_master

-- Auto-generated Seed Data for car_model_master
-- Contains popular Korean models with generation-based fuel type mapping
INSERT INTO
    car_model_master (
        manufacturer,
        model_name,
        model_year,
        fuel_type
    )
VALUES (
        'Hyundai',
        'Avante (MD)',
        2010,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Avante (MD)',
        2010,
        'LPG'
    ),
    (
        'Hyundai',
        'Avante (MD)',
        2010,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Avante (MD)',
        2011,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Avante (MD)',
        2011,
        'LPG'
    ),
    (
        'Hyundai',
        'Avante (MD)',
        2011,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Avante (MD)',
        2012,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Avante (MD)',
        2012,
        'LPG'
    ),
    (
        'Hyundai',
        'Avante (MD)',
        2012,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Avante (MD)',
        2013,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Avante (MD)',
        2013,
        'LPG'
    ),
    (
        'Hyundai',
        'Avante (MD)',
        2013,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Avante (MD)',
        2014,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Avante (MD)',
        2014,
        'LPG'
    ),
    (
        'Hyundai',
        'Avante (MD)',
        2014,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Avante (AD)',
        2015,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Avante (AD)',
        2015,
        'LPG'
    ),
    (
        'Hyundai',
        'Avante (AD)',
        2015,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Avante (AD)',
        2016,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Avante (AD)',
        2016,
        'LPG'
    ),
    (
        'Hyundai',
        'Avante (AD)',
        2016,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Avante (AD)',
        2017,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Avante (AD)',
        2017,
        'LPG'
    ),
    (
        'Hyundai',
        'Avante (AD)',
        2017,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Avante (AD)',
        2018,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Avante (AD)',
        2018,
        'LPG'
    ),
    (
        'Hyundai',
        'Avante (AD)',
        2018,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Avante (AD)',
        2019,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Avante (AD)',
        2019,
        'LPG'
    ),
    (
        'Hyundai',
        'Avante (AD)',
        2019,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Avante (CN7)',
        2020,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Avante (CN7)',
        2020,
        'LPG'
    ),
    (
        'Hyundai',
        'Avante (CN7)',
        2020,
        'HEV'
    ),
    (
        'Hyundai',
        'Avante (CN7)',
        2021,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Avante (CN7)',
        2021,
        'LPG'
    ),
    (
        'Hyundai',
        'Avante (CN7)',
        2021,
        'HEV'
    ),
    (
        'Hyundai',
        'Avante (CN7)',
        2022,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Avante (CN7)',
        2022,
        'LPG'
    ),
    (
        'Hyundai',
        'Avante (CN7)',
        2022,
        'HEV'
    ),
    (
        'Hyundai',
        'Avante (CN7)',
        2023,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Avante (CN7)',
        2023,
        'LPG'
    ),
    (
        'Hyundai',
        'Avante (CN7)',
        2023,
        'HEV'
    ),
    (
        'Hyundai',
        'Avante (CN7)',
        2024,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Avante (CN7)',
        2024,
        'LPG'
    ),
    (
        'Hyundai',
        'Avante (CN7)',
        2024,
        'HEV'
    ),
    (
        'Hyundai',
        'Sonata (YF)',
        2010,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Sonata (YF)',
        2010,
        'LPG'
    ),
    (
        'Hyundai',
        'Sonata (YF)',
        2010,
        'HEV'
    ),
    (
        'Hyundai',
        'Sonata (YF)',
        2011,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Sonata (YF)',
        2011,
        'LPG'
    ),
    (
        'Hyundai',
        'Sonata (YF)',
        2011,
        'HEV'
    ),
    (
        'Hyundai',
        'Sonata (YF)',
        2012,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Sonata (YF)',
        2012,
        'LPG'
    ),
    (
        'Hyundai',
        'Sonata (YF)',
        2012,
        'HEV'
    ),
    (
        'Hyundai',
        'Sonata (YF)',
        2013,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Sonata (YF)',
        2013,
        'LPG'
    ),
    (
        'Hyundai',
        'Sonata (YF)',
        2013,
        'HEV'
    ),
    (
        'Hyundai',
        'Sonata (LF)',
        2014,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Sonata (LF)',
        2014,
        'LPG'
    ),
    (
        'Hyundai',
        'Sonata (LF)',
        2014,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Sonata (LF)',
        2014,
        'HEV'
    ),
    (
        'Hyundai',
        'Sonata (LF)',
        2014,
        'PHEV'
    ),
    (
        'Hyundai',
        'Sonata (LF)',
        2015,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Sonata (LF)',
        2015,
        'LPG'
    ),
    (
        'Hyundai',
        'Sonata (LF)',
        2015,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Sonata (LF)',
        2015,
        'HEV'
    ),
    (
        'Hyundai',
        'Sonata (LF)',
        2015,
        'PHEV'
    ),
    (
        'Hyundai',
        'Sonata (LF)',
        2016,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Sonata (LF)',
        2016,
        'LPG'
    ),
    (
        'Hyundai',
        'Sonata (LF)',
        2016,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Sonata (LF)',
        2016,
        'HEV'
    ),
    (
        'Hyundai',
        'Sonata (LF)',
        2016,
        'PHEV'
    ),
    (
        'Hyundai',
        'Sonata (LF)',
        2017,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Sonata (LF)',
        2017,
        'LPG'
    ),
    (
        'Hyundai',
        'Sonata (LF)',
        2017,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Sonata (LF)',
        2017,
        'HEV'
    ),
    (
        'Hyundai',
        'Sonata (LF)',
        2017,
        'PHEV'
    ),
    (
        'Hyundai',
        'Sonata (LF)',
        2018,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Sonata (LF)',
        2018,
        'LPG'
    ),
    (
        'Hyundai',
        'Sonata (LF)',
        2018,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Sonata (LF)',
        2018,
        'HEV'
    ),
    (
        'Hyundai',
        'Sonata (LF)',
        2018,
        'PHEV'
    ),
    (
        'Hyundai',
        'Sonata (DN8)',
        2019,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Sonata (DN8)',
        2019,
        'LPG'
    ),
    (
        'Hyundai',
        'Sonata (DN8)',
        2019,
        'HEV'
    ),
    (
        'Hyundai',
        'Sonata (DN8)',
        2020,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Sonata (DN8)',
        2020,
        'LPG'
    ),
    (
        'Hyundai',
        'Sonata (DN8)',
        2020,
        'HEV'
    ),
    (
        'Hyundai',
        'Sonata (DN8)',
        2021,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Sonata (DN8)',
        2021,
        'LPG'
    ),
    (
        'Hyundai',
        'Sonata (DN8)',
        2021,
        'HEV'
    ),
    (
        'Hyundai',
        'Sonata (DN8)',
        2022,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Sonata (DN8)',
        2022,
        'LPG'
    ),
    (
        'Hyundai',
        'Sonata (DN8)',
        2022,
        'HEV'
    ),
    (
        'Hyundai',
        'Sonata (DN8)',
        2023,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Sonata (DN8)',
        2023,
        'LPG'
    ),
    (
        'Hyundai',
        'Sonata (DN8)',
        2023,
        'HEV'
    ),
    (
        'Hyundai',
        'Sonata (DN8)',
        2024,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Sonata (DN8)',
        2024,
        'LPG'
    ),
    (
        'Hyundai',
        'Sonata (DN8)',
        2024,
        'HEV'
    ),
    (
        'Hyundai',
        'Grandeur (HG)',
        2011,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Grandeur (HG)',
        2011,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Grandeur (HG)',
        2011,
        'HEV'
    ),
    (
        'Hyundai',
        'Grandeur (HG)',
        2011,
        'LPG'
    ),
    (
        'Hyundai',
        'Grandeur (HG)',
        2012,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Grandeur (HG)',
        2012,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Grandeur (HG)',
        2012,
        'HEV'
    ),
    (
        'Hyundai',
        'Grandeur (HG)',
        2012,
        'LPG'
    ),
    (
        'Hyundai',
        'Grandeur (HG)',
        2013,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Grandeur (HG)',
        2013,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Grandeur (HG)',
        2013,
        'HEV'
    ),
    (
        'Hyundai',
        'Grandeur (HG)',
        2013,
        'LPG'
    ),
    (
        'Hyundai',
        'Grandeur (HG)',
        2014,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Grandeur (HG)',
        2014,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Grandeur (HG)',
        2014,
        'HEV'
    ),
    (
        'Hyundai',
        'Grandeur (HG)',
        2014,
        'LPG'
    ),
    (
        'Hyundai',
        'Grandeur (HG)',
        2015,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Grandeur (HG)',
        2015,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Grandeur (HG)',
        2015,
        'HEV'
    ),
    (
        'Hyundai',
        'Grandeur (HG)',
        2015,
        'LPG'
    ),
    (
        'Hyundai',
        'Grandeur (IG)',
        2016,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Grandeur (IG)',
        2016,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Grandeur (IG)',
        2016,
        'HEV'
    ),
    (
        'Hyundai',
        'Grandeur (IG)',
        2016,
        'LPG'
    ),
    (
        'Hyundai',
        'Grandeur (IG)',
        2017,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Grandeur (IG)',
        2017,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Grandeur (IG)',
        2017,
        'HEV'
    ),
    (
        'Hyundai',
        'Grandeur (IG)',
        2017,
        'LPG'
    ),
    (
        'Hyundai',
        'Grandeur (IG)',
        2018,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Grandeur (IG)',
        2018,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Grandeur (IG)',
        2018,
        'HEV'
    ),
    (
        'Hyundai',
        'Grandeur (IG)',
        2018,
        'LPG'
    ),
    (
        'Hyundai',
        'Grandeur (IG FL)',
        2019,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Grandeur (IG FL)',
        2019,
        'HEV'
    ),
    (
        'Hyundai',
        'Grandeur (IG FL)',
        2019,
        'LPG'
    ),
    (
        'Hyundai',
        'Grandeur (IG FL)',
        2020,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Grandeur (IG FL)',
        2020,
        'HEV'
    ),
    (
        'Hyundai',
        'Grandeur (IG FL)',
        2020,
        'LPG'
    ),
    (
        'Hyundai',
        'Grandeur (IG FL)',
        2021,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Grandeur (IG FL)',
        2021,
        'HEV'
    ),
    (
        'Hyundai',
        'Grandeur (IG FL)',
        2021,
        'LPG'
    ),
    (
        'Hyundai',
        'Grandeur (GN7)',
        2022,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Grandeur (GN7)',
        2022,
        'HEV'
    ),
    (
        'Hyundai',
        'Grandeur (GN7)',
        2022,
        'LPG'
    ),
    (
        'Hyundai',
        'Grandeur (GN7)',
        2023,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Grandeur (GN7)',
        2023,
        'HEV'
    ),
    (
        'Hyundai',
        'Grandeur (GN7)',
        2023,
        'LPG'
    ),
    (
        'Hyundai',
        'Grandeur (GN7)',
        2024,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Grandeur (GN7)',
        2024,
        'HEV'
    ),
    (
        'Hyundai',
        'Grandeur (GN7)',
        2024,
        'LPG'
    ),
    (
        'Hyundai',
        'Tucson (ix)',
        2010,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Tucson (ix)',
        2010,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Tucson (ix)',
        2011,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Tucson (ix)',
        2011,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Tucson (ix)',
        2012,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Tucson (ix)',
        2012,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Tucson (ix)',
        2013,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Tucson (ix)',
        2013,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Tucson (ix)',
        2014,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Tucson (ix)',
        2014,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Tucson (TL)',
        2015,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Tucson (TL)',
        2015,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Tucson (TL)',
        2016,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Tucson (TL)',
        2016,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Tucson (TL)',
        2017,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Tucson (TL)',
        2017,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Tucson (TL)',
        2018,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Tucson (TL)',
        2018,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Tucson (TL)',
        2019,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Tucson (TL)',
        2019,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Tucson (NX4)',
        2020,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Tucson (NX4)',
        2020,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Tucson (NX4)',
        2020,
        'HEV'
    ),
    (
        'Hyundai',
        'Tucson (NX4)',
        2021,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Tucson (NX4)',
        2021,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Tucson (NX4)',
        2021,
        'HEV'
    ),
    (
        'Hyundai',
        'Tucson (NX4)',
        2022,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Tucson (NX4)',
        2022,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Tucson (NX4)',
        2022,
        'HEV'
    ),
    (
        'Hyundai',
        'Tucson (NX4)',
        2023,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Tucson (NX4)',
        2023,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Tucson (NX4)',
        2023,
        'HEV'
    ),
    (
        'Hyundai',
        'Tucson (NX4)',
        2024,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Tucson (NX4)',
        2024,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Tucson (NX4)',
        2024,
        'HEV'
    ),
    (
        'Hyundai',
        'Santa Fe (CM)',
        2010,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Santa Fe (CM)',
        2011,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Santa Fe (DM)',
        2012,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Santa Fe (DM)',
        2012,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Santa Fe (DM)',
        2013,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Santa Fe (DM)',
        2013,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Santa Fe (DM)',
        2014,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Santa Fe (DM)',
        2014,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Santa Fe (DM)',
        2015,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Santa Fe (DM)',
        2015,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Santa Fe (DM)',
        2016,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Santa Fe (DM)',
        2016,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Santa Fe (DM)',
        2017,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Santa Fe (DM)',
        2017,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Santa Fe (TM)',
        2018,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Santa Fe (TM)',
        2018,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Santa Fe (TM)',
        2019,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Santa Fe (TM)',
        2019,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Santa Fe (TM)',
        2020,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Santa Fe (TM)',
        2020,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Santa Fe (TM)',
        2021,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Santa Fe (TM)',
        2021,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Santa Fe (TM)',
        2022,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Santa Fe (TM)',
        2022,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Santa Fe (MX5)',
        2023,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Santa Fe (MX5)',
        2023,
        'HEV'
    ),
    (
        'Hyundai',
        'Santa Fe (MX5)',
        2024,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Santa Fe (MX5)',
        2024,
        'HEV'
    ),
    (
        'Hyundai',
        'Palisade',
        2018,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Palisade',
        2018,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Palisade',
        2019,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Palisade',
        2019,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Palisade',
        2020,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Palisade',
        2020,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Palisade',
        2021,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Palisade',
        2021,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Palisade',
        2022,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Palisade',
        2022,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Palisade',
        2023,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Palisade',
        2023,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Palisade',
        2024,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Palisade',
        2024,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Casper',
        2021,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Casper',
        2022,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Casper',
        2023,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Casper',
        2024,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Kona (OS)',
        2017,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Kona (OS)',
        2017,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Kona (OS)',
        2017,
        'HEV'
    ),
    (
        'Hyundai',
        'Kona (OS)',
        2017,
        'EV'
    ),
    (
        'Hyundai',
        'Kona (OS)',
        2018,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Kona (OS)',
        2018,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Kona (OS)',
        2018,
        'HEV'
    ),
    (
        'Hyundai',
        'Kona (OS)',
        2018,
        'EV'
    ),
    (
        'Hyundai',
        'Kona (OS)',
        2019,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Kona (OS)',
        2019,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Kona (OS)',
        2019,
        'HEV'
    ),
    (
        'Hyundai',
        'Kona (OS)',
        2019,
        'EV'
    ),
    (
        'Hyundai',
        'Kona (OS)',
        2020,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Kona (OS)',
        2020,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Kona (OS)',
        2020,
        'HEV'
    ),
    (
        'Hyundai',
        'Kona (OS)',
        2020,
        'EV'
    ),
    (
        'Hyundai',
        'Kona (OS)',
        2021,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Kona (OS)',
        2021,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Kona (OS)',
        2021,
        'HEV'
    ),
    (
        'Hyundai',
        'Kona (OS)',
        2021,
        'EV'
    ),
    (
        'Hyundai',
        'Kona (OS)',
        2022,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Kona (OS)',
        2022,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Kona (OS)',
        2022,
        'HEV'
    ),
    (
        'Hyundai',
        'Kona (OS)',
        2022,
        'EV'
    ),
    (
        'Hyundai',
        'Kona (SX2)',
        2023,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Kona (SX2)',
        2023,
        'HEV'
    ),
    (
        'Hyundai',
        'Kona (SX2)',
        2023,
        'EV'
    ),
    (
        'Hyundai',
        'Kona (SX2)',
        2024,
        'GASOLINE'
    ),
    (
        'Hyundai',
        'Kona (SX2)',
        2024,
        'HEV'
    ),
    (
        'Hyundai',
        'Kona (SX2)',
        2024,
        'EV'
    ),
    (
        'Hyundai',
        'Staria',
        2021,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Staria',
        2021,
        'LPG'
    ),
    (
        'Hyundai',
        'Staria',
        2021,
        'HEV'
    ),
    (
        'Hyundai',
        'Staria',
        2022,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Staria',
        2022,
        'LPG'
    ),
    (
        'Hyundai',
        'Staria',
        2022,
        'HEV'
    ),
    (
        'Hyundai',
        'Staria',
        2023,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Staria',
        2023,
        'LPG'
    ),
    (
        'Hyundai',
        'Staria',
        2023,
        'HEV'
    ),
    (
        'Hyundai',
        'Staria',
        2024,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Staria',
        2024,
        'LPG'
    ),
    (
        'Hyundai',
        'Staria',
        2024,
        'HEV'
    ),
    (
        'Hyundai',
        'Starex (Grand)',
        2010,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Starex (Grand)',
        2010,
        'LPG'
    ),
    (
        'Hyundai',
        'Starex (Grand)',
        2011,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Starex (Grand)',
        2011,
        'LPG'
    ),
    (
        'Hyundai',
        'Starex (Grand)',
        2012,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Starex (Grand)',
        2012,
        'LPG'
    ),
    (
        'Hyundai',
        'Starex (Grand)',
        2013,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Starex (Grand)',
        2013,
        'LPG'
    ),
    (
        'Hyundai',
        'Starex (Grand)',
        2014,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Starex (Grand)',
        2014,
        'LPG'
    ),
    (
        'Hyundai',
        'Starex (Grand)',
        2015,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Starex (Grand)',
        2015,
        'LPG'
    ),
    (
        'Hyundai',
        'Starex (Grand)',
        2016,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Starex (Grand)',
        2016,
        'LPG'
    ),
    (
        'Hyundai',
        'Starex (Grand)',
        2017,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Starex (Grand)',
        2017,
        'LPG'
    ),
    (
        'Hyundai',
        'Starex (Grand)',
        2018,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Starex (Grand)',
        2018,
        'LPG'
    ),
    (
        'Hyundai',
        'Starex (Grand)',
        2019,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Starex (Grand)',
        2019,
        'LPG'
    ),
    (
        'Hyundai',
        'Starex (Grand)',
        2020,
        'DIESEL'
    ),
    (
        'Hyundai',
        'Starex (Grand)',
        2020,
        'LPG'
    ),
    (
        'Hyundai',
        'Ioniq 5',
        2021,
        'EV'
    ),
    (
        'Hyundai',
        'Ioniq 5',
        2022,
        'EV'
    ),
    (
        'Hyundai',
        'Ioniq 5',
        2023,
        'EV'
    ),
    (
        'Hyundai',
        'Ioniq 5',
        2024,
        'EV'
    ),
    (
        'Hyundai',
        'Ioniq 6',
        2022,
        'EV'
    ),
    (
        'Hyundai',
        'Ioniq 6',
        2023,
        'EV'
    ),
    (
        'Hyundai',
        'Ioniq 6',
        2024,
        'EV'
    ),
    (
        'Kia',
        'K3 (YD)',
        2012,
        'GASOLINE'
    ),
    (
        'Kia',
        'K3 (YD)',
        2012,
        'DIESEL'
    ),
    (
        'Kia',
        'K3 (YD)',
        2013,
        'GASOLINE'
    ),
    (
        'Kia',
        'K3 (YD)',
        2013,
        'DIESEL'
    ),
    (
        'Kia',
        'K3 (YD)',
        2014,
        'GASOLINE'
    ),
    (
        'Kia',
        'K3 (YD)',
        2014,
        'DIESEL'
    ),
    (
        'Kia',
        'K3 (YD)',
        2015,
        'GASOLINE'
    ),
    (
        'Kia',
        'K3 (YD)',
        2015,
        'DIESEL'
    ),
    (
        'Kia',
        'K3 (YD)',
        2016,
        'GASOLINE'
    ),
    (
        'Kia',
        'K3 (YD)',
        2016,
        'DIESEL'
    ),
    (
        'Kia',
        'K3 (YD)',
        2017,
        'GASOLINE'
    ),
    (
        'Kia',
        'K3 (YD)',
        2017,
        'DIESEL'
    ),
    (
        'Kia',
        'K3 (BD)',
        2018,
        'GASOLINE'
    ),
    (
        'Kia',
        'K3 (BD)',
        2019,
        'GASOLINE'
    ),
    (
        'Kia',
        'K3 (BD)',
        2020,
        'GASOLINE'
    ),
    (
        'Kia',
        'K3 (BD)',
        2021,
        'GASOLINE'
    ),
    (
        'Kia',
        'K3 (BD)',
        2022,
        'GASOLINE'
    ),
    (
        'Kia',
        'K3 (BD)',
        2023,
        'GASOLINE'
    ),
    (
        'Kia',
        'K3 (BD)',
        2024,
        'GASOLINE'
    ),
    (
        'Kia',
        'K5 (TF)',
        2010,
        'GASOLINE'
    ),
    ('Kia', 'K5 (TF)', 2010, 'LPG'),
    ('Kia', 'K5 (TF)', 2010, 'HEV'),
    (
        'Kia',
        'K5 (TF)',
        2011,
        'GASOLINE'
    ),
    ('Kia', 'K5 (TF)', 2011, 'LPG'),
    ('Kia', 'K5 (TF)', 2011, 'HEV'),
    (
        'Kia',
        'K5 (TF)',
        2012,
        'GASOLINE'
    ),
    ('Kia', 'K5 (TF)', 2012, 'LPG'),
    ('Kia', 'K5 (TF)', 2012, 'HEV'),
    (
        'Kia',
        'K5 (TF)',
        2013,
        'GASOLINE'
    ),
    ('Kia', 'K5 (TF)', 2013, 'LPG'),
    ('Kia', 'K5 (TF)', 2013, 'HEV'),
    (
        'Kia',
        'K5 (TF)',
        2014,
        'GASOLINE'
    ),
    ('Kia', 'K5 (TF)', 2014, 'LPG'),
    ('Kia', 'K5 (TF)', 2014, 'HEV'),
    (
        'Kia',
        'K5 (JF)',
        2015,
        'GASOLINE'
    ),
    ('Kia', 'K5 (JF)', 2015, 'LPG'),
    (
        'Kia',
        'K5 (JF)',
        2015,
        'DIESEL'
    ),
    ('Kia', 'K5 (JF)', 2015, 'HEV'),
    (
        'Kia',
        'K5 (JF)',
        2016,
        'GASOLINE'
    ),
    ('Kia', 'K5 (JF)', 2016, 'LPG'),
    (
        'Kia',
        'K5 (JF)',
        2016,
        'DIESEL'
    ),
    ('Kia', 'K5 (JF)', 2016, 'HEV'),
    (
        'Kia',
        'K5 (JF)',
        2017,
        'GASOLINE'
    ),
    ('Kia', 'K5 (JF)', 2017, 'LPG'),
    (
        'Kia',
        'K5 (JF)',
        2017,
        'DIESEL'
    ),
    ('Kia', 'K5 (JF)', 2017, 'HEV'),
    (
        'Kia',
        'K5 (JF)',
        2018,
        'GASOLINE'
    ),
    ('Kia', 'K5 (JF)', 2018, 'LPG'),
    (
        'Kia',
        'K5 (JF)',
        2018,
        'DIESEL'
    ),
    ('Kia', 'K5 (JF)', 2018, 'HEV'),
    (
        'Kia',
        'K5 (DL3)',
        2019,
        'GASOLINE'
    ),
    (
        'Kia',
        'K5 (DL3)',
        2019,
        'LPG'
    ),
    (
        'Kia',
        'K5 (DL3)',
        2019,
        'HEV'
    ),
    (
        'Kia',
        'K5 (DL3)',
        2020,
        'GASOLINE'
    ),
    (
        'Kia',
        'K5 (DL3)',
        2020,
        'LPG'
    ),
    (
        'Kia',
        'K5 (DL3)',
        2020,
        'HEV'
    ),
    (
        'Kia',
        'K5 (DL3)',
        2021,
        'GASOLINE'
    ),
    (
        'Kia',
        'K5 (DL3)',
        2021,
        'LPG'
    ),
    (
        'Kia',
        'K5 (DL3)',
        2021,
        'HEV'
    ),
    (
        'Kia',
        'K5 (DL3)',
        2022,
        'GASOLINE'
    ),
    (
        'Kia',
        'K5 (DL3)',
        2022,
        'LPG'
    ),
    (
        'Kia',
        'K5 (DL3)',
        2022,
        'HEV'
    ),
    (
        'Kia',
        'K5 (DL3)',
        2023,
        'GASOLINE'
    ),
    (
        'Kia',
        'K5 (DL3)',
        2023,
        'LPG'
    ),
    (
        'Kia',
        'K5 (DL3)',
        2023,
        'HEV'
    ),
    (
        'Kia',
        'K5 (DL3)',
        2024,
        'GASOLINE'
    ),
    (
        'Kia',
        'K5 (DL3)',
        2024,
        'LPG'
    ),
    (
        'Kia',
        'K5 (DL3)',
        2024,
        'HEV'
    ),
    (
        'Kia',
        'K7 (VG)',
        2010,
        'GASOLINE'
    ),
    ('Kia', 'K7 (VG)', 2010, 'LPG'),
    (
        'Kia',
        'K7 (VG)',
        2011,
        'GASOLINE'
    ),
    ('Kia', 'K7 (VG)', 2011, 'LPG'),
    ('Kia', 'K7 (VG)', 2011, 'HEV'),
    (
        'Kia',
        'K7 (VG)',
        2012,
        'GASOLINE'
    ),
    ('Kia', 'K7 (VG)', 2012, 'LPG'),
    ('Kia', 'K7 (VG)', 2012, 'HEV'),
    (
        'Kia',
        'K7 (VG)',
        2013,
        'GASOLINE'
    ),
    ('Kia', 'K7 (VG)', 2013, 'LPG'),
    ('Kia', 'K7 (VG)', 2013, 'HEV'),
    (
        'Kia',
        'K7 (VG)',
        2014,
        'GASOLINE'
    ),
    ('Kia', 'K7 (VG)', 2014, 'LPG'),
    ('Kia', 'K7 (VG)', 2014, 'HEV'),
    (
        'Kia',
        'K7 (VG)',
        2015,
        'GASOLINE'
    ),
    ('Kia', 'K7 (VG)', 2015, 'LPG'),
    ('Kia', 'K7 (VG)', 2015, 'HEV'),
    (
        'Kia',
        'K7 (YG)',
        2016,
        'GASOLINE'
    ),
    (
        'Kia',
        'K7 (YG)',
        2016,
        'DIESEL'
    ),
    ('Kia', 'K7 (YG)', 2016, 'LPG'),
    ('Kia', 'K7 (YG)', 2016, 'HEV'),
    (
        'Kia',
        'K7 (YG)',
        2017,
        'GASOLINE'
    ),
    (
        'Kia',
        'K7 (YG)',
        2017,
        'DIESEL'
    ),
    ('Kia', 'K7 (YG)', 2017, 'LPG'),
    ('Kia', 'K7 (YG)', 2017, 'HEV'),
    (
        'Kia',
        'K7 (YG)',
        2018,
        'GASOLINE'
    ),
    (
        'Kia',
        'K7 (YG)',
        2018,
        'DIESEL'
    ),
    ('Kia', 'K7 (YG)', 2018, 'LPG'),
    ('Kia', 'K7 (YG)', 2018, 'HEV'),
    (
        'Kia',
        'K7 (YG)',
        2019,
        'GASOLINE'
    ),
    (
        'Kia',
        'K7 (YG)',
        2019,
        'DIESEL'
    ),
    ('Kia', 'K7 (YG)', 2019, 'LPG'),
    ('Kia', 'K7 (YG)', 2019, 'HEV'),
    (
        'Kia',
        'K7 (YG)',
        2020,
        'GASOLINE'
    ),
    (
        'Kia',
        'K7 (YG)',
        2020,
        'DIESEL'
    ),
    ('Kia', 'K7 (YG)', 2020, 'LPG'),
    ('Kia', 'K7 (YG)', 2020, 'HEV'),
    (
        'Kia',
        'K8 (GL3)',
        2021,
        'GASOLINE'
    ),
    (
        'Kia',
        'K8 (GL3)',
        2021,
        'LPG'
    ),
    (
        'Kia',
        'K8 (GL3)',
        2021,
        'HEV'
    ),
    (
        'Kia',
        'K8 (GL3)',
        2022,
        'GASOLINE'
    ),
    (
        'Kia',
        'K8 (GL3)',
        2022,
        'LPG'
    ),
    (
        'Kia',
        'K8 (GL3)',
        2022,
        'HEV'
    ),
    (
        'Kia',
        'K8 (GL3)',
        2023,
        'GASOLINE'
    ),
    (
        'Kia',
        'K8 (GL3)',
        2023,
        'LPG'
    ),
    (
        'Kia',
        'K8 (GL3)',
        2023,
        'HEV'
    ),
    (
        'Kia',
        'K8 (GL3)',
        2024,
        'GASOLINE'
    ),
    (
        'Kia',
        'K8 (GL3)',
        2024,
        'LPG'
    ),
    (
        'Kia',
        'K8 (GL3)',
        2024,
        'HEV'
    ),
    (
        'Kia',
        'Sportage (SL)',
        2010,
        'DIESEL'
    ),
    (
        'Kia',
        'Sportage (SL)',
        2010,
        'GASOLINE'
    ),
    (
        'Kia',
        'Sportage (SL)',
        2011,
        'DIESEL'
    ),
    (
        'Kia',
        'Sportage (SL)',
        2011,
        'GASOLINE'
    ),
    (
        'Kia',
        'Sportage (SL)',
        2012,
        'DIESEL'
    ),
    (
        'Kia',
        'Sportage (SL)',
        2012,
        'GASOLINE'
    ),
    (
        'Kia',
        'Sportage (SL)',
        2013,
        'DIESEL'
    ),
    (
        'Kia',
        'Sportage (SL)',
        2013,
        'GASOLINE'
    ),
    (
        'Kia',
        'Sportage (SL)',
        2014,
        'DIESEL'
    ),
    (
        'Kia',
        'Sportage (SL)',
        2014,
        'GASOLINE'
    ),
    (
        'Kia',
        'Sportage (QL)',
        2015,
        'DIESEL'
    ),
    (
        'Kia',
        'Sportage (QL)',
        2015,
        'GASOLINE'
    ),
    (
        'Kia',
        'Sportage (QL)',
        2016,
        'DIESEL'
    ),
    (
        'Kia',
        'Sportage (QL)',
        2016,
        'GASOLINE'
    ),
    (
        'Kia',
        'Sportage (QL)',
        2017,
        'DIESEL'
    ),
    (
        'Kia',
        'Sportage (QL)',
        2017,
        'GASOLINE'
    ),
    (
        'Kia',
        'Sportage (QL)',
        2018,
        'DIESEL'
    ),
    (
        'Kia',
        'Sportage (QL)',
        2018,
        'GASOLINE'
    ),
    (
        'Kia',
        'Sportage (QL)',
        2019,
        'DIESEL'
    ),
    (
        'Kia',
        'Sportage (QL)',
        2019,
        'GASOLINE'
    ),
    (
        'Kia',
        'Sportage (QL)',
        2020,
        'DIESEL'
    ),
    (
        'Kia',
        'Sportage (QL)',
        2020,
        'GASOLINE'
    ),
    (
        'Kia',
        'Sportage (NQ5)',
        2021,
        'DIESEL'
    ),
    (
        'Kia',
        'Sportage (NQ5)',
        2021,
        'GASOLINE'
    ),
    (
        'Kia',
        'Sportage (NQ5)',
        2021,
        'HEV'
    ),
    (
        'Kia',
        'Sportage (NQ5)',
        2021,
        'LPG'
    ),
    (
        'Kia',
        'Sportage (NQ5)',
        2022,
        'DIESEL'
    ),
    (
        'Kia',
        'Sportage (NQ5)',
        2022,
        'GASOLINE'
    ),
    (
        'Kia',
        'Sportage (NQ5)',
        2022,
        'HEV'
    ),
    (
        'Kia',
        'Sportage (NQ5)',
        2022,
        'LPG'
    ),
    (
        'Kia',
        'Sportage (NQ5)',
        2023,
        'DIESEL'
    ),
    (
        'Kia',
        'Sportage (NQ5)',
        2023,
        'GASOLINE'
    ),
    (
        'Kia',
        'Sportage (NQ5)',
        2023,
        'HEV'
    ),
    (
        'Kia',
        'Sportage (NQ5)',
        2023,
        'LPG'
    ),
    (
        'Kia',
        'Sportage (NQ5)',
        2024,
        'DIESEL'
    ),
    (
        'Kia',
        'Sportage (NQ5)',
        2024,
        'GASOLINE'
    ),
    (
        'Kia',
        'Sportage (NQ5)',
        2024,
        'HEV'
    ),
    (
        'Kia',
        'Sportage (NQ5)',
        2024,
        'LPG'
    ),
    (
        'Kia',
        'Sorento (R)',
        2010,
        'DIESEL'
    ),
    (
        'Kia',
        'Sorento (R)',
        2010,
        'GASOLINE'
    ),
    (
        'Kia',
        'Sorento (R)',
        2011,
        'DIESEL'
    ),
    (
        'Kia',
        'Sorento (R)',
        2011,
        'GASOLINE'
    ),
    (
        'Kia',
        'Sorento (R)',
        2012,
        'DIESEL'
    ),
    (
        'Kia',
        'Sorento (R)',
        2012,
        'GASOLINE'
    ),
    (
        'Kia',
        'Sorento (R)',
        2013,
        'DIESEL'
    ),
    (
        'Kia',
        'Sorento (R)',
        2013,
        'GASOLINE'
    ),
    (
        'Kia',
        'Sorento (UM)',
        2014,
        'DIESEL'
    ),
    (
        'Kia',
        'Sorento (UM)',
        2014,
        'GASOLINE'
    ),
    (
        'Kia',
        'Sorento (UM)',
        2015,
        'DIESEL'
    ),
    (
        'Kia',
        'Sorento (UM)',
        2015,
        'GASOLINE'
    ),
    (
        'Kia',
        'Sorento (UM)',
        2016,
        'DIESEL'
    ),
    (
        'Kia',
        'Sorento (UM)',
        2016,
        'GASOLINE'
    ),
    (
        'Kia',
        'Sorento (UM)',
        2017,
        'DIESEL'
    ),
    (
        'Kia',
        'Sorento (UM)',
        2017,
        'GASOLINE'
    ),
    (
        'Kia',
        'Sorento (UM)',
        2018,
        'DIESEL'
    ),
    (
        'Kia',
        'Sorento (UM)',
        2018,
        'GASOLINE'
    ),
    (
        'Kia',
        'Sorento (UM)',
        2019,
        'DIESEL'
    ),
    (
        'Kia',
        'Sorento (UM)',
        2019,
        'GASOLINE'
    ),
    (
        'Kia',
        'Sorento (MQ4)',
        2020,
        'DIESEL'
    ),
    (
        'Kia',
        'Sorento (MQ4)',
        2020,
        'GASOLINE'
    ),
    (
        'Kia',
        'Sorento (MQ4)',
        2020,
        'HEV'
    ),
    (
        'Kia',
        'Sorento (MQ4)',
        2021,
        'DIESEL'
    ),
    (
        'Kia',
        'Sorento (MQ4)',
        2021,
        'GASOLINE'
    ),
    (
        'Kia',
        'Sorento (MQ4)',
        2021,
        'HEV'
    ),
    (
        'Kia',
        'Sorento (MQ4)',
        2022,
        'DIESEL'
    ),
    (
        'Kia',
        'Sorento (MQ4)',
        2022,
        'GASOLINE'
    ),
    (
        'Kia',
        'Sorento (MQ4)',
        2022,
        'HEV'
    ),
    (
        'Kia',
        'Sorento (MQ4)',
        2023,
        'DIESEL'
    ),
    (
        'Kia',
        'Sorento (MQ4)',
        2023,
        'GASOLINE'
    ),
    (
        'Kia',
        'Sorento (MQ4)',
        2023,
        'HEV'
    ),
    (
        'Kia',
        'Sorento (MQ4)',
        2024,
        'DIESEL'
    ),
    (
        'Kia',
        'Sorento (MQ4)',
        2024,
        'GASOLINE'
    ),
    (
        'Kia',
        'Sorento (MQ4)',
        2024,
        'HEV'
    ),
    (
        'Kia',
        'Carnival (R)',
        2010,
        'DIESEL'
    ),
    (
        'Kia',
        'Carnival (R)',
        2010,
        'GASOLINE'
    ),
    (
        'Kia',
        'Carnival (R)',
        2011,
        'DIESEL'
    ),
    (
        'Kia',
        'Carnival (R)',
        2011,
        'GASOLINE'
    ),
    (
        'Kia',
        'Carnival (R)',
        2012,
        'DIESEL'
    ),
    (
        'Kia',
        'Carnival (R)',
        2012,
        'GASOLINE'
    ),
    (
        'Kia',
        'Carnival (R)',
        2013,
        'DIESEL'
    ),
    (
        'Kia',
        'Carnival (R)',
        2013,
        'GASOLINE'
    ),
    (
        'Kia',
        'Carnival (YP)',
        2014,
        'DIESEL'
    ),
    (
        'Kia',
        'Carnival (YP)',
        2014,
        'GASOLINE'
    ),
    (
        'Kia',
        'Carnival (YP)',
        2015,
        'DIESEL'
    ),
    (
        'Kia',
        'Carnival (YP)',
        2015,
        'GASOLINE'
    ),
    (
        'Kia',
        'Carnival (YP)',
        2016,
        'DIESEL'
    ),
    (
        'Kia',
        'Carnival (YP)',
        2016,
        'GASOLINE'
    ),
    (
        'Kia',
        'Carnival (YP)',
        2017,
        'DIESEL'
    ),
    (
        'Kia',
        'Carnival (YP)',
        2017,
        'GASOLINE'
    ),
    (
        'Kia',
        'Carnival (YP)',
        2018,
        'DIESEL'
    ),
    (
        'Kia',
        'Carnival (YP)',
        2018,
        'GASOLINE'
    ),
    (
        'Kia',
        'Carnival (YP)',
        2019,
        'DIESEL'
    ),
    (
        'Kia',
        'Carnival (YP)',
        2019,
        'GASOLINE'
    ),
    (
        'Kia',
        'Carnival (KA4)',
        2020,
        'DIESEL'
    ),
    (
        'Kia',
        'Carnival (KA4)',
        2020,
        'GASOLINE'
    ),
    (
        'Kia',
        'Carnival (KA4)',
        2020,
        'HEV'
    ),
    (
        'Kia',
        'Carnival (KA4)',
        2021,
        'DIESEL'
    ),
    (
        'Kia',
        'Carnival (KA4)',
        2021,
        'GASOLINE'
    ),
    (
        'Kia',
        'Carnival (KA4)',
        2021,
        'HEV'
    ),
    (
        'Kia',
        'Carnival (KA4)',
        2022,
        'DIESEL'
    ),
    (
        'Kia',
        'Carnival (KA4)',
        2022,
        'GASOLINE'
    ),
    (
        'Kia',
        'Carnival (KA4)',
        2022,
        'HEV'
    ),
    (
        'Kia',
        'Carnival (KA4)',
        2023,
        'DIESEL'
    ),
    (
        'Kia',
        'Carnival (KA4)',
        2023,
        'GASOLINE'
    ),
    (
        'Kia',
        'Carnival (KA4)',
        2023,
        'HEV'
    ),
    (
        'Kia',
        'Carnival (KA4)',
        2024,
        'DIESEL'
    ),
    (
        'Kia',
        'Carnival (KA4)',
        2024,
        'GASOLINE'
    ),
    (
        'Kia',
        'Carnival (KA4)',
        2024,
        'HEV'
    ),
    (
        'Kia',
        'Niro (DE)',
        2016,
        'HEV'
    ),
    (
        'Kia',
        'Niro (DE)',
        2016,
        'PHEV'
    ),
    (
        'Kia',
        'Niro (DE)',
        2016,
        'EV'
    ),
    (
        'Kia',
        'Niro (DE)',
        2017,
        'HEV'
    ),
    (
        'Kia',
        'Niro (DE)',
        2017,
        'PHEV'
    ),
    (
        'Kia',
        'Niro (DE)',
        2017,
        'EV'
    ),
    (
        'Kia',
        'Niro (DE)',
        2018,
        'HEV'
    ),
    (
        'Kia',
        'Niro (DE)',
        2018,
        'PHEV'
    ),
    (
        'Kia',
        'Niro (DE)',
        2018,
        'EV'
    ),
    (
        'Kia',
        'Niro (DE)',
        2019,
        'HEV'
    ),
    (
        'Kia',
        'Niro (DE)',
        2019,
        'PHEV'
    ),
    (
        'Kia',
        'Niro (DE)',
        2019,
        'EV'
    ),
    (
        'Kia',
        'Niro (DE)',
        2020,
        'HEV'
    ),
    (
        'Kia',
        'Niro (DE)',
        2020,
        'PHEV'
    ),
    (
        'Kia',
        'Niro (DE)',
        2020,
        'EV'
    ),
    (
        'Kia',
        'Niro (DE)',
        2021,
        'HEV'
    ),
    (
        'Kia',
        'Niro (DE)',
        2021,
        'PHEV'
    ),
    (
        'Kia',
        'Niro (DE)',
        2021,
        'EV'
    ),
    (
        'Kia',
        'Niro (SG2)',
        2022,
        'HEV'
    ),
    (
        'Kia',
        'Niro (SG2)',
        2022,
        'EV'
    ),
    (
        'Kia',
        'Niro (SG2)',
        2023,
        'HEV'
    ),
    (
        'Kia',
        'Niro (SG2)',
        2023,
        'EV'
    ),
    (
        'Kia',
        'Niro (SG2)',
        2024,
        'HEV'
    ),
    (
        'Kia',
        'Niro (SG2)',
        2024,
        'EV'
    ),
    (
        'Kia',
        'Seltos',
        2019,
        'GASOLINE'
    ),
    (
        'Kia',
        'Seltos',
        2019,
        'DIESEL'
    ),
    (
        'Kia',
        'Seltos',
        2020,
        'GASOLINE'
    ),
    (
        'Kia',
        'Seltos',
        2020,
        'DIESEL'
    ),
    (
        'Kia',
        'Seltos',
        2021,
        'GASOLINE'
    ),
    (
        'Kia',
        'Seltos',
        2021,
        'DIESEL'
    ),
    (
        'Kia',
        'Seltos',
        2022,
        'GASOLINE'
    ),
    (
        'Kia',
        'Seltos',
        2022,
        'DIESEL'
    ),
    (
        'Kia',
        'Seltos',
        2023,
        'GASOLINE'
    ),
    (
        'Kia',
        'Seltos',
        2023,
        'DIESEL'
    ),
    (
        'Kia',
        'Seltos',
        2024,
        'GASOLINE'
    ),
    (
        'Kia',
        'Seltos',
        2024,
        'DIESEL'
    ),
    (
        'Kia',
        'Ray',
        2011,
        'GASOLINE'
    ),
    ('Kia', 'Ray', 2011, 'EV'),
    (
        'Kia',
        'Ray',
        2012,
        'GASOLINE'
    ),
    ('Kia', 'Ray', 2012, 'EV'),
    (
        'Kia',
        'Ray',
        2013,
        'GASOLINE'
    ),
    ('Kia', 'Ray', 2013, 'EV'),
    (
        'Kia',
        'Ray',
        2014,
        'GASOLINE'
    ),
    ('Kia', 'Ray', 2014, 'EV'),
    (
        'Kia',
        'Ray',
        2015,
        'GASOLINE'
    ),
    ('Kia', 'Ray', 2015, 'EV'),
    (
        'Kia',
        'Ray',
        2016,
        'GASOLINE'
    ),
    ('Kia', 'Ray', 2016, 'EV'),
    (
        'Kia',
        'Ray',
        2017,
        'GASOLINE'
    ),
    ('Kia', 'Ray', 2017, 'EV'),
    (
        'Kia',
        'Ray',
        2018,
        'GASOLINE'
    ),
    ('Kia', 'Ray', 2018, 'EV'),
    (
        'Kia',
        'Ray',
        2019,
        'GASOLINE'
    ),
    ('Kia', 'Ray', 2019, 'EV'),
    (
        'Kia',
        'Ray',
        2020,
        'GASOLINE'
    ),
    ('Kia', 'Ray', 2020, 'EV'),
    (
        'Kia',
        'Ray',
        2021,
        'GASOLINE'
    ),
    ('Kia', 'Ray', 2021, 'EV'),
    (
        'Kia',
        'Ray',
        2022,
        'GASOLINE'
    ),
    ('Kia', 'Ray', 2022, 'EV'),
    (
        'Kia',
        'Ray',
        2023,
        'GASOLINE'
    ),
    ('Kia', 'Ray', 2023, 'EV'),
    (
        'Kia',
        'Ray',
        2024,
        'GASOLINE'
    ),
    ('Kia', 'Ray', 2024, 'EV'),
    ('Kia', 'EV6', 2021, 'EV'),
    ('Kia', 'EV6', 2022, 'EV'),
    ('Kia', 'EV6', 2023, 'EV'),
    ('Kia', 'EV6', 2024, 'EV'),
    ('Kia', 'EV9', 2023, 'EV'),
    ('Kia', 'EV9', 2024, 'EV'),
    (
        'Genesis',
        'G70',
        2017,
        'GASOLINE'
    ),
    (
        'Genesis',
        'G70',
        2017,
        'DIESEL'
    ),
    (
        'Genesis',
        'G70',
        2018,
        'GASOLINE'
    ),
    (
        'Genesis',
        'G70',
        2018,
        'DIESEL'
    ),
    (
        'Genesis',
        'G70',
        2019,
        'GASOLINE'
    ),
    (
        'Genesis',
        'G70',
        2019,
        'DIESEL'
    ),
    (
        'Genesis',
        'G70',
        2020,
        'GASOLINE'
    ),
    (
        'Genesis',
        'G70',
        2020,
        'DIESEL'
    ),
    (
        'Genesis',
        'G70',
        2021,
        'GASOLINE'
    ),
    (
        'Genesis',
        'G70',
        2021,
        'DIESEL'
    ),
    (
        'Genesis',
        'G70',
        2022,
        'GASOLINE'
    ),
    (
        'Genesis',
        'G70',
        2022,
        'DIESEL'
    ),
    (
        'Genesis',
        'G70',
        2023,
        'GASOLINE'
    ),
    (
        'Genesis',
        'G70',
        2023,
        'DIESEL'
    ),
    (
        'Genesis',
        'G70',
        2024,
        'GASOLINE'
    ),
    (
        'Genesis',
        'G70',
        2024,
        'DIESEL'
    ),
    (
        'Genesis',
        'G80 (DH)',
        2016,
        'GASOLINE'
    ),
    (
        'Genesis',
        'G80 (DH)',
        2016,
        'DIESEL'
    ),
    (
        'Genesis',
        'G80 (DH)',
        2017,
        'GASOLINE'
    ),
    (
        'Genesis',
        'G80 (DH)',
        2017,
        'DIESEL'
    ),
    (
        'Genesis',
        'G80 (DH)',
        2018,
        'GASOLINE'
    ),
    (
        'Genesis',
        'G80 (DH)',
        2018,
        'DIESEL'
    ),
    (
        'Genesis',
        'G80 (DH)',
        2019,
        'GASOLINE'
    ),
    (
        'Genesis',
        'G80 (DH)',
        2019,
        'DIESEL'
    ),
    (
        'Genesis',
        'G80 (RG3)',
        2020,
        'GASOLINE'
    ),
    (
        'Genesis',
        'G80 (RG3)',
        2020,
        'DIESEL'
    ),
    (
        'Genesis',
        'G80 (RG3)',
        2020,
        'EV'
    ),
    (
        'Genesis',
        'G80 (RG3)',
        2021,
        'GASOLINE'
    ),
    (
        'Genesis',
        'G80 (RG3)',
        2021,
        'DIESEL'
    ),
    (
        'Genesis',
        'G80 (RG3)',
        2021,
        'EV'
    ),
    (
        'Genesis',
        'G80 (RG3)',
        2022,
        'GASOLINE'
    ),
    (
        'Genesis',
        'G80 (RG3)',
        2022,
        'DIESEL'
    ),
    (
        'Genesis',
        'G80 (RG3)',
        2022,
        'EV'
    ),
    (
        'Genesis',
        'G80 (RG3)',
        2023,
        'GASOLINE'
    ),
    (
        'Genesis',
        'G80 (RG3)',
        2023,
        'DIESEL'
    ),
    (
        'Genesis',
        'G80 (RG3)',
        2023,
        'EV'
    ),
    (
        'Genesis',
        'G80 (RG3)',
        2024,
        'GASOLINE'
    ),
    (
        'Genesis',
        'G80 (RG3)',
        2024,
        'DIESEL'
    ),
    (
        'Genesis',
        'G80 (RG3)',
        2024,
        'EV'
    ),
    (
        'Genesis',
        'G90',
        2016,
        'GASOLINE'
    ),
    (
        'Genesis',
        'G90',
        2017,
        'GASOLINE'
    ),
    (
        'Genesis',
        'G90',
        2018,
        'GASOLINE'
    ),
    (
        'Genesis',
        'G90',
        2019,
        'GASOLINE'
    ),
    (
        'Genesis',
        'G90',
        2020,
        'GASOLINE'
    ),
    (
        'Genesis',
        'G90',
        2021,
        'GASOLINE'
    ),
    (
        'Genesis',
        'G90',
        2022,
        'GASOLINE'
    ),
    (
        'Genesis',
        'G90',
        2023,
        'GASOLINE'
    ),
    (
        'Genesis',
        'G90',
        2024,
        'GASOLINE'
    ),
    ('Genesis', 'GV60', 2021, 'EV'),
    ('Genesis', 'GV60', 2022, 'EV'),
    ('Genesis', 'GV60', 2023, 'EV'),
    ('Genesis', 'GV60', 2024, 'EV'),
    (
        'Genesis',
        'GV70',
        2020,
        'GASOLINE'
    ),
    (
        'Genesis',
        'GV70',
        2020,
        'DIESEL'
    ),
    ('Genesis', 'GV70', 2020, 'EV'),
    (
        'Genesis',
        'GV70',
        2021,
        'GASOLINE'
    ),
    (
        'Genesis',
        'GV70',
        2021,
        'DIESEL'
    ),
    ('Genesis', 'GV70', 2021, 'EV'),
    (
        'Genesis',
        'GV70',
        2022,
        'GASOLINE'
    ),
    (
        'Genesis',
        'GV70',
        2022,
        'DIESEL'
    ),
    ('Genesis', 'GV70', 2022, 'EV'),
    (
        'Genesis',
        'GV70',
        2023,
        'GASOLINE'
    ),
    (
        'Genesis',
        'GV70',
        2023,
        'DIESEL'
    ),
    ('Genesis', 'GV70', 2023, 'EV'),
    (
        'Genesis',
        'GV70',
        2024,
        'GASOLINE'
    ),
    (
        'Genesis',
        'GV70',
        2024,
        'DIESEL'
    ),
    ('Genesis', 'GV70', 2024, 'EV'),
    (
        'Genesis',
        'GV80',
        2020,
        'GASOLINE'
    ),
    (
        'Genesis',
        'GV80',
        2020,
        'DIESEL'
    ),
    (
        'Genesis',
        'GV80',
        2021,
        'GASOLINE'
    ),
    (
        'Genesis',
        'GV80',
        2021,
        'DIESEL'
    ),
    (
        'Genesis',
        'GV80',
        2022,
        'GASOLINE'
    ),
    (
        'Genesis',
        'GV80',
        2022,
        'DIESEL'
    ),
    (
        'Genesis',
        'GV80',
        2023,
        'GASOLINE'
    ),
    (
        'Genesis',
        'GV80',
        2023,
        'DIESEL'
    ),
    (
        'Genesis',
        'GV80',
        2024,
        'GASOLINE'
    ),
    (
        'Genesis',
        'GV80',
        2024,
        'DIESEL'
    ),
    (
        'KG Mobility',
        'Tivoli',
        2015,
        'GASOLINE'
    ),
    (
        'KG Mobility',
        'Tivoli',
        2015,
        'DIESEL'
    ),
    (
        'KG Mobility',
        'Tivoli',
        2016,
        'GASOLINE'
    ),
    (
        'KG Mobility',
        'Tivoli',
        2016,
        'DIESEL'
    ),
    (
        'KG Mobility',
        'Tivoli',
        2017,
        'GASOLINE'
    ),
    (
        'KG Mobility',
        'Tivoli',
        2017,
        'DIESEL'
    ),
    (
        'KG Mobility',
        'Tivoli',
        2018,
        'GASOLINE'
    ),
    (
        'KG Mobility',
        'Tivoli',
        2018,
        'DIESEL'
    ),
    (
        'KG Mobility',
        'Tivoli',
        2019,
        'GASOLINE'
    ),
    (
        'KG Mobility',
        'Tivoli',
        2019,
        'DIESEL'
    ),
    (
        'KG Mobility',
        'Tivoli',
        2020,
        'GASOLINE'
    ),
    (
        'KG Mobility',
        'Tivoli',
        2020,
        'DIESEL'
    ),
    (
        'KG Mobility',
        'Tivoli',
        2021,
        'GASOLINE'
    ),
    (
        'KG Mobility',
        'Tivoli',
        2021,
        'DIESEL'
    ),
    (
        'KG Mobility',
        'Tivoli',
        2022,
        'GASOLINE'
    ),
    (
        'KG Mobility',
        'Tivoli',
        2022,
        'DIESEL'
    ),
    (
        'KG Mobility',
        'Tivoli',
        2023,
        'GASOLINE'
    ),
    (
        'KG Mobility',
        'Tivoli',
        2023,
        'DIESEL'
    ),
    (
        'KG Mobility',
        'Tivoli',
        2024,
        'GASOLINE'
    ),
    (
        'KG Mobility',
        'Tivoli',
        2024,
        'DIESEL'
    ),
    (
        'KG Mobility',
        'Torres',
        2022,
        'GASOLINE'
    ),
    (
        'KG Mobility',
        'Torres',
        2022,
        'EV'
    ),
    (
        'KG Mobility',
        'Torres',
        2023,
        'GASOLINE'
    ),
    (
        'KG Mobility',
        'Torres',
        2023,
        'EV'
    ),
    (
        'KG Mobility',
        'Torres',
        2024,
        'GASOLINE'
    ),
    (
        'KG Mobility',
        'Torres',
        2024,
        'EV'
    ),
    (
        'KG Mobility',
        'Korando',
        2011,
        'DIESEL'
    ),
    (
        'KG Mobility',
        'Korando',
        2011,
        'GASOLINE'
    ),
    (
        'KG Mobility',
        'Korando',
        2011,
        'EV'
    ),
    (
        'KG Mobility',
        'Korando',
        2012,
        'DIESEL'
    ),
    (
        'KG Mobility',
        'Korando',
        2012,
        'GASOLINE'
    ),
    (
        'KG Mobility',
        'Korando',
        2012,
        'EV'
    ),
    (
        'KG Mobility',
        'Korando',
        2013,
        'DIESEL'
    ),
    (
        'KG Mobility',
        'Korando',
        2013,
        'GASOLINE'
    ),
    (
        'KG Mobility',
        'Korando',
        2013,
        'EV'
    ),
    (
        'KG Mobility',
        'Korando',
        2014,
        'DIESEL'
    ),
    (
        'KG Mobility',
        'Korando',
        2014,
        'GASOLINE'
    ),
    (
        'KG Mobility',
        'Korando',
        2014,
        'EV'
    ),
    (
        'KG Mobility',
        'Korando',
        2015,
        'DIESEL'
    ),
    (
        'KG Mobility',
        'Korando',
        2015,
        'GASOLINE'
    ),
    (
        'KG Mobility',
        'Korando',
        2015,
        'EV'
    ),
    (
        'KG Mobility',
        'Korando',
        2016,
        'DIESEL'
    ),
    (
        'KG Mobility',
        'Korando',
        2016,
        'GASOLINE'
    ),
    (
        'KG Mobility',
        'Korando',
        2016,
        'EV'
    ),
    (
        'KG Mobility',
        'Korando',
        2017,
        'DIESEL'
    ),
    (
        'KG Mobility',
        'Korando',
        2017,
        'GASOLINE'
    ),
    (
        'KG Mobility',
        'Korando',
        2017,
        'EV'
    ),
    (
        'KG Mobility',
        'Korando',
        2018,
        'DIESEL'
    ),
    (
        'KG Mobility',
        'Korando',
        2018,
        'GASOLINE'
    ),
    (
        'KG Mobility',
        'Korando',
        2018,
        'EV'
    ),
    (
        'KG Mobility',
        'Korando',
        2019,
        'DIESEL'
    ),
    (
        'KG Mobility',
        'Korando',
        2019,
        'GASOLINE'
    ),
    (
        'KG Mobility',
        'Korando',
        2019,
        'EV'
    ),
    (
        'KG Mobility',
        'Korando',
        2020,
        'DIESEL'
    ),
    (
        'KG Mobility',
        'Korando',
        2020,
        'GASOLINE'
    ),
    (
        'KG Mobility',
        'Korando',
        2020,
        'EV'
    ),
    (
        'KG Mobility',
        'Korando',
        2021,
        'DIESEL'
    ),
    (
        'KG Mobility',
        'Korando',
        2021,
        'GASOLINE'
    ),
    (
        'KG Mobility',
        'Korando',
        2021,
        'EV'
    ),
    (
        'KG Mobility',
        'Korando',
        2022,
        'DIESEL'
    ),
    (
        'KG Mobility',
        'Korando',
        2022,
        'GASOLINE'
    ),
    (
        'KG Mobility',
        'Korando',
        2022,
        'EV'
    ),
    (
        'KG Mobility',
        'Korando',
        2023,
        'DIESEL'
    ),
    (
        'KG Mobility',
        'Korando',
        2023,
        'GASOLINE'
    ),
    (
        'KG Mobility',
        'Korando',
        2023,
        'EV'
    ),
    (
        'KG Mobility',
        'Korando',
        2024,
        'DIESEL'
    ),
    (
        'KG Mobility',
        'Korando',
        2024,
        'GASOLINE'
    ),
    (
        'KG Mobility',
        'Korando',
        2024,
        'EV'
    ),
    (
        'KG Mobility',
        'Rexton',
        2010,
        'DIESEL'
    ),
    (
        'KG Mobility',
        'Rexton',
        2010,
        'GASOLINE'
    ),
    (
        'KG Mobility',
        'Rexton',
        2011,
        'DIESEL'
    ),
    (
        'KG Mobility',
        'Rexton',
        2011,
        'GASOLINE'
    ),
    (
        'KG Mobility',
        'Rexton',
        2012,
        'DIESEL'
    ),
    (
        'KG Mobility',
        'Rexton',
        2012,
        'GASOLINE'
    ),
    (
        'KG Mobility',
        'Rexton',
        2013,
        'DIESEL'
    ),
    (
        'KG Mobility',
        'Rexton',
        2013,
        'GASOLINE'
    ),
    (
        'KG Mobility',
        'Rexton',
        2014,
        'DIESEL'
    ),
    (
        'KG Mobility',
        'Rexton',
        2014,
        'GASOLINE'
    ),
    (
        'KG Mobility',
        'Rexton',
        2015,
        'DIESEL'
    ),
    (
        'KG Mobility',
        'Rexton',
        2015,
        'GASOLINE'
    ),
    (
        'KG Mobility',
        'Rexton',
        2016,
        'DIESEL'
    ),
    (
        'KG Mobility',
        'Rexton',
        2016,
        'GASOLINE'
    ),
    (
        'KG Mobility',
        'Rexton',
        2017,
        'DIESEL'
    ),
    (
        'KG Mobility',
        'Rexton',
        2017,
        'GASOLINE'
    ),
    (
        'KG Mobility',
        'Rexton',
        2018,
        'DIESEL'
    ),
    (
        'KG Mobility',
        'Rexton',
        2018,
        'GASOLINE'
    ),
    (
        'KG Mobility',
        'Rexton',
        2019,
        'DIESEL'
    ),
    (
        'KG Mobility',
        'Rexton',
        2019,
        'GASOLINE'
    ),
    (
        'KG Mobility',
        'Rexton',
        2020,
        'DIESEL'
    ),
    (
        'KG Mobility',
        'Rexton',
        2020,
        'GASOLINE'
    ),
    (
        'KG Mobility',
        'Rexton',
        2021,
        'DIESEL'
    ),
    (
        'KG Mobility',
        'Rexton',
        2021,
        'GASOLINE'
    ),
    (
        'KG Mobility',
        'Rexton',
        2022,
        'DIESEL'
    ),
    (
        'KG Mobility',
        'Rexton',
        2022,
        'GASOLINE'
    ),
    (
        'KG Mobility',
        'Rexton',
        2023,
        'DIESEL'
    ),
    (
        'KG Mobility',
        'Rexton',
        2023,
        'GASOLINE'
    ),
    (
        'KG Mobility',
        'Rexton',
        2024,
        'DIESEL'
    ),
    (
        'KG Mobility',
        'Rexton',
        2024,
        'GASOLINE'
    ),
    (
        'Renault Korea',
        'SM6',
        2016,
        'GASOLINE'
    ),
    (
        'Renault Korea',
        'SM6',
        2016,
        'DIESEL'
    ),
    (
        'Renault Korea',
        'SM6',
        2016,
        'LPG'
    ),
    (
        'Renault Korea',
        'SM6',
        2017,
        'GASOLINE'
    ),
    (
        'Renault Korea',
        'SM6',
        2017,
        'DIESEL'
    ),
    (
        'Renault Korea',
        'SM6',
        2017,
        'LPG'
    ),
    (
        'Renault Korea',
        'SM6',
        2018,
        'GASOLINE'
    ),
    (
        'Renault Korea',
        'SM6',
        2018,
        'DIESEL'
    ),
    (
        'Renault Korea',
        'SM6',
        2018,
        'LPG'
    ),
    (
        'Renault Korea',
        'SM6',
        2019,
        'GASOLINE'
    ),
    (
        'Renault Korea',
        'SM6',
        2019,
        'DIESEL'
    ),
    (
        'Renault Korea',
        'SM6',
        2019,
        'LPG'
    ),
    (
        'Renault Korea',
        'SM6',
        2020,
        'GASOLINE'
    ),
    (
        'Renault Korea',
        'SM6',
        2020,
        'DIESEL'
    ),
    (
        'Renault Korea',
        'SM6',
        2020,
        'LPG'
    ),
    (
        'Renault Korea',
        'SM6',
        2021,
        'GASOLINE'
    ),
    (
        'Renault Korea',
        'SM6',
        2021,
        'DIESEL'
    ),
    (
        'Renault Korea',
        'SM6',
        2021,
        'LPG'
    ),
    (
        'Renault Korea',
        'SM6',
        2022,
        'GASOLINE'
    ),
    (
        'Renault Korea',
        'SM6',
        2022,
        'DIESEL'
    ),
    (
        'Renault Korea',
        'SM6',
        2022,
        'LPG'
    ),
    (
        'Renault Korea',
        'SM6',
        2023,
        'GASOLINE'
    ),
    (
        'Renault Korea',
        'SM6',
        2023,
        'DIESEL'
    ),
    (
        'Renault Korea',
        'SM6',
        2023,
        'LPG'
    ),
    (
        'Renault Korea',
        'SM6',
        2024,
        'GASOLINE'
    ),
    (
        'Renault Korea',
        'SM6',
        2024,
        'DIESEL'
    ),
    (
        'Renault Korea',
        'SM6',
        2024,
        'LPG'
    ),
    (
        'Renault Korea',
        'QM6',
        2016,
        'GASOLINE'
    ),
    (
        'Renault Korea',
        'QM6',
        2016,
        'DIESEL'
    ),
    (
        'Renault Korea',
        'QM6',
        2016,
        'LPG'
    ),
    (
        'Renault Korea',
        'QM6',
        2017,
        'GASOLINE'
    ),
    (
        'Renault Korea',
        'QM6',
        2017,
        'DIESEL'
    ),
    (
        'Renault Korea',
        'QM6',
        2017,
        'LPG'
    ),
    (
        'Renault Korea',
        'QM6',
        2018,
        'GASOLINE'
    ),
    (
        'Renault Korea',
        'QM6',
        2018,
        'DIESEL'
    ),
    (
        'Renault Korea',
        'QM6',
        2018,
        'LPG'
    ),
    (
        'Renault Korea',
        'QM6',
        2019,
        'GASOLINE'
    ),
    (
        'Renault Korea',
        'QM6',
        2019,
        'DIESEL'
    ),
    (
        'Renault Korea',
        'QM6',
        2019,
        'LPG'
    ),
    (
        'Renault Korea',
        'QM6',
        2020,
        'GASOLINE'
    ),
    (
        'Renault Korea',
        'QM6',
        2020,
        'DIESEL'
    ),
    (
        'Renault Korea',
        'QM6',
        2020,
        'LPG'
    ),
    (
        'Renault Korea',
        'QM6',
        2021,
        'GASOLINE'
    ),
    (
        'Renault Korea',
        'QM6',
        2021,
        'DIESEL'
    ),
    (
        'Renault Korea',
        'QM6',
        2021,
        'LPG'
    ),
    (
        'Renault Korea',
        'QM6',
        2022,
        'GASOLINE'
    ),
    (
        'Renault Korea',
        'QM6',
        2022,
        'DIESEL'
    ),
    (
        'Renault Korea',
        'QM6',
        2022,
        'LPG'
    ),
    (
        'Renault Korea',
        'QM6',
        2023,
        'GASOLINE'
    ),
    (
        'Renault Korea',
        'QM6',
        2023,
        'DIESEL'
    ),
    (
        'Renault Korea',
        'QM6',
        2023,
        'LPG'
    ),
    (
        'Renault Korea',
        'QM6',
        2024,
        'GASOLINE'
    ),
    (
        'Renault Korea',
        'QM6',
        2024,
        'DIESEL'
    ),
    (
        'Renault Korea',
        'QM6',
        2024,
        'LPG'
    ),
    (
        'Renault Korea',
        'XM3',
        2020,
        'GASOLINE'
    ),
    (
        'Renault Korea',
        'XM3',
        2020,
        'HEV'
    ),
    (
        'Renault Korea',
        'XM3',
        2021,
        'GASOLINE'
    ),
    (
        'Renault Korea',
        'XM3',
        2021,
        'HEV'
    ),
    (
        'Renault Korea',
        'XM3',
        2022,
        'GASOLINE'
    ),
    (
        'Renault Korea',
        'XM3',
        2022,
        'HEV'
    ),
    (
        'Renault Korea',
        'XM3',
        2023,
        'GASOLINE'
    ),
    (
        'Renault Korea',
        'XM3',
        2023,
        'HEV'
    ),
    (
        'Renault Korea',
        'XM3',
        2024,
        'GASOLINE'
    ),
    (
        'Renault Korea',
        'XM3',
        2024,
        'HEV'
    ),
    (
        'Renault Korea',
        'SM5 (Nova)',
        2010,
        'GASOLINE'
    ),
    (
        'Renault Korea',
        'SM5 (Nova)',
        2010,
        'DIESEL'
    ),
    (
        'Renault Korea',
        'SM5 (Nova)',
        2010,
        'LPG'
    ),
    (
        'Renault Korea',
        'SM5 (Nova)',
        2011,
        'GASOLINE'
    ),
    (
        'Renault Korea',
        'SM5 (Nova)',
        2011,
        'DIESEL'
    ),
    (
        'Renault Korea',
        'SM5 (Nova)',
        2011,
        'LPG'
    ),
    (
        'Renault Korea',
        'SM5 (Nova)',
        2012,
        'GASOLINE'
    ),
    (
        'Renault Korea',
        'SM5 (Nova)',
        2012,
        'DIESEL'
    ),
    (
        'Renault Korea',
        'SM5 (Nova)',
        2012,
        'LPG'
    ),
    (
        'Renault Korea',
        'SM5 (Nova)',
        2013,
        'GASOLINE'
    ),
    (
        'Renault Korea',
        'SM5 (Nova)',
        2013,
        'DIESEL'
    ),
    (
        'Renault Korea',
        'SM5 (Nova)',
        2013,
        'LPG'
    ),
    (
        'Renault Korea',
        'SM5 (Nova)',
        2014,
        'GASOLINE'
    ),
    (
        'Renault Korea',
        'SM5 (Nova)',
        2014,
        'DIESEL'
    ),
    (
        'Renault Korea',
        'SM5 (Nova)',
        2014,
        'LPG'
    ),
    (
        'Renault Korea',
        'SM5 (Nova)',
        2015,
        'GASOLINE'
    ),
    (
        'Renault Korea',
        'SM5 (Nova)',
        2015,
        'DIESEL'
    ),
    (
        'Renault Korea',
        'SM5 (Nova)',
        2015,
        'LPG'
    ),
    (
        'Renault Korea',
        'SM5 (Nova)',
        2016,
        'GASOLINE'
    ),
    (
        'Renault Korea',
        'SM5 (Nova)',
        2016,
        'DIESEL'
    ),
    (
        'Renault Korea',
        'SM5 (Nova)',
        2016,
        'LPG'
    ),
    (
        'Renault Korea',
        'SM5 (Nova)',
        2017,
        'GASOLINE'
    ),
    (
        'Renault Korea',
        'SM5 (Nova)',
        2017,
        'DIESEL'
    ),
    (
        'Renault Korea',
        'SM5 (Nova)',
        2017,
        'LPG'
    ),
    (
        'Renault Korea',
        'SM5 (Nova)',
        2018,
        'GASOLINE'
    ),
    (
        'Renault Korea',
        'SM5 (Nova)',
        2018,
        'DIESEL'
    ),
    (
        'Renault Korea',
        'SM5 (Nova)',
        2018,
        'LPG'
    ),
    (
        'Chevrolet',
        'Spark',
        2011,
        'GASOLINE'
    ),
    (
        'Chevrolet',
        'Spark',
        2012,
        'GASOLINE'
    ),
    (
        'Chevrolet',
        'Spark',
        2013,
        'GASOLINE'
    ),
    (
        'Chevrolet',
        'Spark',
        2014,
        'GASOLINE'
    ),
    (
        'Chevrolet',
        'Spark',
        2015,
        'GASOLINE'
    ),
    (
        'Chevrolet',
        'Spark',
        2016,
        'GASOLINE'
    ),
    (
        'Chevrolet',
        'Spark',
        2017,
        'GASOLINE'
    ),
    (
        'Chevrolet',
        'Spark',
        2018,
        'GASOLINE'
    ),
    (
        'Chevrolet',
        'Spark',
        2019,
        'GASOLINE'
    ),
    (
        'Chevrolet',
        'Spark',
        2020,
        'GASOLINE'
    ),
    (
        'Chevrolet',
        'Spark',
        2021,
        'GASOLINE'
    ),
    (
        'Chevrolet',
        'Spark',
        2022,
        'GASOLINE'
    ),
    (
        'Chevrolet',
        'Trax',
        2013,
        'GASOLINE'
    ),
    (
        'Chevrolet',
        'Trax',
        2013,
        'DIESEL'
    ),
    (
        'Chevrolet',
        'Trax',
        2014,
        'GASOLINE'
    ),
    (
        'Chevrolet',
        'Trax',
        2014,
        'DIESEL'
    ),
    (
        'Chevrolet',
        'Trax',
        2015,
        'GASOLINE'
    ),
    (
        'Chevrolet',
        'Trax',
        2015,
        'DIESEL'
    ),
    (
        'Chevrolet',
        'Trax',
        2016,
        'GASOLINE'
    ),
    (
        'Chevrolet',
        'Trax',
        2016,
        'DIESEL'
    ),
    (
        'Chevrolet',
        'Trax',
        2017,
        'GASOLINE'
    ),
    (
        'Chevrolet',
        'Trax',
        2017,
        'DIESEL'
    ),
    (
        'Chevrolet',
        'Trax',
        2018,
        'GASOLINE'
    ),
    (
        'Chevrolet',
        'Trax',
        2018,
        'DIESEL'
    ),
    (
        'Chevrolet',
        'Trax',
        2019,
        'GASOLINE'
    ),
    (
        'Chevrolet',
        'Trax',
        2019,
        'DIESEL'
    ),
    (
        'Chevrolet',
        'Trax',
        2020,
        'GASOLINE'
    ),
    (
        'Chevrolet',
        'Trax',
        2020,
        'DIESEL'
    ),
    (
        'Chevrolet',
        'Trax',
        2021,
        'GASOLINE'
    ),
    (
        'Chevrolet',
        'Trax',
        2021,
        'DIESEL'
    ),
    (
        'Chevrolet',
        'Trax',
        2022,
        'GASOLINE'
    ),
    (
        'Chevrolet',
        'Trax',
        2022,
        'DIESEL'
    ),
    (
        'Chevrolet',
        'Trax',
        2023,
        'GASOLINE'
    ),
    (
        'Chevrolet',
        'Trax',
        2023,
        'DIESEL'
    ),
    (
        'Chevrolet',
        'Trax',
        2024,
        'GASOLINE'
    ),
    (
        'Chevrolet',
        'Trax',
        2024,
        'DIESEL'
    ),
    (
        'Chevrolet',
        'Trailblazer',
        2020,
        'GASOLINE'
    ),
    (
        'Chevrolet',
        'Trailblazer',
        2021,
        'GASOLINE'
    ),
    (
        'Chevrolet',
        'Trailblazer',
        2022,
        'GASOLINE'
    ),
    (
        'Chevrolet',
        'Trailblazer',
        2023,
        'GASOLINE'
    ),
    (
        'Chevrolet',
        'Trailblazer',
        2024,
        'GASOLINE'
    );