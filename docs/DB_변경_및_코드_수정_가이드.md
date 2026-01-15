# DB 설계 변경 및 코드 수정 가이드 (Report)

본 보고서는 최신화된 **DB 상세 설계서(v1.6)**와 현재 **백엔드 코드(Entity)** 간의 차이점을 분석하고, SRS 요구사항을 충족하기 위해 필요한 수정 사항을 정의합니다.

---

## 1. 개요
최신 SRS 반영 과정에서 AI 진단 고도화, 영수증 OCR, Smart EDR(선별적 저장) 기능이 추가됨에 따라 기존 데이터베이스 구조와 엔티티 클래스의 업데이트가 필요합니다.

---

## 2. 주요 불일치 및 수정 필요 사항

### 2.1 신규 필요 엔티티 (Missing Entities)
현재 코드에는 정의되어 있지 않으나, AI 기능 및 리포트 제공을 위해 반드시 추가되어야 할 테이블입니다.

| 테이블명 | 관련 엔티티명 | 관련 요구사항 | 주요 목적 |
|:---|:---|:---|:---|
| `anomaly_records` | `AnomalyRecord` | REQ-AI-01 | AI 기반 이상 탐지 이력 및 기여 요인 저장 |
| `user_insights` | `UserInsight` | REQ-USER-04 | 주행별/정기 AI 리포트 전문 저장 |
| `ai_evidences` | `AiEvidence` | REQ-AI-06 | 정밀 진단을 위한 멀티모달(사진/음성) 데이터 관리 |
| `diag_results` | `DiagResult` | REQ-AI-02 | AI 진단 세션의 상세 결과(Markdown 리포트 등) 저장 |

### 2.2 기존 엔티티 수정 사항 (Field Updates) - **반영 완료**
기존에 구현된 클래스에 신규 기능을 위한 필드를 추가하고 ID 정책을 동기화했습니다.

| 엔티티명 | 추가/수정 필드 | 설명 |
|:---|:---|:---|
| `DtcHistory` | `ragGuide` (Text) | [REQ-AI-03] RAG를 통해 생성된 직관적인 고장 가이드 저장 |
| `MaintenanceHistory` | `ocrData`, `shopName`, `isStandardized` | [REQ-EXT-02] 영수증 데이터 및 정비 시설 정보 저장 |

### 2.3 명칭 및 정책 정합성 (Discrepancies)
- **테이블명 반영 완료**: 설계서 표준(`maintenance_logs`)에 맞춰 엔티티의 테이블 매핑을 변경했습니다.
- **ID 타입 반영 완료**: `MaintenanceHistory`의 ID를 `Long`에서 `UUID`로 반영 완료하였습니다. 

---

## 3. 검증 필요 항목 (Test Requirements)

코드 수정 후 정상 동작 확인을 위해 반드시 테스트해야 할 항목들입니다.

### 3.1 ID 체계 변경 및 조회 검증
- [ ] **UUID 생성 확인**: 정비 이력 등록 시 `UUID`가 정상적으로 자동 생성되는지 확인합니다.
- [ ] **조회 및 매핑**: Repository와 Service에서 `UUID`를 통해 정비 이력을 정확히 조회하고 목록을 반환하는지 테스트합니다.

### 3.2 신규 필드 영속성 및 데이터 확인
- [ ] **RAG 가이드**: `DtcHistory`에 `ragGuide` 텍스트가 정상적으로 저장되고 API를 통해 응답되는지 확인합니다.
- [ ] **OCR 및 상세 데이터**: `MaintenanceHistory`에 `ocrData`(JSON), `shopName`, `isStandardized` 필드가 DB에 올바르게 반영되는지 확인합니다.

### 3.3 로직 정합성
- [ ] **소모품 상태 조회**: 엔티티 구조와 ID 타입이 변경된 후에도 `/api/vehicles/{vehicleId}/consumables` 호출 시 잔존 수명 계산 결과가 정확히 응답되는지 확인합니다.

---

## 4. 향후 작업 제언
- **신규 엔티티 구현**: `AnomalyRecord`, `UserInsight` 등 아직 생성되지 않은 엔티티들은 실제 기능 개발 시점에 설계서 v1.6을 참고하여 구현합니다.

---
**보고서 끝**
