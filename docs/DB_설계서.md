# 데이터베이스 상세 설계서 (v1.5)

> **기반 기술**: PostgreSQL 15+, TimescaleDB (시계열 확장), pgvector (벡터 검색 확장)
> **식별자 정책**: 모든 주요 테이블은 분산 환경 정합성과 보안을 위해 `UUID`를 기본 PK로 사용함.
> **보안 정책**: 개인정보 및 차대번호(VIN), **클라우드 액세스 토큰**은 `AES-256` 암호화 및 `Soft Delete` 정책을 적용하며, 탈퇴/삭제된 데이터는 AI 학습을 위해 **개인식별정보 제거(익명화) 후 보존**함.

---

## 1. 개요
본 시스템은 차량의 고주파 시계열 데이터, 비즈니스 메타데이터, 그리고 AI 진단을 위한 증거 및 벡터 데이터를 통합 관리합니다. v1.5에서는 백엔드 코드 연동 과정에서 추가된 사용자 프로필 및 차량 세부 정보(별칭, 메모, OBD 기기 식별자)를 문서에 동기화하였습니다.

---

## 2. 상세 테이블 명세

### 2.1 사용자 및 차량 (Core)
차량 소유 관계와 기본적인 차량 정보를 관리합니다.

| 테이블명 | 컬럼명 | 타입 | 제약조건 | 설명 |
|:---|:---|:---|:---|:---|
| **users** | user_id | UUID | PK | 사용자 고유 식별자 |
| | email | VARCHAR(255) | UK, NOT NULL | 로그인 계정 (직접/소셜) |
| | password_hash | VARCHAR(255) | | 암호화된 비밀번호 (bcrypt) |
| | nickname | VARCHAR(50) | | 서비스 내 활동 닉네임 |
| | fcm_token | VARCHAR(255) | | 푸시 알림 발송용 토큰 |
| | user_level | ENUM | DEFAULT 'FREE' | FREE / PREMIUM / ADMIN |
| | membership_expiry | TIMESTAMP | | 멤버십 만료 일시 |
| | last_login_at | TIMESTAMP | | 최종 로그인 일시 |
| | created_at | TIMESTAMP | DEFAULT NOW(), NOT NULL | 가입 일시 (BaseEntity) |
| | updated_at | TIMESTAMP | NOT NULL | 수정 일시 (BaseEntity) |
| | profile_image | OID | | 프로필 이미지 바이너리 |
| | deleted_at | TIMESTAMP | | 탈퇴 일시 (Soft Delete) |

#### 2.1.2 사용자 알림 및 서비스 설정 (user_settings - FR-NOTI-001)
| 테이블명 | 컬럼명 | 타입 | 제약조건 | 설명 |
|:---|:---|:---|:---|:---|
| **user_settings** | user_id | UUID | PK, FK | 사용자 식별자 (users.user_id) |
| | noti_maintenance | BOOLEAN | DEFAULT TRUE | 정비/소모품 알림 수신 여부 |
| | noti_anomaly | BOOLEAN | DEFAULT TRUE | 실시간 이상감지 알림 수신 여부 |
| | noti_marketing | BOOLEAN | DEFAULT FALSE | 마케팅 알림 수신 여부 |
| | night_push_allowed| BOOLEAN | DEFAULT FALSE | 야간 푸시 제한 여부 |

#### 2.1.3 제조사 클라우드 연동 계정 (cloud_accounts - FR-CLOUD-001)
*OAuth 연동 정보를 보관하며, 토큰은 반드시 AES-256으로 암호화하여 저장합니다.*

| 테이블명 | 컬럼명 | 타입 | 제약조건 | 설명 |
|:---|:---|:---|:---|:---|
| **cloud_accounts** | account_id | UUID | PK | 식별자 |
| | user_id | UUID | FK | 사용자 식별자 |
| | provider | VARCHAR(50) | | 제조사 (HYUNDAI, KIA, TESLA 등) - Via High Mobility |
| | provider_user_id | VARCHAR(255) | | High Mobility 사용자 식별 ID |
| | access_token | TEXT | | 암호화된 Access Token |
| | refresh_token | TEXT | | 암호화된 Refresh Token |
| | expires_at | TIMESTAMP | | 토큰 만료 일시 |
| | last_synced_at | TIMESTAMP | | 최종 데이터 동기화 성공 시각 |

