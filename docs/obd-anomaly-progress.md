# OBD Anomaly Progress Log

## 2026-02-16 | Step3: vFinal 엔진 보강 + 4케이스 테스트

### 1) 변경 요약 (What Changed)
- Core 스키마를 Core7로 확정 (`core_min=5`)
  - 해석: 실차 지원 가능한 7개 피처 기준으로 정렬/검증
- Hybrid 게이팅 정리 (`AE_ONLY / IF_ONLY / BOTH`)
  - 해석: 품질이 좋으면 AE, 나쁘면 IF, 애매하면 둘 다
- AE 실패 시 IF fallback 명시
  - 해석: 예외가 나도 서비스는 죽지 않고 IF로 안전 동작
- IF degraded 점수식 안정화
  - 해석: `iforest.pkl` 없어도 점수가 과도하게 튀지 않게 조정
- Artifact JSON 로딩 보강 (`utf-8-sig`)
  - 해석: BOM 인코딩 파일도 정상 파싱

### 2) 수정 파일 (Files Changed)
- `ai/app/services/obd_anomaly/models/schemas/v1/schema_core.json`
- `ai/app/services/obd_anomaly/core/scorers/engine_scorer.py`
- `ai/app/services/obd_anomaly/core/scorers/iforest_scorer.py`
- `ai/app/services/obd_anomaly/core/artifacts/loader.py`
- `ai/app/services/obd_anomaly/core/policy/threshold_policy.py`
- `tests/test_obd_anomaly_vfinal.py`
- `docs/4.API 명세서.md`

### 3) 추가 테스트 (4 Cases)
- 정상 데이터 -> 알람 낮음 (`is_anomaly=false`)
  - 해석: 정상 입력에서 오탐 억제 확인
- 컬럼 부족 -> `IF_ONLY`, AE `SKIPPED`
  - 해석: core feature 부족 시 안전하게 IF 경로 선택
- 결측/샘플링 불안정 -> `IF_ONLY`
  - 해석: 품질이 낮아도 API 정상 응답
- 강한 이상 패턴 -> K 연속 후 정책 이벤트 발생
  - 해석: threshold 1회 초과가 아니라 정책 기준으로 이벤트 생성

### 4) 검증 결과 (Validation)
- 실행 명령:
  - `python -m pytest -q ..\\tests\\test_obd_anomaly_vfinal.py`
- 결과:
  - `4 passed, 3 warnings`

### 5) 이슈 및 해결 (Issues & Fixes)
- 이슈: 모든 윈도우가 `SKIPPED`로 떨어짐
  - 원인: BOM 포함 JSON 파싱 실패
- 해결: JSON 로더를 `utf-8-sig` 우선 처리로 변경

### 6) 남은 경고 (Non-blocking)
- Pydantic v2 deprecation (`Config` -> `ConfigDict`)
- IF scorer의 빈 슬라이스 RuntimeWarning (기능상 치명적 아님)
