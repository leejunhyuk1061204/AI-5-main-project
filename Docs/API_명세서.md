# API 상세 명세서 (v2.0)

> **문서 개요**: 본 문서는 시스템 간 통신 규격을 정의하며, 크게 **Client(App) ↔ Backend(Java)** 와 **Backend(Java) ↔ AI Server(Python)** 두 가지 파트로 나뉩니다.
> **RabbitMQ**는 내부 인프라 통신용이므로 본 REST API 명세에는 포함되지 않습니다.

---

# Part 1. Frontend ↔ Backend API
> **Mobile App**과 **Java Backend** 간의 통신 규격입니다.
> - **Base URL**: `https://api.car-sentry.com/api/v1`
> - **Auth**: `Authorization: Bearer {jwt_token}`

### 📦 공통 응답 규격 (Common Response)
모든 API 응답은 `ApiResponse` 객체로 래핑되어 전달됩니다.
```json
{
  "success": true,
  "data": { ... },
  "error": null
}
```
- **success**: 요청 처리 성공 여부 (boolean)
- **data**: 실제 결과 데이터 (성공 시에만 존재, 실패 시 null)
- **error**: 에러 정보 (실패 시에만 존재, 성공 시 null)
  - `code`: 에러 코드
  - `message`: 상세 에러 메시지

## 1. 사용자 및 인증 (Auth & Users)

### 1.1 인증 (Authentication)
- **POST `/auth/signup` (FR-USER-001)**: 회원가입 (이메일, 비밀번호, 닉네임)
- **POST `/auth/login` (FR-USER-002)**: 로그인 (JWT Access/Refresh Token 발급)
- **POST `/auth/refresh` (FR-USER-008)**: 토큰 갱신
- **POST `/auth/logout` (FR-USER-007)**: 로그아웃

### 1.2 사용자 정보 (User Profile)
- **GET `/users/me` (FR-USER-003)**: 내 프로필 조회
- **PATCH `/users/me` (FR-USER-004)**: 프로필 수정 (닉네임, FCM 토큰)
- **POST `/users/me/password` (FR-USER-005)**: 비밀번호 변경
- **DELETE `/users/me` (FR-USER-006)**: 회원 탈퇴

### 1.3 설정 (Settings)
- **GET `/users/me/settings` (FR-NOTI-001)**: 알림 설정 조회 (정비, 이상징후, 리콜 등)
- **PUT `/users/me/settings` (FR-NOTI-001)**: 알림 설정 수정

---

## 2. 차량 관리 (Vehicles)

### 2.1 차량 등록 및 조회
- **POST `/vehicles` (FR-CAR-001)**: 차량 등록
    - **Body**: `vin`(Optional), `car_number`, `manufacturer`, `model`, `year`, `fuel_type`
- **GET `/vehicles` (FR-CAR-002)**: 보유 차량 목록 조회
- **GET `/vehicles/{id}` (FR-CAR-003)**: 차량 상세 정보 조회
- **PATCH `/vehicles/{id}` (FR-CAR-004)**: 차량 정보 수정 (별명, 메모)
- **POST `/vehicles/{id}/primary` (FR-CAR-005)**: 대표 차량 설정
- **DELETE `/vehicles/{id}` (FR-CAR-006)**: 차량 삭제

### 2.2 공공 데이터 및 마스터 데이터 (Data & Spec)
- **GET `/master/manufacturers` (BE-VH-003)**: 제조사 목록 조회
    - **Response**: `["Hyundai", "Kia", ...]`
- **GET `/master/models?manufacturer={name}` (BE-VH-003)**: 제조사별 모델 데이터 조회
    - **Query**: `manufacturer` (필수, e.g., "Hyundai")
    - **Response**: `[{ "modelName": "Avante (CN7)", "modelYear": 2024, "fuelType": "GASOLINE" }, ...]`
    - **Strategy**: 프론트엔드에서 모델명/연식/연료 드롭다운 필터링 처리
- **GET `/vehicles/{id}/spec` (FR-CAR-007)**: 차량 제원 상세 조회 (배기량, 연비 등 - 공공 API 캐시)
- **GET `/vehicles/{id}/recall` (FR-RECALL-001)**: 리콜 대상 여부 및 상세 조회 (국토부 API)
- **GET `/vehicles/{id}/inspection` (FR-INSP-001)**: 정기검사 유효기간 및 이력 조회 (교통안전공단)
- **GET `/vehicles/{id}/performance` (FR-VALUE-001)**: 중고차 성능점검 기록 조회 (교통안전공단)

---

## 3. 텔레메트리 및 운전 분석 (Telemetry)

### 3.1 주행 데이터
- **POST `/telemetry/batch` (FR-OBD-001)**: [앱→서버] OBD 로그 배치 업로드 (3분 주기)
    - **Body**: `[{timestamp, rpm, speed, ...}, ...]`
- **GET `/trips` (FR-DRIVE-002)**: 주행 이력 목록 조회 (기간 필터)
- **GET `/trips/{trip_id}` (FR-DRIVE-003)**: 상세 주행 리포트 (경로, 운전점수, 급가속 횟수 등)
- **GET `/telemetry/status/{vehicleId}` (FR-OBD-002)**: 차량의 실시간 연결 및 주행 상태 조회
- **POST `/telemetry/status/{vehicleId}/disconnect` (FR-OBD-005)**: 앱에서 수동으로 연결 해제 시 현재 주행 세션 즉시 종료
    - **Response**: `{ "success": true, ... }`

### 3.2 제조사 클라우드 연동 (Cloud)
- **POST `/cloud/connect` (FR-CLOUD-001)**: OAuth 연동 시작 (Redirect URL 반환)
- **POST `/cloud/callback` (FR-CLOUD-002)**: 인증 코드 수신 및 토큰 교환
- **POST `/cloud/sync` (FR-CLOUD-003)**: 데이터 수동 동기화 요청