#### 2.1.4 리프레시 토큰 (refresh_tokens - BE-AU-006)
*사용자의 로그인 유지를 위한 JWT Refresh Token을 관리합니다.*

| 테이블명 | 컬럼명 | 타입 | 제약조건 | 설명 |
|:---|:---|:---|:---|:---|
| **refresh_tokens** | id | BIGINT | PK, AUTO_INC | 식별자 |
| | user_id | UUID | FK, UK, NOT NULL | 사용자 식별자 (users.user_id) |
| | token | VARCHAR(255) | UK, NOT NULL | Refresh Token 문자열 |
| | expiry_date | TIMESTAMP | NOT NULL | 토큰 만료 일시 |

| 테이블명 | 컬럼명 | 타입 | 제약조건 | 설명 |
|:---|:---|:---|:---|:---|
| **vehicles** | vehicles_id | UUID | PK | 차량 고유 식별자 |
| | user_id | UUID | FK | 소유주 (users.user_id) |
| | vin | VARCHAR(255) | UK | 차대번호 (암호화, 어댑터 미연동 시 NULL 가능) |
| | car_number | VARCHAR(20) | | 차량 번호 (예: 123가 4567) |
| | manufacturer | VARCHAR(50) | | 제조사 (예: Hyundai) |
| | model_name | VARCHAR(100) | | 모델명 (예: Sonata) |
| | model_year | INT | | 차량 연식 (예: 2023) |
| | fuel_type | ENUM | | GASOLINE / DIESEL / EV / HEV / LPG |
| | total_mileage | FLOAT | DEFAULT 0 | 누적 주행거리 (km) |
| | is_primary | BOOLEAN | DEFAULT FALSE | 대표 차량 여부 |
| | registration_source | ENUM | | MANUAL / OBD / CLOUD |
| | cloud_linked | BOOLEAN | DEFAULT FALSE | 클라우드 계정 연동 여부 |
| | nickname | VARCHAR(50) | | 차량 별칭 (사용자 설정) |
| | memo | TEXT | | 차량 관련 메모 |
| | obd_device_id | VARCHAR(100) | | OBD 어댑터 하드웨어 식별자 |
| | created_at | TIMESTAMP | DEFAULT NOW() | 등록 일시 |
| | deleted_at | TIMESTAMP | | 삭제 일시 (Soft Delete) |



### 2.2 텔레메트리 (Telemetry)
차량 주행 중 발생하는 데이터와 제조사 클라우드 동기화 데이터를 관리합니다.

#### 2.2.1 OBD 실시간 로그 (obd_logs - TimescaleDB)
*하이퍼테이블(Hypertable)로 설정하며, 3일 보관 후 자동 삭제(Drop Chunk) 정책을 적용함.*

| 테이블명 | 컬럼명 | 타입 | 제약조건 | 설명 |
|:---|:---|:---|:---|:---|
| **obd_logs** | time | TIMESTAMPTZ | PK | 수집 시각 |
| | vehicles_id | UUID | PK, FK | 차량 식별자 |
| | rpm | FLOAT | | 엔진 회전수 |
| | speed | FLOAT | | 차량 속도 |
| | voltage | FLOAT | | 배터리 전압 |
| | coolant_temp | FLOAT | | 냉각수 온도 |
| | engine_load | FLOAT | | 엔진 부하 |
| | fuel_trim_short | FLOAT | | 단기 연료 보정값 |
| | fuel_trim_long | FLOAT | | 장기 연료 보정값 |
| | json_extra | JSONB | | 연료량/제조사별 특화 데이터 (EV SoC 등) |

#### 2.2.2 클라우드 동기화 데이터 (cloud_telemetry)
*제조사 API(High Mobility)를 통해 정기적으로 가져오는 공식 상태 정보.*

