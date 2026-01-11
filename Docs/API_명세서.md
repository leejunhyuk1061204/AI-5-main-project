# API 상세 명세서 (v1.4)

## 1. 공통 규격
- **기본 URL**: `/api/v1`
- **인증**: JWT (Header: `Authorization: Bearer {token}`)
- **응답 형식**: `{ "success": boolean, "data": object|null, "error": { "code": string, "message": string }|null }`

---

## 2. 사용자 및 인증 (Auth & Users)

### 2.1 회원가입/로그인
- **POST `/auth/signup` (FR-USER-001)**: 이메일 기반 회원가입
- **POST `/auth/login` (FR-USER-002)**: 로그인 및 JWT 발급
- **POST `/auth/logout` (FR-USER-007)**: 로그아웃 (토큰 무효화 처리)

### 2.2 계정 및 보안
- **GET `/users/me` (FR-USER-003)**: 내 프로필 정보 및 멤버십 조회
- **PATCH `/users/me` (FR-USER-004)**: 닉네임, FCM 토큰 업데이트
- **POST `/users/me/password` (FR-USER-005)**: 비밀번호 변경
- **DELETE `/users/me` (FR-USER-006)**: 회원 탈퇴 (Soft Delete & 익명화)

### 2.3 서비스 설정
- **GET `/users/me/settings` (FR-NOTI-001)**: 알림 항목별 ON/OFF 상태 조회
- **PUT `/users/me/settings` (FR-NOTI-001)**: 알림 설정 일괄 업데이트

---

## 3. 차량 관리 (Vehicles)

### 3.1 등록 및 조회
- **POST `/vehicles` (FR-CAR-001)**: 차량 등록 (VIN/차번호 기반)
- **GET `/vehicles` (FR-CAR-002)**: 내 차량 리스트 조회
- **GET `/vehicles/{vehicles_id}` (FR-CAR-003)**: 특정 차량 상세 정보 및 제원

### 3.2 수정 및 설정
- **PATCH `/vehicles/{vehicles_id}` (FR-CAR-004)**: 차량 별명, 메모 수정
- **POST `/vehicles/{vehicles_id}/primary` (FR-CAR-005)**: 대표 차량으로 설정
- **DELETE `/vehicles/{vehicles_id}` (FR-CAR-006)**: 차량 삭제 (Soft Delete)

---

## 4. 텔레메트리 및 데이터 (Telemetry)

### 4.1 OBD 데이터
- **POST `/telemetry/obd` (FR-OBD-003, FR-DRIVE-001)**: 실시간 로그 배치 업로드
- **GET `/trips` (FR-DRIVE-002)**: 주행 이력 목록
- **GET `/trips/{trip_id}` (FR-DRIVE-002, 003)**: 상세 주행 보고서 및 운전 점수

### 4.2 제조사 클라우드 연동
- **POST `/cloud/connect` (FR-CLOUD-001)**: 제조사 OAuth 연동 요청 (입구)
- **POST `/cloud/callback` (FR-CLOUD-001)**: OAuth 인증 코드 전달 및 토큰 교환
- **POST `/cloud/sync` (FR-CLOUD-002)**: 클라우드 데이터 강제 동기화 트리거

---

## 5. AI 진단 및 예지 (Diagnosis & AI)

### 5.1 고장 진단 (DTC)
- **GET `/vehicles/{id}/dtc` (FR-DIAG-001)**: 현재/기존 DTC 이력 조회 (정규화된 Freeze Frame 포함)
- **POST `/vehicles/{id}/dtc/clear` (FR-DIAG-001)**: DTC 삭제 명령 전송

### 5.2 정밀 진단 시스템
- **POST `/ai/diagnose` (FR-DIAG-002)**: 멀티모달 진단 요청 (소리, 사진 등 포함)
- **GET `/ai/diagnose/{session_id}` (FR-DIAG-003)**: 진단 리포트 조회
- **GET `/ai/missions/{session_id}` (FR-DIAG-004)**: AI 추가 증거 요청(미션) 확인

### 5.3 이상 감지 및 예지
- **GET `/vehicles/{id}/anomalies` (FR-ANOMALY-001, 002)**: 실시간 이상 징후 이력 조회
- **GET `/vehicles/{id}/predictions` (FR-PREDICT-002)**: 부품 및 고장 시점 사전 예측 정보

---

## 6. 소모품 및 알림 (Parts & Notifications)

### 6.1 소모품 관리
- **GET `/vehicles/{id}/consumables` (FR-PARTS-004)**: 소모품 상태 목록 조회
- **POST `/maintenance` (FR-PARTS-001)**: 정비 기록 추가 및 주기 리셋

### 6.2 알림 및 리콜
- **GET `/notifications` (FR-RECALL-003)**: 알림 내역 조회
- **GET `/external/recall/{vin}` (FR-RECALL-001)**: 국토부 리콜 상세 정보
- **GET `/personal/insights` (FR-PERS-001)**: 개인화 인사이트(미니 보고서) 조회

---

## 7. 외부 데이터 및 지식 (External)
- **GET `/external/car-specs/{vin}` (FR-CAR-003)**: 차량 상세 제원 연동
- **GET `/ai/knowledge/search` (FR-DIAG-005)**: 지식베이스 RAG 검색
- **GET `/external/used-car/performance/{id}` (FR-VALUE-001)**: 중고차 성능점검 기록 조회
