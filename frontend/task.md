# 📂 프로젝트 기능 현황 및 태스크 (Frontend)

## ✅ 완료된 기능 (Done)
### 🔐 인증 & 사용자 (Auth & User)
- [x] **기본 인증**: 회원가입, 로그인, 로그아웃 (JWT 기반)
- [x] **소셜 로그인**: 카카오, 구글 로그인 연동 (기능 구현 완료)
- [x] **토큰 관리**: 액세스 토큰 자동 갱신 (Axios Interceptor)
- [x] **마이페이지**: 내 정보 조회 및 수정

### 🚗 차량 관리 (Vehicle)
- [x] **차량 등록**: 수동 등록 및 OBD 스캔 등록 흐름
- [x] **조회**: 내 차 목록 조회, 대표 차량 설정 바인딩
- [x] **상세 제원**: `ServiceSpecs` API 연동 및 제원 상세 페이지 (`Spec.tsx`)
- [x] **멤버십**: 멤버십 상태 조회 및 페이지 UI (`Membership.tsx`)
- [x] **OCR 차계부**: 영수증 인식 및 차계부 자동 등록 기능

### 📊 주행 및 데이터 (Trip & Data)
- [x] **주행 기록**: 최신 주행 카드(`DrivingHis.tsx`) 및 전체 이력 리스트(`DrivingList.tsx`) 분리 구현
- [x] **안전 지수**: 메인 페이지 종합 점수 및 상태 표시
- [x] **OBD 통신**: BLE/Classic 블루투스 연결, 실시간 데이터 파싱 (`ObdService.ts`)
- [x] **데이터 전송**: 3분 단위 배치 업로드, 버퍼 플러시 로직
- [x] **시뮬레이션**: OBD 연결 없는 상태에서의 시뮬레이션 모드 (랜덤 점수 생성 및 타임존 이슈 해결)
- [x] **오프라인 모드**: 주행 데이터(Telemetry) 및 주행 종료는 SQLite 큐 구현 완료. **DTC 보고 기능(백그라운드 큐잉) 구현 완료**.
- [x] **그래프 최적화**: `DrivingHis.tsx` 렌더링 최적화 (`useMemo` 적용)

### 🧠 AI 진단 (AI Diagnosis)
- [x] **복합 진단 (Chatbot)**: 챗봇 문진 및 진단 프로세스 (로딩 메시지 UX 개선 완료)
- [x] **소리 진단**: 엔진 시동음 녹음 및 분석 요청 로직
- [x] **영상 진단**: 외관 촬영 및 분석 요청 로직
- [x] **프롬프트 수정**: AI 진단 정확도 향상을 위한 프롬프트 업데이트

### 🔔 알림 및 정비 (Notification & Maintenance)
- [x] **FCM 푸시 알림**: 
  - 백엔드 Firebase 설정 오류(키 파일, 프로젝트 ID) 해결
  - `fcmService.ts` 구현 (Foreground/Background/Quit 상태 핸들링)
  - FCM 토큰 자동 등록/갱신 로직 구현
- [x] **정비 이력 페이지**: `MaintenanceHistory.tsx` 구현 및 API 연결
- [x] **소모품 관리**: 소모품 교체 주기 관리 및 예외 처리 (`SupManage.tsx`)
- [x] **알림 목록**: 서버 알림 조회/읽음 처리 (`AlertMain.tsx`)

### 🛠 시스템 (System)
- [x] **에러 핸들링 강화**: `GlobalErrorBoundary` 및 `CustomErrorModal` (Glassmorphism UI) 적용 완료
- [x] **환경 설정**: `.env` 관리 및 API 키 보안
- [x] **네이티브 기능**: 카메라, 마이크, 블루투스 권한 및 기능 연동 (`app.config.ts`)
- [x] **백그라운드 수집**: `BackgroundService`와 `ObdService` 연동 완료
- [x] **안드로이드 안정성**: 포그라운드 서비스 타입(`connectedDevice`) 명시 및 배터리 최적화 안내 팝업 구현
- [x] **로그아웃 Store 초기화**: 로그아웃 시 모든 store reset 처리 완료
- [x] **Deep Link**: 결제 성공 등 외부 앱 연동을 위한 딥링크 설정 (`frontend://`)

---

## 🔥 진행 중 및 예정 (In Progress & Todo)

### 🚀 최종 점검 및 고도화
- [x] **FCM 딥링크 테스트**: 
  - [x] 알림 클릭 시 `DiagnosisReport`, `SupManage` 등으로 올바르게 이동하는지 검증
  - [x] 앱 종료/백그라운드 상태에서의 동작 확인
- [x] **오프라인 모드**: 네트워크 연결 끊김 시 데이터 로컬 저장 (SQLite) 후 재연결 시 자동 전송 구현
- [x] **타입스크립트 강화**: `any` 타입 지양 및 엄격한 타입 적용
- [ ] **Native Build**: `expo-updates` 모듈 사용을 위해 `npx expo run:android` 또는 `eas build` 필요 (현재 방어 코드 적용됨)

### ⚠️ 미연결 백엔드 API (우선순위 낮음)
- 없음 (현재 모든 필수 API 연결 완료)

---

### 🔗 백엔드-프론트엔드 연결 상태 (Backend API Sync)

#### ✅ 정상 연결됨 (Connected)
- **Auth**: 회원가입, 로그인, 정보수정, **FCM 토큰 갱신 (`PATCH /auth/fcm-token`)**
- **Vehicle**: 차량 등록(수동/OBD), 조회, 대표차량 설정, 상세정보, **차량 삭제 (`DELETE /vehicles/{id}`)**
- **Maintenance**: 정비 이력 조회/등록, 소모품 상태 조회 (`GET /vehicles/{id}/consumables`)
- **Notification**: 알림 목록 조회, 읽음 처리
- **Diagnosis**: 챗봇/음성/영상 진단 요청 및 결과 조회
- **Trip**: **자동 주행 기록 (`POST /trips/start` & `end`)** - OBD 연결 시 자동 시작
- **Master**: 제조사/모델/소모품 데이터 조회 (`/master/**`)
- **Payment**: 카카오페이 결제 준비/승인 (`/payment/**`)
- **Settings**: 사용자 알림 설정 조회/수정 (`/user/settings`)
- **OCR**: 영수증 분석 및 정비 이력 연동 (`/ocr/**`)
- **Telemetry**: OBD 로그 배치 전송 및 상태 조회 (`/telemetry/**`)

#### ⚠️ 미연결 / 부분 연결 (Partial / Disconnected)
- 없음