| 테이블명 | 컬럼명 | 타입 | 제약조건 | 설명 |
|:---|:---|:---|:---|:---|
| **cloud_telemetry** | last_synced_at | TIMESTAMPTZ | PK | 동기화 시각 |
| | vehicles_id | UUID | PK, FK | 차량 식별자 |
| | odometer | FLOAT | | 공식 누적 주행거리 |
| | fuel_level | FLOAT | | 잔여 연료량 (%) |
| | battery_soc | FLOAT | | EV 배터리 잔량 (%) |
| | charging_status | ENUM | | EV 충전 상태 (DISCONNECTED/CHARGING/FULL/ERROR) |

#### 2.2.3 주행 요약 (trip_summaries)
*주행 종료 시 OBD 데이터를 가공하여 생성하는 통계 리포트.*

| 테이블명 | 컬럼명 | 타입 | 제약조건 | 설명 |
|:---|:---|:---|:---|:---|
| **trip_summaries** | start_time | TIMESTAMP | PK | 주행 시작 시각 |
| | vehicles_id | UUID | PK, FK | 차량 식별자 |
| | trip_id | UUID | UK, NOT NULL | 주행 세션 식별자 (로직용) |
| | end_time | TIMESTAMP | | 주행 종료 시각 |
| | distance | FLOAT | | 해당 주행 거리 (km) |
| | drive_score | INT | | 해당 주행 운전 점수 (0~100) |
| | average_speed | FLOAT | | 평균 속도 |
| | top_speed | FLOAT | | 최고 속도 |
| | fuel_consumed | FLOAT | | 소모 연료량 추정치 |
| | min_battery_voltage | FLOAT | | 시동 시 최저 전압 (배터리 수명 예측용) |
| | max_coolant_temp | FLOAT | | 주행 중 최고 냉각수 온도 (과열 이력) |
| | avg_fuel_trim | FLOAT | | 평균 연료 보정값 (흡기/누유 추적) |
| | max_engine_load | FLOAT | | 최대 엔진 부하 (엔진 피로도 관리) |
| | idle_time | INT | | 공회전 시간 (초) - 정차 비율 계산용 |
| | hard_accel_count | INT | | 급가속 횟수 (운전 습관) |
| | hard_brake_count | INT | | 급감속 횟수 (브레이크 수명 예측) |

### 2.3 AI 진단 및 증거 (Diagnosis & AI)
AI 모델의 분석 과정과 최종 리포트를 관리합니다.

| 테이블명 | 컬럼명 | 타입 | 제약조건 | 설명 |
|:---|:---|:---|:---|:---|
| **diag_sessions** | diag_session_id | UUID | PK | 진단 세션 식별자 |
| | vehicles_id | UUID | FK | 차량 식별자 |
| | trip_id | UUID | FK | 주행 세션 ID (nullable, trip_summaries.trip_id) |
| | trigger_type | ENUM | | MANUAL/DTC/ANOMALY/ROUTINE |
| | status | ENUM | | PENDING/PROCESSING/DONE/FAILED |
| | created_at | TIMESTAMP | | 요청 시각 |

> [!TIP]
> **소모품 리셋 연동**: 정비 이력이 등록되면 해당 부품의 `consumables_state` 레코드가 자동으로 갱신(수명 100% 리셋)됩니다.

#### 2.3.2 AI 진단 결과 (diag_results)
| 테이블명 | 컬럼명 | 타입 | 제약조건 | 설명 |
|:---|:---|:---|:---|:---|
| **diag_results** | diag_result_id | UUID | PK | 결과 식별자 |
| | diag_session_id | UUID | FK | 진단 세션 ID (diag_sessions.diag_session_id) |
| | final_report | TEXT | | LLM 생성 최종 분석 리포트 |
| | confidence | FLOAT | | 진단 결과에 대한 신뢰도 점수 |
| | detected_issues | JSONB | | 감지된 고장/이상 항목 리스트 |
| | actions_json | JSONB | | 추천 정비 또는 자가 조치 액션 |
| | risk_level | ENUM | | LOW/MID/HIGH/CRITICAL (판정 기준은 기술가이드라인 11.6 참조) |