---

## 4. 정비 및 예지 (Maintenance & AI)

### 4.1 진단 및 리포트
- **POST `/ai/diagnose` (FR-DIAG-002)**: 멀티모달 진단 요청
    - **Request (Multipart)**:
        - `type`: "VISION" | "AUDIO" | "HYBRID"
        - `file`: 이미지 또는 오디오 파일
        - `obd_context`: (Optional) 최근 OBD 스냅샷
    - **Response**: `session_id` 반환 (비동기 처리)
- **GET `/ai/diagnose/{session_id}` (FR-DIAG-003)**: 진단 결과 상세 조회 (Polling)
- **GET `/ai/missions/{session_id}` (FR-DIAG-004)**: 추가 증거 요청 미션 확인

### 4.2 이상 감지 및 예측
- **GET `/vehicles/{id}/anomalies` (FR-ANOMALY-001)**: 이상 징후 감지 이력
    - **Query**: `start_date`, `end_date`, `page`, `size`
- **GET `/vehicles/{id}/predictions` (FR-PREDICT-001)**: 소모품 수명 예측 및 교체 추천일
    - **Response**: 부품별 `remaining_life (%)`, `predicted_date`, `wear_factor`

### 4.3 차계부 (Maintenance Log)
- **GET `/maintenance` (FR-LOG-001)**: 정비 내역 조회
- **POST `/maintenance` (FR-LOG-002)**: 정비 내역 수동 입력 (영수증 OCR 포함)
- **PUT `/maintenance/{log_id}` (FR-LOG-003)**: 내역 수정
- **DELETE `/maintenance/{log_id}` (FR-LOG-004)**: 내역 삭제

---

## 5. 부가 기능 (Features)
- **GET `/notifications` (FR-NOTI-002)**: 알림 센터 내역 조회
- **GET `/insights/personal` (FR-INSIGHT-001)**: 개인화 운전/정비 인사이트 조회
- **GET `/knowledge/search` (FR-RAG-001)**: 자동차 Q&A (RAG 검색)

---
---

# Part 2. Backend ↔ AI Server API (Internal)
> **Java Backend**가 **Python AI Server**로 추론을 요청할 때 사용하는 내부 API입니다.
> - **Base URL**: `http://ai-service:8000` (Private Network)
> - **Protocol**: HTTP/1.1 (Wait for Response)

### 1. Vision Analysis (YOLOv8)
- **POST `/predict/vision`**
    - **Description**: 차량 외관 이미지를 분석하여 손상 부위 탐지.
    - **Request (Multipart)**:
        - `file`: 이미지 파일 (Binary)
    - **Response (JSON)**:
        ```json
        {
            "status": "DAMAGED",
            "damage_area_px": 4500,
            "detections": [
                {
                    "label": "SCRATCH",
                    "confidence": 0.92,
                    "bbox": [120, 45, 200, 150] // [x, y, w, h]
                }
            ],
            "processed_image_url": "s3://..."
        }
        ```

### 2. Audio Diagnosis (AST)
- **POST `/predict/audio`**
    - **Description**: 엔진/부품 소리를 분석하여 이상 유무 및 원인 판별.
    - **Request (Multipart)**:
        - `file`: 오디오 파일 (.wav, .m4a)
    - **Response (JSON)**:
        ```json
        {
            "primary_status": "FAULTY",
            "component": "ENGINE_BELT",
            "detail": {
                "diagnosed_label": "SLIP_NOISE",
                "description": "구동 벨트 장력 부족 의심"
            },
            "confidence": 0.88,
            "is_critical": false
        }
        ```

### 3. Anomaly Detection (LSTM-AE)
- **POST `/predict/anomaly`**
    - **Description**: 시계열 OBD 데이터를 분석하여 이상 징후 패턴 감지.
    - **Request (JSON)**:
        ```json
        {
            "time_series": [
                { "rpm": 2500, "load": 45.5, "coolant": 92.0, "voltage": 13.5 },
                { "rpm": 2510, "load": 46.0, "coolant": 92.1, "voltage": 13.4 },
                ... // (60 items for 60s window)
            ]
        }
        ```
    - **Response (JSON)**:
        ```json
        {
            "is_anomaly": true,
            "anomaly_score": 0.85,
            "threshold": 0.70,
            "contributing_factors": ["RPM", "VOLTAGE"]
        }
        ```

### 4. Wear Factor Prediction (XGBoost)
- **POST `/predict/wear-factor`**
    - **Description**: 차량 누적 데이터 및 운전 습관을 기반으로 소모품 노화 계수 예측.
    - **Request (JSON)**:
        ```json
        {
            "target_item": "ENGINE_OIL", // [Add] 예측 대상 (ENGINE_OIL, BRAKE_PADS, TIRES 등)
            "last_replaced": {           // [Add] 마지막 교체 시점
                "date": "2025-06-01",
                "mileage": 48000         // [Check] 교체 당시 총 주행거리 (누적값) -> 현재-이거 = 사용량
            },
            "vehicle_metadata": {
                "model_year": 2020,
                "fuel_type": "GASOLINE",
                "total_mileage": 52000
            },
            "driving_habits": {
                "avg_rpm": 2200,
                "hard_accel_count": 15,
                "hard_brake_count": 8,
                "idle_ratio": 0.15
            }
        }
        ```
    - **Response (JSON)**:
        ```json
        {
            "predicted_wear_factor": 1.15, // 표준 대비 1.15배 빠르게 마모 중
            "model_version": "v1.0.2"
        }
        ```
