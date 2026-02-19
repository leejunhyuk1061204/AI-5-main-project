# OBD Anomaly Progress Log

## Pre-Step3 Summary (Step1~2)

- vFinal 방향 확정: Hybrid(Stat/AE) + Quality Gating + Policy 구조 채택
- 문서/API 명세 정렬: `window_sec=60`, `stride_sec=30`, `domains+events` 중심 응답 유지
- 코어 스키마 정리: Core10에서 실차 대응 가능한 Core7로 전환
- 엔진 경로 리팩터링: 스코어러/정책/아티팩트 로딩 구조 분리
- 기본 안정성 확보: artifact 부재 시 degraded 동작, API 정상 응답 보장
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

## 2026-02-16 | Step4: Policy/Top-Signals refinement + sample runner

### 1) 변경 요약 (What Changed)
- 정책 로직 보강
  - `k_consecutive`, `cooldown_sec` 경계값 방어(`k>=1`, `cooldown>=0`)
  - policy event에 `streak`, `start_t` 메타 추가
- severity 판정 기준을 policy 값(`warning`, `critical`) 우선 사용
- `top_signals` 정규화 보강
  - 합계가 0일 때 `0,0,0` 대신 균등 분배 fallback
  - 서비스/스코어러 양쪽 경로에서 일관 처리
- IF 통계 계산 경고 완화
  - 빈 diff 슬라이스에서 `nanmean` 경고 방지
- 샘플 실행 스크립트 추가
  - `ai/scripts/obd_engine/run_obd_anomaly_sample.py`

### 2) 수정 파일 (Files Changed)
- `ai/app/services/obd_anomaly/core/policy/threshold_policy.py`
- `ai/app/services/obd_anomaly/core/scorers/engine_scorer.py`
- `ai/app/services/obd_anomaly/core/scorers/iforest_scorer.py`
- `ai/app/services/obd_anomaly/obd_anomaly_service.py`
- `tests/test_obd_policy_top_signals.py` (신규)
- `ai/scripts/obd_engine/run_obd_anomaly_sample.py` (신규)

### 3) 검증 결과 (Validation)
- 실행 명령:
  - `python -m pytest -q ..\\tests\\test_obd_anomaly_vfinal.py ..\\tests\\test_obd_policy_top_signals.py`
  - `python scripts\\obd_engine\\run_obd_anomaly_sample.py`
- 결과:
  - `7 passed, 1 warning`
  - 샘플 응답에서 `ENGINE_POLICY_ANOMALY` 이벤트 정상 생성 확인
  - `domains.engine.top_signals.contribution` 값이 0이 아닌 정규화 값으로 출력 확인

### 4) 참고 사항 (Notes)
- 현재 샘플은 artifact 부재(degraded) 환경에서도 정책/이벤트 경로가 동작함을 확인하기 위한 목적
- 남은 warning은 Pydantic v2 deprecation (`Config` -> `ConfigDict`)이며 기능 영향은 없음

## 2026-02-18 | Step6: One-class dataset split/training policy

### One-class 학습 원칙
- 학습 대상: `is_normal=true` 샘플만 사용
- 정상 라벨 기준: `normal`, `frei`, `stau` (및 `0`, `NORMAL` 호환)
- 학습 제외: `is_normal=false` 샘플
  - 해석: 이상/불확실 샘플은 train에 섞지 않고 val/test, 리플레이 평가 용도로만 사용

### Split 원칙
- 비율: `train/val/test = 70/15/15`
- 방식: `trip_id` 또는 `session_id` 그룹 단위 split (윈도우 랜덤 split 금지)
- 목적: 데이터 누수(leakage) 방지 및 정책(threshold/K/cooldown) 검증 신뢰성 확보

### 실행 결과 (Data Prep)
- 실행 스크립트:
  - `prepare_obd_raw_core7.py`
  - `prepare_dataset.py`
- 결과:
  - rows_total: `2,732,486`
  - trips_total: `81`
  - split_groups: `train=56`, `val=12`, `test=13`
- 이슈/수정:
  - 이슈: 초기 실행에서 `trips=0`으로 집계되어 split 실패
  - 원인: `prepare_obd_raw_core7.py`에서 `trip_id/label` 인덱스 정렬 불일치로 NaN 발생
  - 해결: DataFrame 인덱스를 시간축 인덱스로 맞춘 뒤 `trip_id/label` 컬럼을 고정 문자열로 주입
- 상태:
  - Data prep 완료
  - 다음 단계: `train_iforest.py` -> `train_lstm_ae.py` -> `eval_policy.py`