#### 2.3.3 AI 진단 증거 및 미션 (ai_evidences - FR-DIAG-004)
*AI가 직접 수집하거나 사용자에게 요청한 사진/녹음 등의 멀티모달 증거를 관리합니다.*

| 테이블명 | 컬럼명 | 타입 | 제약조건 | 설명 |
|:---|:---|:---|:---|:---|
| **ai_evidences** | evidence_id | UUID | PK | 분석 증거 식별자 |
| | diag_session_id | UUID | FK | 진단 세션 ID (diag_sessions.diag_session_id) |
| | media_type | ENUM | | AUDIO/IMAGE/SNAPSHOT |
| | s3_key | TEXT | | AWS S3 저장 경로 (UPLOADED 상태에서 필수) |
| | ai_analysis | JSONB | | AI 분석 결과(YOLO/AST 결과 등) |
| | status | ENUM | DEFAULT 'UPLOADED' | REQUESTED / UPLOADED / FAILED |
| | request_text | TEXT | | AI가 사용자에게 사진/녹음 등을 요청한 안내 문구 |

### 2.4 상태 관리 및 히스토리 (Status & History)
차량의 건강 상태와 정비 이력을 관리합니다.

#### 2.4.1 DTC 고장 코드 이력 (dtc_history)
| 테이블명 | 컬럼명 | 타입 | 제약조건 | 설명 |
|:---|:---|:---|:---|:---|
| **dtc_history** | dtc_id | UUID | PK | 이력 식별자 |
| | vehicles_id | UUID | FK | 차량 식별자 |
| | dtc_code | VARCHAR(10) | | 고장 코드 (예: P0301) |
| | description | TEXT | | 코드 설명 (기본) |
| | dtc_type | ENUM | | STORED(03) / PENDING(07) / PERMANENT(0A) |
| | status | ENUM | | ACTIVE/RESOLVED/CLEARED |
| | resolution_type| ENUM | | AUTO / MANUAL / OBD_CLEAR |
| | discovered_at | TIMESTAMP | | 최초 감지 시각 |
| | resolved_at | TIMESTAMP | | 해결/삭제 시각 |

#### 2.4.2 DTC 고장 시점 스냅샷 (dtc_freeze_frames - 정규화)
*Mode 02 데이터를 JSONB 대신 컬럼 기반으로 저장하여 분석 및 통계 속도를 최적화합니다.*

| 테이블명 | 컬럼명 | 타입 | 제약조건 | 설명 |
|:---|:---|:---|:---|:---|
| **dtc_freeze_frames** | frame_id | UUID | PK | 식별자 |
| | dtc_id | UUID | FK, UK | 관련 고장 이력 식별자 |
| | rpm | FLOAT | | 엔진 회전수 |
| | speed | FLOAT | | 차량 속도 |
| | coolant_temp | FLOAT | | 냉각수 온도 |
| | engine_load | FLOAT | | 엔진 부하 |
| | ambient_temp | FLOAT | | 외기 온도 |
| | fuel_pressure | FLOAT | | 연료 압력 |
| | pids_snapshot | JSONB | | 기타 비표준/특이 PID 데이터 |

#### 2.4.3 소모품 잔여 수명 (consumables_state)
| 테이블명 | 컬럼명 | 타입 | 제약조건 | 설명 |
|:---|:---|:---|:---|:---|
| **consumables_state** | consumable_id | UUID | PK | 레코드 식별자 |
| | vehicles_id | UUID | FK | 차량 식별자 |
| | part_name | VARCHAR(50) | | 부품명 (EngineOil, Tires 등) |
| | current_life | FLOAT | | 현재 예상 잔여 수명 (%) |
| | predicted_date | DATE | | 예상 교체 필요 날짜 |
| | last_updated | TIMESTAMP | | AI 모델 최종 예측 시점 |

