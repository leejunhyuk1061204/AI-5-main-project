# 백엔드 API 기능 리스트 (컨트롤러별 정리)

백엔드 서버(`root/backend/src/main/java/kr/co/himedia/controller`)의 모든 컨트롤러에 정의된 API 기능 목록입니다.

---

## 1. AuthController (`/auth`)
인증 및 사용자 계정 관리 기능을 담당합니다.

| 기능명 | Method | Endpoint | 설명 |
| :--- | :--- | :--- | :--- |
| 회원가입 | POST | `/signup` | 신규 사용자 등록 |
| 로그인 | POST | `/login` | JWT 토큰 발급 |
| 토큰 갱신 | POST | `/refresh` | Refresh Token을 이용한 Access Token 갱신 |
| 내 정보 조회 | GET | `/me` | 로그인한 사용자의 프로필 정보 조회 |
| 정보 수정 | PATCH | `/me` | 사용자 프로필 정보 업데이트 |
| FCM 토큰 갱신 | PATCH | `/fcm-token` | 알림용 FCM 토큰 전용 업데이트 |
| 회원 탈퇴 | DELETE | `/me` | 계정 삭제 (Soft Delete 방식) |
| 프로필 이미지 업로드 | POST | `/me/image` | 프로필 사진 등록/수정 (Multipart) |

## 2. VehicleController (`/vehicles`)
차량 등록 및 관리 기능을 담당합니다.

| 기능명 | Method | Endpoint | 설명 |
| :--- | :--- | :--- | :--- |
| 차량 등록 | POST | `/` | 사용자 입력 정보로 차량 등록 |
| 차대번호 등록 (OBD) | POST | `/obd` | OBD VIN 정보를 이용한 단순 등록 | - VIN으로 차량정보 가져오는 api 불확실. -> 차량등록 + 차대번호 등록 만 구현
| 차량 목록 조회 | GET | `/` | 사용자가 등록한 모든 차량 리스트 |
| 차량 상세 조회 | GET | `/{vehicleId}` | 특정 차량의 상세 정보 조회 |
| 차량 정보 수정 | PUT | `/{vehicleId}` | 차량 닉네임, 메모 등 수정 |
| 대표 차량 설정 | PATCH | `/primary` | 메인 차량으로 지정 |
| 차량 삭제 | DELETE | `/{vehicleId}` | 차량 정보 삭제 (Soft Delete) |

## 3. TripController (`/trips`)
주행 세션 및 이력 관리 기능을 담당합니다.

| 기능명 | Method | Endpoint | 설명 |
| :--- | :--- | :--- | :--- |
| 주행 이력 목록 조회 | GET | `/` | 차량별 전체 주행 기록 조회 |
| 주행 이력 상세 조회 | GET | `/{tripId}` | 특정 주행의 상세 경로 및 통계 |
| 주행 세션 시작 | POST | `/start` | 새로운 주행 시작 (ID 발급) |
| 주행 세션 종료 | POST | `/end` | 주행 종료 및 기록 요약 저장 (자동 진단, 소모품 예측 Trigger) |

## 4. ObdController (`/telemetry`)
OBD 데이터를 통한 실시간 및 배치 데이터 수집을 담당합니다.

| 기능명 | Method | Endpoint | 설명 |
| :--- | :--- | :--- | :--- |
| 벌크 로그 수집 | POST | `/batch` | 3분 단위 OBD 로그 대량 저장 (JSON Body) |
| 연결 상태 조회 | GET | `/status/{vehicleId}` | 실시간 연결 및 주행 상태 확인 |
| 수동 연결 해제 | POST | `/status/disconnect` | 사용자에 의한 수동 종료 처리 |

## 5. AiController (`/ai`)
AI 진단 및 데이터 처리를 담당합니다.

| 기능명 | Method | Endpoint | 설명 |
| :--- | :--- | :--- | :--- |
| DTC 수신 처리 | POST | `/dtc` | 고장 코드 분석 및 처리 |
| AI 진단 요청 | POST | `/diagnose` | Vision(이미지)/Audio(소리) 개별 진단 |
| 통합 진단 요청 | POST | `/diagnose/unified` | 멀티모달(소리+사진+데이터) 통합 진단 (Multipart) |

## 6. MaintenanceController (`/api/vehicles`)
정비 기록 및 소모품 관리를 담당합니다.

| 기능명 | Method | Endpoint | 설명 |
| :--- | :--- | :--- | :--- |
| 정비 기록 등록 | POST | `/{vehicleId}/maintenance` | 신규 정비 내역 추가 |
| 소모품 상태 조회 | GET | `/{vehicleId}/consumables` | 주요 소모품 교체 주기 상태 확인 |

## 7. MasterController (`/master`)
시스템 공통 기초 데이터를 제공합니다.

| 기능명 | Method | Endpoint | 설명 |
| :--- | :--- | :--- | :--- |
| 제조사 목록 조회 | GET | `/manufacturers` | 등록된 모든 자동차 제조사 리스트 |
| 모델 목록 조회 | GET | `/models` | 특정 제조사의 차량 모델 및 연식 정보 |

## 8. AdminController (`/admin/test`)
시스템 관리 및 테스트용 API입니다.

| 기능명 | Method | Endpoint | 설명 |
| :--- | :--- | :--- | :--- |
| 과거 데이터 주입 | POST | `/insert-old-logs` | 테스트용 과거 로그 데이터 생성 |
| 리텐션 청소 실행 | POST | `/trigger-cleanup` | 로그 정리 스케줄러 강제 실행 |
| 리포트 생성 실행 | POST | `/trigger-report` | 주간 리포트 스케줄러 강제 실행 |

## 9. MediaController (`/media`)
파일 업로드 유틸리티입니다.

| 기능명 | Method | Endpoint | 설명 |
| :--- | :--- | :--- | :--- |
| 미디어 업로드 | POST | `/upload` | 이미지/오디오 파일 업로드 (Multipart) |

## 10. AiTestController (`/ai/test`)
AI/RAG 기능 단순 테스트용입니다.

| 기능명 | Method | Endpoint | 설명 |
| :--- | :--- | :--- | :--- |
| RAG 지식 검색 | GET | `/knowledge/search` | 지식 베이스 검색 테스트 (`?query=...`) |

---

## 11. ⚠️ 테스트가 어렵거나 불가능한 API (Untestable / Requires Setup)
이 섹션의 API는 Insomnia 등에서 단순 URL 호출로 테스트하기 어렵습니다.

| 컨트롤러 | Method | Endpoint | 사유 |
| :--- | :--- | :--- | :--- |
| **CloudAuthController** | GET | `/api/v1/auth/callback/{provider}` | 외부 OAuth 제공자(Google, Naver 등)의 인증 코드(`code`)와 콜백 리다이렉트가 필요함. |
| **GlobalExceptionHandler** | - | - | 직접 호출 불가. 에러 상황 유발 시 자동 동작. |