#### 2.4.4 정비 차계부 (maintenance_logs)
| 테이블명 | 컬럼명 | 타입 | 제약조건 | 설명 |
|:---|:---|:---|:---|:---|
| **maintenance_logs** | maintenance_id | UUID | PK | 기록 식별자 |
| | vehicles_id | UUID | FK | 차량 식별자 |
| | maintenance_date | DATE | | 정비 수행 날짜 |
| | part_name | VARCHAR(50) | | 정비/교체 항목 (표준 Key 또는 사용자 입력) |
| | is_standardized | BOOLEAN | | 표준 항목 여부 (True: 리스트 선택, False: 직접 입력) |
| | cost | INT | | 정비 비용 |
| | shop_name | VARCHAR(100) | | 정비소 이름 |
| | mileage_at_work | FLOAT | | 정비 시점 주행거리 |
| | receipts_s3_key | TEXT | | 영수증 사진 S3 경로 (OCR용) |
| | memo | TEXT | | 추가 특이사항 |

#### 2.4.4 소모품 및 정비 항목 표준 명칭 (Standard Naming)
AI 예측 데이터(`consumables_state`)와 연동되는 핵심 항목들은 드롭다운 선택 형식을 제공하며, 그 외 항목은 '기타'를 통해 자유 입력이 가능합니다.

| 표준 명칭 (Key) | 한글 표시명 | 분류 | AI 수명 연동 여부 |
|:---|:---|:---|:---|
| `ENGINE_OIL` | 엔진 오일 | 필터/윤활유 | Yes |
| `TIRE_FRONT` | 앞 타이어 | 구동/제동 | Yes |
| `TIRE_REAR` | 뒤 타이어 | 구동/제동 | Yes |
| `BRAKE_PAD_FRONT`| 앞 브레이크 패드 | 구동/제동 | Yes |
| `BRAKE_PAD_REAR` | 뒤 브레이크 패드 | 구동/제동 | Yes |
| `BATTERY_12V` | 12V 배터리 | 전기 장치 | Yes |
| `CABIN_FILTER` | 에어컨 필터 | 필터/윤활유 | Yes |
| `COOLANT` | 냉각수 | 필터/윤활유 | Yes |
| `OTHER` | 기타 (직접 입력) | - | No (이력만 보존) |

### 2.5 알림 및 기타 (Notification & Extra)
| 테이블명 | 컬럼명 | 타입 | 제약조건 | 설명 |
|:---|:---|:---|:---|:---|
| **user_notifications** | notification_id | UUID | PK | 알림 식별자 |
| | user_id | UUID | FK | 수신 대상 사용자 |
| | type | ENUM | | ALARM/RECALL/INFO/REPORT |
| | title | VARCHAR(255) | | 알림 제목 |
| | message | TEXT | | 알림 본문 |
| | is_read | BOOLEAN | DEFAULT FALSE | 읽음 여부 |
| | created_at | TIMESTAMP | | 발송 시각 |
| **knowledge_vectors** | knowledge_id | UUID | PK | 식별자 |
| | category | VARCHAR(20) | | MANUAL / DTC_GUIDE / CASE_STUDY / PART_INFO |
| | content | TEXT | | 원문 텍스트 |
| | metadata | JSONB | | { manufacturer, model, year, source, page, dtc_code } |
| | embedding | VECTOR(1024) | | 로컬 AI (mxbai-embed-large) 임베딩 벡터 |

### 2.6 외부 API 연동 및 상세 정보 (External & Detailed)
국토부, 교통안전공단 및 중고차 성능점검 API 등을 통해 수집되는 차량의 객관적 상태 정보를 관리합니다.

#### 2.6.1 차량 상세 제원 (vehicle_specs - FR-CAR-003)
| 테이블명 | 컬럼명 | 타입 | 제약조건 | 설명 |
|:---|:---|:---|:---|:---|
| **vehicle_specs** | spec_id | UUID | PK | 식별자 |
| | vehicles_id | UUID | FK | 차량 식별자 |
| | length | FLOAT | | 전장 (mm) |
| | width | FLOAT | | 전폭 (mm) |
| | height | FLOAT | | 전고 (mm) |
| | displacement | INT | | 배기량 (cc) |
| | engine_type | VARCHAR(50) | | 엔진 형식 |
| | max_power | FLOAT | | 최대 출력 (hp) |
| | max_torque | FLOAT | | 최대 토크 (kg.m) |
| | tire_size_front | VARCHAR(50) | | 앞 타이어 규격 |
| | tire_size_rear | VARCHAR(50) | | 뒤 타이어 규격 |
| | official_fuel_economy| FLOAT | | 공인 연비 (km/L) |
| | last_updated | TIMESTAMP | | 동기화 시각 |





---

### 2.7 차량 마스터 데이터 (Reference Data)
사용자에게 수동 등록(Track B) 시 제공할 제조사 및 차량 모델 표준 정보입니다. 프론트엔드 캐싱을 위해 단순한 구조로 설계합니다.

| 테이블명 | 컬럼명 | 타입 | 제약조건 | 설명 |
|:---|:---|:---|:---|:---|
| **car_model_master** | model_id | BIGINT | PK | 식별자 (Auto Increment) |
| | manufacturer | VARCHAR(50) | | 제조사 (예: Hyundai, Kia) |
| | model_name | VARCHAR(100) | | 모델명 (예: Grandeur IG) |
| | model_year | INT | | 연식 (예: 2020) |
| | fuel_type | VARCHAR(20) | | 유종 (Gasoline/Diesel/LPG/HEV/EV) |
| | displacement | INT | | 배기량 (cc) - 자동차세/연비 기준 |
| | spec_json | JSONB | | 기타 제원 (탱크용량, 타이어규격 등) |

---

### 2.8 실시간 이상 감지 이력 (anomaly_records - FR-ANOMALY)
OBD 표준 DTC 외에 AI가 실시간으로 감지한 핵심 이상 징후를 기록합니다. 시계열 데이터 삭제(3일) 대비 영구 보존용 '사건 하이라이트' 역할을 합니다.

| 테이블명 | 컬럼명 | 타입 | 제약조건 | 설명 |
|:---|:---|:---|:---|:---|
| **anomaly_records** | anomaly_id | UUID | PK | 이상 징후 식별자 |
| | vehicles_id | UUID | FK | 차량 식별자 |
| | recorded_at | TIMESTAMP | | 감지 시각 |
| | anomaly_type | VARCHAR(50) | | 전압 급락 / RPM 이상 / 냉각수 과열 등 |
| | severity | ENUM | | LOW / MID / HIGH / CRITICAL |
| | snapshot_data | JSONB | | 감지 당시의 주요 센서값 요약 |

### 2.8 개인화 인사이트 및 리포트 (user_insights - FR-PERS-001)
AI가 분석한 주행/정비 리포트(미니 보고서) 전문을 관리합니다. 사용자 맞춤형 조언을 보관합니다.

| 테이블명 | 컬럼명 | 타입 | 제약조건 | 설명 |
|:---|:---|:---|:---|:---|
| **user_insights** | insight_id | UUID | PK | 리포트 식별자 |
| | user_id | UUID | FK | 수신 대상 사용자 |
| | trip_id | UUID | FK, NULLABLE| 관련 주행 세션 (주행별 피드백인 경우 필수) |
| | category | ENUM | | ECO_DRIVING / SAFETY / MAINTENANCE |
| | title | VARCHAR(255) | | 리포트 제목 (예: 오늘 출근길 분석) |
| | content_markdown| TEXT | | 상세 분석 내용 (LLM 생성 Markdown) |
| | created_at | TIMESTAMP | | 생성 일시 |
| | is_read | BOOLEAN | DEFAULT FALSE | 사용자 확인 여부 |

---

## 3. 데이터 운영 및 저장 전략

### 3.1 Tiered Storage Strategy
데이터의 중요도와 사용 빈도에 따라 저장소를 계층화합니다.

| 티어 (Tier) | 저장소 | 대상 데이터 | 보관 정책 | 사유 |
|:---|:---|:---|:---|:---|
| **Hot** | TimescaleDB | `obd_logs` | 3일 | 고해상도 초단위 데이터. 분석 후 삭제 |
| **Warm** | PostgreSQL | 메타데이터, 결과, 요약 | 영구 (Soft Delete) | 비즈니스 로직 및 관리용 필수 데이터 |
| **Cold** | AWS S3 | 이미지, 음성, 원본로그 | 영구 | 대용량 바이너리 및 AI 재학습용 자산 |

### 3.2 리텐션 정책 (Retention Policy)
- **실시간 로그 (`obd_logs`)**: 주행 중 1Hz로 쌓이는 데이터는 3일이 지나면 TimescaleDB의 `Drop Chunk` 기능을 통해 물리적으로 삭제하여 저장 공간을 최적화합니다.
- **주행 요약 (`trip_summaries`)**: 실시간 로그 삭제 전, 주행 거리/연비/점수 등을 요약하여 영구 보존합니다.
- **Soft Delete**: `users`, `vehicles` 등 주요 정보는 법적 분쟁 및 AI 재학습(비식별화)을 위해 실제 DB에서 삭제하지 않고 `deleted_at` 컬럼으로 관리합니다.

### 3.3 데이터 수집 및 처리 프로세스 (Lifecycle)

| 단계 | 발생 시점 | 주요 동작 | 대상 테이블 |
|:---|:---|:---|:---|
| **Step 1** | 시동 및 앱 연동 | 신규 `trip_id` 생성 및 주행 시작 기록 (상태: PENDING) | `trip_summaries` |
| **Step 2** | 주행 중 | 1Hz 간격 로우 데이터 적재 및 DB 실시간 부분 집계 | `obd_logs` |
| **Step 3** | 시동 종료 | 주행 종료 시각 기록 및 DB 집계 데이터(CAGG) 호출 | `obd_logs`, `trip_summaries` |
| **Step 4** | 최종 가공 | 백엔드에서 운전 점수 등 비즈니스 로직 산출 후 레코드 완성 | `trip_summaries` |

> [!NOTE]
> **Continuous Aggregates 활용**: `obd_logs`의 거대 데이터를 백엔드에서 매번 전수 조사하지 않도록 DB 수준에서 1차 가공(급가속 등 수치 요약)을 수행합니다.

### 3.4 데이터 동기화 및 모니터링 세부 정책

#### 3.4.1 데이터 선선도 (Data Freshness)
- **OBD 실시간 로그**: 사용자가 차량에 탑승하고 앱이 실행 중인 경우 **1Hz(1초 단위)** 수집을 보장합니다.
- **제조사 API (Cloud)**: API 호출 비용 및 차량 배터리 보호를 위해 **1시간 단위 스케줄러**를 통한 동기화를 기본으로 합니다. (실시간성보다 상태 추적 목적)

#### 3.4.2 긴급 상태 대응 (`ERROR` Handling)
- **감지 시점**: `cloud_telemetry` 동기화 도중 `charging_status`가 `ERROR`로 확인될 경우.
- **대응 로직**: 백엔드는 즉시 `user_notifications` 테이블에 긴급 알림 레코드를 생성하고 FCM 신호를 발송합니다.
- **판단 기준**: 실시간 '방전' 감지는 OBD 전압 데이터(`voltage`)를 우선하며, 클라우드 데이터는 보조 지표로 활용합니다.

#### 3.4.3 DTC 감지 및 관리 전략 (Persistence & Safety)
- **불변 이력 (Immutable History)**: 차량 제어기(ECU)에서 DTC가 삭제(Mode 04)되거나 감지되지 않더라도, `dtc_history`의 해당 레코드는 절대 삭제하지 않습니다. 오직 `status`와 `resolved_at`만 갱신합니다.
- **상시 감지**: Mode 01(MIL 상태)을 1초 주기로 체크합니다.
- **기록 시점**: MIL 점등 또는 신규 DTC 감지 시 즉시 Mode 02(Freeze Frame)를 수집하여 기록합니다.
- **해결 정합성**: 
    - `CLEARED`: 사용자가 앱에서 '삭제 명령'을 보냈을 때의 상태.
    - `RESOLVED`: 정비 이력(`maintenance_logs`)이 등록되거나, 일정 주행 기간 동안 해당 DTC가 재발생하지 않음을 AI가 확인했을 때의 상태.
- **재확인 로직**: '삭제'된 DTC가 다시 감지될 경우, 신규 레코드가 아닌 기존 레코드와의 연관성을 분석하여 '미결된 고장'으로 리스크 가중치를 부여합니다.

#### 3.4.4 정비 이력 관리 (Single Source)
- **원칙**: 공공 데이터와의 병합 로직을 폐기하고, 사용자의 **수동 입력**(`maintenance_logs`)을 유일한, 신뢰할 수 있는 관리 기준으로 삼습니다.
- **데이터 풍부성**: 사용자가 입력한 가격, 메모, 사진 등은 소모품 주기 예측의 핵심 학습 데이터로 보존합니다.

#### 3.4.5 커넥션 풀 및 트랜잭션 정책
- **원칙**: 모든 원격 호출(AI 서버, 클라우드 API) 시 DB 트랜잭션을 점유하지 않음.
- **데이터 정합성**: `status` 컬럼(PENDING, PROCESSING, COMPLETED, ERROR)을 이용한 상태 전이 기반의 무결성 보장.
- **풀 관리**: API 서버와 배치 워커의 커넥션 풀 분리 운영 권장.

#### 3.4.6 OBD 모드(Mode)별 데이터 매핑 가이드
표준 OBD-II 프로토콜의 각 모드별 데이터가 저장되는 위치를 정의합니다.

| OBD Mode | 설명 | 저장 위치 (테이블/컬럼) | 비고 |
|:---|:---|:---|:---|
| **Mode 01** | 실시간 센서 데이터 (PIDs) | `obd_logs` (주요 지표), `json_extra` (특화 데이터) | MIL 상태 포함 |
| **Mode 02** | 고장 시점 스냅샷 (Freeze Frame) | `dtc_freeze_frames` | 정규화된 컬럼 기반 저장 |
| **Mode 03** | 저장된 고장 코드 (Stored DTCs) | `dtc_history` (`dtc_type='STORED'`) | 확정된 고장 |
| **Mode 04** | 고장 코드 및 저항값 삭제 | `dtc_history.resolved_at` 갱신 | 삭제 액션 결과 반영 |
| **Mode 06** | 모니터링 테스트 결과 | `ai_evidences.ai_analysis` | 고급 진단 시 스냅샷 저장 |
| **Mode 07** | 미확정 고장 코드 (Pending DTCs) | `dtc_history` (`dtc_type='PENDING'`) | 간헐적 오류 추적 |
| **Mode 09** | 차량 정보 (VIN 등) | `vehicles.vin` | 어댑터 연동 시 자동 수집 |
| **Mode 0A** | 영구 고장 코드 (Permanent DTCs) | `dtc_history` (`dtc_type='PERMANENT'`) | 삭제 후에도 남는 기록 |

---

## 4. 데이터 삭제 및 보존 원칙 (Data Retention Policy)

> [!IMPORTANT]
> **모든 데이터는 물리적으로 완전히 삭제하지 않는 것을 원칙으로 합니다.**

1.  **Soft Delete 적용**: 사용자의 서비스 탈퇴 또는 차량 삭제 시에도 DB의 `deleted_at` 컬럼만 업데이트하며, 로우(Row) 자체는 삭제하지 않습니다.
2.  **AI 재학습 활용**: 삭제 처리된 데이터는 서비스 운영 목적에서는 제외되나, **개인식별정보(Email, VIN, 차번호 등)를 제거(Anonymization)**한 후 AI 모델의 고도화 및 학습용 데이터셋으로 영구 보존하여 활용합니다.
3.  **데이터 무결성**: 시계열 데이터(`obd_logs`) 역시 3일 후 핫 스토리지에서 삭제되기 전, 반드시 `trip_summaries` 및 `ai_evidences`로 유의미한 정보가 추출/정제되었음을 보장해야 합니다.

---

---


---
**[문서 끝]**

