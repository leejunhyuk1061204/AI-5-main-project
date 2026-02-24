# OBD Anomaly Progress Log

참조 문서:
- docs/obd-anomaly-design-and-overfitting-guardrails.md

## 2026-02-20 | Step9: 현재 상태 고정(빠른 판단용)

### 0) 보고용 수치 요약 (Final Snapshot)
- 데이터/학습
  - one-class(정상만 학습), split=`70/15/15`(trip 단위)
  - IF 학습 윈도우: `6332`
  - AE 학습: `epochs=10`, `loss 0.523741 -> 0.360000`, `elapsed=1788.76s`
  - AE 산출물: `lstm_ae.pt`, `scaler.json`
- 정책/임계값
  - threshold: `0.795981` (val q99 기준)
  - k_consecutive: `2`
  - cooldown_sec: `60`
- val 정상 분포
  - q50: `0.256836`
  - q90: `0.433243`
  - q95: `0.632952`
  - q99: `0.795981`
- 운영 오탐 지표
  - alarms_per_hour: `0.226986`
  - window-level FPR(근사): `~1%` (q99 threshold 설계 기준)
- AE 학습 상태 해석
  - epoch 진행에 따라 loss가 안정적으로 감소하여 정상 패턴 재구성 학습 수렴 확인
- 안정성
  - pytest: `8 passed, 4 warnings`

### 1) 지금 검증 완료
- 코드 안정성/회귀 테스트 통과
  - `python -m pytest -q ..\tests\test_obd_anomaly_vfinal.py ..\tests\test_obd_policy_top_signals.py`
  - 결과: `8 passed, 4 warnings`
- 강제 anomaly 판정 로직 제거 완료
  - 의도적으로 `is_anomaly=true`를 강제로 올리는 경로 제거
- 저품질 입력 대응 경로 확인
  - `INSUFFICIENT_CORE_FEATURES` 이벤트 노출
  - electrical 이벤트 중복 요약(`occurrences`) 동작 확인

### 2) 아직 미검증
- "실제 stall 탐지 성능"은 아직 미검증
  - 현재 kona 파일에서 rpm 급락 패턴 미관측
  - 관측값: `rpm_min=1441`, `rpm_max=1678`, `speed_max=46`

### 3) 검증 한계 (명시)
- 현재 확보된 실차 파일에는 stall 순간(엔진 rpm 급락) 구간이 포함되어 있지 않음
- 따라서 Step9 범위에서는 stall 탐지 "성능 검증"을 완료할 수 없음
- val/test가 정상-only(one-class)이므로 Precision/Recall/F1은 미산출

### 4) Step9 종료 기준 (확정)
- 종료 범위: 저품질 입력 처리 안정화 + 이벤트/요약/severity 동작 검증
- 미종료 범위: stall 포함 실차 로그 기반 탐지 성능 검증
- 다음 단계 입력 조건: stall 직전~직후 1~2분 로그 1건 확보 후 재검증


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

## 2026-02-19 | Step7: IF training

### 실행 결과 (IsolationForest)
- 실행 스크립트:
  - `train_iforest.py`
- 입력:
  - `train.jsonl` (split 결과, train trips=56)
- 결과:
  - status: `[OK] iforest trained`
  - windows_used: `6332`
  - model: `ai/app/services/obd_anomaly/models/artifacts/v1/iforest.pkl`
  - report: `ai/app/services/obd_anomaly/offline/datasets/vfinal/iforest_report.json`
- 해석:
  - train split에서 60/30(window/stride)로 생성된 6,332개 윈도우를 기반으로 정상 분포 학습 완료
- 다음 단계:
  - `train_lstm_ae.py` 실행

## 2026-02-19 | Step7: LSTM-AE training (in progress)

### 실행 계획
- 실행 스크립트:
  - `train_lstm_ae.py`
- 입력:
  - `train.jsonl` (split 결과, train trips=56)
- 파라미터:
  - `window_sec=60`
  - `stride_sec=30`
  - `epochs=10`
  - `batch_size=32`
  - `lr=1e-3`

### 기록 템플릿 (학습 종료 후 채우기)
- 결과:
  - status: `[OK] lstm-ae trained` | `FAILED` | `INTERRUPTED`
  - start_time:
  - end_time:
  - elapsed_sec:
  - final_loss:
  - windows_used:
  - model: `ai/app/services/obd_anomaly/models/artifacts/v1/lstm_ae.pt`
  - scaler: `ai/app/services/obd_anomaly/models/artifacts/v1/scaler.json`
  - report: `ai/app/services/obd_anomaly/offline/datasets/vfinal/lstm_ae_report.json`
- 다음 단계:
  - `eval_policy.py` 실행

### 실행 결과 (LSTM-AE)
- 실행 스크립트:
  - `train_lstm_ae.py`
- 결과:
  - status: `[OK] lstm-ae trained`
  - start_time: `2026-02-19 10:50:56`
  - end_time: `2026-02-19 11:20:44`
  - elapsed_sec: `1788.76` (약 29분 49초)
  - final_loss: `0.360000`
  - loss_trend: `0.523741 -> 0.360000` (10 epochs)
  - model: `ai/app/services/obd_anomaly/models/artifacts/v1/lstm_ae.pt`
  - scaler: `ai/app/services/obd_anomaly/models/artifacts/v1/scaler.json`
  - report: `ai/app/services/obd_anomaly/offline/datasets/vfinal/lstm_ae_report.json`
- 해석:
  - epoch 진행에 따라 재구성 손실이 안정적으로 감소하여 정상 패턴 학습이 진행됨
- 다음 단계:
  - `eval_policy.py` 실행 후 `threshold_policy.json` 확정

## 2026-02-19 | Step7: Policy evaluation

### 실행 결과 (Policy)
- 실행 스크립트:
  - `eval_policy.py`
- 결과:
  - status: `[OK] policy evaluated`
  - policy: `ai/app/services/obd_anomaly/models/artifacts/v1/threshold_policy.json`
  - report: `ai/app/services/obd_anomaly/offline/datasets/vfinal/policy_report.md`
- 핵심 정책값:
  - threshold: `0.795981`
  - k_consecutive: `2`
  - cooldown_sec: `60`
  - severity.warning: `0.7`
  - severity.critical: `0.85`
- 정상 분포/알람 지표(val):
  - q50: `0.256836`
  - q90: `0.433243`
  - q95: `0.632952`
  - q99: `0.795981`
  - alarms_per_hour: `0.226986`
- top_signals 예시:
  - `intake_air_temp_c`, `engine_rpm`, `throttle_pos_pct` 중심으로 상위 기여
- 참고:
  - `torch.load` 관련 FutureWarning 1건 발생(동작 영향 없음, 향후 `weights_only=True` 검토)

## 2026-02-19 | Step7: Integration test validation

### 실행 결과 (pytest)
- 실행 명령:
  - `python -m pytest -q ..\tests\test_obd_anomaly_vfinal.py ..\tests\test_obd_policy_top_signals.py`
- 결과:
  - `8 passed, 4 warnings in 4.47s`
- 경고 (non-blocking):
  - Pydantic v2 deprecation (`Config` -> `ConfigDict`)
  - `torch.load(weights_only=False)` future warning
- 결론:
  - Step7 학습/정책 반영 상태에서 핵심 통합 테스트 통과

## 2026-02-19 | Step7: Sample run validation

### 실행 결과 (run_obd_anomaly_sample.py)
- 실행 명령:
  - `python scripts\obd_engine\run_obd_anomaly_sample.py`
- 결과:
  - 샘플 실행 자체는 정상 완료 (응답 JSON 반환)
  - `torch.load(weights_only=False)` FutureWarning 1건 (non-blocking)

### 관찰된 정합성 이슈 (todo)
- 현상:
  - `anomaly_score=1.0`
  - `events[]`에 `ENGINE_HYBRID_ANOMALY` 존재
  - 최상위 `is_anomaly=false`
- 해석:
  - 점수/이벤트와 최상위 anomaly 플래그 간 정합성 불일치
- 다음 조치:
  - `obd_anomaly_service`의 최종 `is_anomaly` 집계 로직과 policy 반영 순서 점검
  - 수정 후 sample 재실행으로 확인

### 조치 결과 (fixed)
- 수정 파일:
  - `ai/app/services/obd_anomaly/obd_anomaly_service.py`
- 수정 내용:
  - 엔진 이벤트 수집을 policy 이벤트 중심으로 정리
  - 최상위 `anomaly_score`를 최종 anomaly 판정과 일치하도록 계산 로직 보정
- 재검증(샘플 실행):
  - `is_anomaly=false`
  - `anomaly_score=0.0`
  - `events=[]`
- 결론:
  - sample 응답에서 점수/플래그/이벤트 정합성 이슈 해결


## 2026-02-19 | Step8: Real-case replay issue (Core7 sparse input)

### 재현 명령
- `python scripts\obd_engine\run_obd_anomaly_real_case.py --debug --csv "C:\Users\seona\Desktop\real_cases\2026-02-03_(2015_grandeur-hg_battery-case).csv" --vehicle-id "veh-real-battery" --trip-id "trip-real-battery" --sampling-hz 10`
- `python scripts\obd_engine\run_obd_anomaly_real_case.py --debug --csv "C:\Users\seona\Desktop\real_cases\2026-02-03_(2024_kona_engine-stall-case).csv" --vehicle-id "veh-real-stall" --trip-id "trip-real-stall" --sampling-hz 10`

### 관찰 결과
- 두 실차 파일 모두 `n_present=3`, `core_min_target=5` (Core7 중 3개만 매핑됨)
- 매핑된 feature: `engine_coolant_temp_c`, `engine_rpm`, `vehicle_speed_kmh`
- 미매핑 feature: `imap_kpa`, `intake_air_temp_c`, `maf_gps`, `throttle_pos_pct`
- 엔진 결과: `status=PROCESSED`, `score=0.0409`, `threshold=0.7959`, `is_anomaly=false`, `events=[]`

### 해석 (핵심)
- 현재 동작은 `IF_ONLY`로 수행되는 것은 맞음.
- 다만 입력 정보량이 `3/7`로 너무 낮아 IF 점수 분별력이 부족하고, 현 threshold 기준으로 anomaly를 올리지 못함.
- 즉 "IF 미동작" 문제가 아니라 "Core7 sparse 입력에서 탐지력 저하" 이슈임.

### 즉시 조치 항목 (슈팅)
1. `n_present < core_min_target` 시 `DATA_QUALITY_LOW` / `INSUFFICIENT_CORE_FEATURES` 이벤트 명시
2. 실차 CSV의 `OBD 모듈 전압(V)`를 `battery_voltage_v`로 매핑하여 electrical rule 경로 확보
3. 필요 시 `n_present=3` 전용 보조 모델/정책(별도 threshold) 분기 도입

### 조치 반영 (2026-02-19, Step8)
- 수정 파일:
  - `ai/app/services/obd_anomaly/core/scorers/engine_scorer.py`
  - `ai/app/services/obd_anomaly/obd_anomaly_service.py`
  - `ai/scripts/obd_engine/run_obd_anomaly_real_case.py`
- 반영 내용:
  - `INSUFFICIENT_CORE_FEATURES` 이벤트 생성 로직 추가 (`n_present < core_min_target`)
  - 엔진 품질 이벤트를 최종 `events[]`로 노출
  - 중복 이벤트(윈도우별 다건)를 단일 요약 이벤트 1건으로 집계
  - 실차 CSV 매핑에 `battery_voltage_v` 추가 (`OBD 모듈 전압(V)`)
- 기대 효과:
  - Core7 부족 사유를 응답에서 즉시 확인 가능
  - 배터리 저전압 케이스는 electrical rule 경로로 탐지 가능성 확보

### 전압 검증 결과 (real cases)
- 실행 명령(CMD):
  - `python -c "import pandas as pd; p=r'C:\Users\seona\Desktop\real_cases\2026-02-03_(2015_grandeur-hg_battery-case).csv'; s=pd.to_numeric(pd.read_csv(p)['OBD 모듈 전압 (V)'], errors='coerce').dropna(); print('battery-case -> min=', float(s.min()), 'max=', float(s.max()), 'avg=', float(s.mean()))"`
  - `python -c "import pandas as pd; p=r'C:\Users\seona\Desktop\real_cases\2026-02-03_(2024_kona_engine-stall-case).csv'; s=pd.to_numeric(pd.read_csv(p)['OBD 모듈 전압 (V)'], errors='coerce').dropna(); print('stall-case -> min=', float(s.min()), 'max=', float(s.max()), 'avg=', float(s.mean()))"`
- 결과:
  - battery-case: `min=12.5`, `max=14.7`, `avg=13.9454`
  - stall-case: `min=12.5`, `max=14.8`, `avg=14.1509`
- 해석:
  - electrical rule 임계값(`11.8V`) 미만 구간이 없어 `electrical.is_anomaly=false`는 정상 동작
  - 배터리/시동꺼짐 재현 탐지는 전압 룰만으로는 한계가 있어 추가 규칙(예: rpm/speed 급락 패턴) 필요

### 전압 룰 기준 개선 (2026-02-19)
- 수정 파일:
  - `ai/app/services/obd_anomaly/domains/electrical_rule.py`
- 변경 사항:
  - 단일 임계값(11.8V) 방식에서 `rpm` 구간 분리 룰로 개선
  - OFF/near-cranking (`rpm < 300`):
    - warning: `< 12.4V`
    - critical: `< 11.8V`
  - ON/charging (`rpm >= 300`):
    - warning: `min_on < 13.5V` 또는 `max_on > 14.8V`
    - critical: `min_on < 12.4V` 또는 `max_on >= 15.2V`
- 반영 의도:
  - 주행 ON 로그에 OFF 기준 전압(11.8V)만 적용되던 오해를 제거하고, 운행 상태별 정상 범위를 반영

### 이벤트 요약 처리 개선 (2026-02-19)
- 수정 파일:
  - `ai/app/services/obd_anomaly/obd_anomaly_service.py`
- 변경 사항:
  - 동일 이벤트(`type/domain/feature/severity`) 다건 발생 시 1건으로 요약 집계
  - 요약 이벤트 메시지에 `occurrences=N` 추가
  - 숫자 value는 그룹 내 최소값으로 대표값 기록
- 반영 의도:
  - 실차 재생 결과에서 `VOLTAGE_ON_WARNING_LOW` 다건 노이즈를 줄이고, 운영/시연 가독성 개선

### API 명세 보강 (2026-02-19)
- 수정 파일:
  - `docs/4.API 명세서.md`
- 반영 내용:
  - `3.3 Event Schema`에 `severity` 해석 문구 명시
    - `INFO`: 참고/품질 안내 (정상 확정 의미 아님)
    - `WARNING`: 주의 필요 이벤트
    - `CRITICAL`: 즉시 대응 필요 이벤트
- 목적:
  - 운영/백엔드/멘토 공유 시 `severity` 의미 오해 방지

### 스톨(시동 꺼짐) 의심 패턴 룰 추가 (2026-02-19)
- 수정 파일:
  - `ai/app/services/obd_anomaly/core/scorers/engine_scorer.py`
  - `ai/app/services/obd_anomaly/obd_anomaly_service.py`
- 반영 내용:
  - 엔진 도메인에 `ENGINE_STALL_SUSPECT` 이벤트 규칙 추가
    - 조건: `engine_rpm`이 고회전(>=1200)에서 저회전(<=400)으로 급락하면서 `vehicle_speed_kmh >= 20` 유지
  - 스톨 이벤트 발생 시 엔진 도메인 `is_anomaly=true` 처리
  - 엔진 이벤트 severity를 `INFO` 고정이 아닌 이벤트 원본값(`WARNING/CRITICAL/INFO`)으로 반영
- 목적:
  - Core7 결손(3/7) 상황에서도 실차 스톨 패턴을 룰 경로로 탐지 가능하도록 보완

### 스톨 케이스 재검증 결론 (2026-02-19)
- 검증 명령:
  - `python scripts\obd_engine\run_obd_anomaly_real_case.py --debug --csv "C:\Users\seona\Desktop\real_cases\2026-02-03_(2024_kona_engine-stall-case).csv" --vehicle-id "veh-real-stall" --trip-id "trip-real-stall" --sampling-hz 10`
  - `python -c "import pandas as pd; p=r'C:\Users\seona\Desktop\real_cases\2026-02-03_(2024_kona_engine-stall-case).csv'; df=pd.read_csv(p); c='엔진 RPM (rpm)'; t='time'; s=df[[t,c]].copy(); s[c]=pd.to_numeric(s[c],errors='coerce'); print(s.nsmallest(20,c).to_string(index=False))"`
- 결과:
  - 리플레이 기준 `is_anomaly=false` 유지
  - 스톨 규칙(`ENGINE_STALL_SUSPECT`) 미트리거
  - RPM 최소값 검증 결과, 최저 RPM 구간이 `1441` 수준으로 유지됨 (급락 신호 부재)
- 해석:
  - 현재 파일은 파일명과 달리 스톨 순간 센서 패턴(급락/저RPM)을 포함하지 않음
  - 규칙 미탐지는 로직 이슈가 아니라 입력 구간 미포함 이슈
- 다음 액션:
  - 스톨 직전~직후(최소 1~2분) 원본 구간 재추출 후 재검증

## 2026-02-23 | Step10: Synthetic Anomaly Benchmark (결과 반영)

### Step10 공통 범례 (먼저 읽기)
- `FPR`: 실제 정상 중 오탐 비율, **낮을수록 좋음**
- `Recall`: 실제 이상 중 탐지 비율, **높을수록 좋음**
- `Precision`: 탐지한 이상 중 실제 이상 비율, **높을수록 좋음**
- `F1`: Precision/Recall 균형 점수, **높을수록 좋음**
- `Accuracy`: 전체 정답률(보조 지표)

- `threshold(th)`: 이상 판정 점수 기준값
- `k_consecutive(k)`: 연속 초과 필요 횟수
- `warning(w)`: WARNING 경계
- `critical(c)`: CRITICAL 경계
### 7) Step10 1차 실행 결과 (Synthetic Eval)
- 실행 일시: 2026-02-23
- 입력: `ai/app/services/obd_anomaly/offline/datasets/vfinal/split/val_synthetic.jsonl`
- 샘플 수: 18 (normal=12, synthetic anomaly=6)
- 산출물:
  - `ai/app/services/obd_anomaly/offline/datasets/vfinal/synthetic_eval.json`
  - `ai/app/services/obd_anomaly/offline/datasets/vfinal/synthetic_eval_report.md`

- Confusion Matrix
  - TP: 5
  - FP: 9
  - TN: 3
  - FN: 1

- Metrics
  - Precision: 0.3571
  - Recall: 0.8333
  - F1: 0.5000
  - FPR: 0.7500
  - Accuracy: 0.4444

- 해석
  - 이상 검출률(Recall)은 높지만 정상 오탐(FP)이 커서 FPR이 높다.
  - 현재 정책은 synthetic anomaly에 민감한 대신 정상 억제가 약한 상태다.

### 8) Step10 정책 보수화 A/B/C 실험 결과 (Synthetic Eval)
- 공통 입력: `ai/app/services/obd_anomaly/offline/datasets/vfinal/split/val_synthetic.jsonl`
- 공통 샘플: 18 (normal=12, synthetic anomaly=6)

- Baseline (기존 정책)
  - 파라미터: `threshold=0.795981`, `k=2`, `warning=0.70`, `critical=0.85`
  - TP/FP/TN/FN: `5/9/3/1`
  - Precision/Recall/F1/FPR/Accuracy: `0.3571 / 0.8333 / 0.5000 / 0.7500 / 0.4444`

- 실험 A
  - 파라미터: `threshold=0.86`, `k=3`, `warning=0.80`, `critical=0.90`
  - TP/FP/TN/FN: `3/4/8/3`
  - Precision/Recall/F1/FPR/Accuracy: `0.4286 / 0.5000 / 0.4615 / 0.3333 / 0.6111`

- 실험 B
  - 파라미터: `threshold=0.90`, `k=3`, `warning=0.85`, `critical=0.93`
  - TP/FP/TN/FN: `0/0/12/6`
  - Precision/Recall/F1/FPR/Accuracy: `0.0000 / 0.0000 / 0.0000 / 0.0000 / 0.6667`
  - 해석: 과보수(미탐 과다)로 운영 부적합

- 실험 C
  - 파라미터: `threshold=0.88`, `k=3`, `warning=0.82`, `critical=0.91`
  - TP/FP/TN/FN: `3/3/9/3`
  - Precision/Recall/F1/FPR/Accuracy: `0.5000 / 0.5000 / 0.5000 / 0.2500 / 0.6667`
  - 해석: A 대비 오탐(FPR) 추가 개선, Recall 유지

- 중간 결론
  - B는 폐기.
  - A/C 중에서는 Step10 합성 벤치 기준 `C`가 균형이 더 좋음.

### 9) 운영 기준 (잠정)
#### 범례 (Metric Legend)
- TP: 실제 이상을 이상으로 탐지
- FP: 실제 정상을 이상으로 오탐
- TN: 실제 정상을 정상으로 탐지
- FN: 실제 이상을 정상으로 미탐

- Precision: 탐지한 이상 중 실제 이상의 비율 (높을수록 좋음)
- Recall: 실제 이상 중 탐지한 비율 (높을수록 좋음)
- F1: Precision/Recall 균형 점수 (높을수록 좋음)
- FPR: 실제 정상 중 오탐 비율 (낮을수록 좋음)
- Accuracy: 전체 예측 정확도 (높을수록 좋음)

- threshold(th): 이상 판정 점수 기준값
- k_consecutive(k): 연속 초과 필요 횟수
- warning(w): WARNING 경계
- critical(c): CRITICAL 경계

- 목표 지표
  - `FPR <= 0.20`
  - `Recall >= 0.60`
  - `F1 >= 0.55`
- 초기 운영/데모 허용 범위
  - `FPR <= 0.30` (임시 허용)
- 후보 선택 우선순위
  - 1순위: FPR
  - 2순위: Recall
  - 3순위: F1
- 비고
  - 현재 Step10 합성 벤치 결과는 운영 목표 대비 미달이며, 추가 정책 탐색(grid search) 진행 필요

### 10) 발표용 요약 (읽는 순서 + 비교표 + 결론)

#### 10-1) 판독 범례 (Legend)
- `FPR`(False Positive Rate): 실제 정상 중 오탐 비율, **낮을수록 좋음**
- `Recall`(재현율): 실제 이상 중 탐지 비율, **높을수록 좋음**
- `Precision`(정밀도): 탐지한 이상 중 실제 이상 비율, **높을수록 좋음**
- `F1`: Precision/Recall 균형 점수, **높을수록 좋음**
- `Accuracy`: 전체 정답률(보조 지표)

#### 10-2) 운영 판단 기준 (이번 발표 기준)
- 1순위: `FPR` (오탐 억제)
- 2순위: `Recall` (미탐 억제)
- 3순위: `F1` (균형)
- 운영 목표치: `FPR <= 0.20`, `Recall >= 0.60`, `F1 >= 0.55`

#### 10-3) 실험 결과 비교표
| 설정 | Precision | Recall | F1 | FPR | Accuracy | 운영 판단 |
|---|---:|---:|---:|---:|---:|---|
| Baseline | 0.3571 | 0.8333 | 0.5000 | 0.7500 | 0.4444 | 오탐 과다로 부적합 |
| A | 0.4286 | 0.5000 | 0.4615 | 0.3333 | 0.6111 | 개선됐지만 FPR 높음 |
| B | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.6667 | 미탐 100%로 제외 |
| C | 0.5000 | 0.5000 | 0.5000 | 0.2500 | 0.6667 | 현재 균형 후보 |
| Grid-best(자동) | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.6667 | 자동선정 한계로 제외 |

#### 10-4) 한 줄 해석
- `B`/`Grid-best`는 FPR만 보면 좋아 보이지만 Recall=0이라 실사용 불가.
- 현재는 `C`가 가장 균형적 후보이나, 운영 목표치 동시 충족은 아직 미달.
- 다음 단계는 실차 이상 라벨 확충 후 동일 지표로 재검증.
### 11) 실험값과 운영값 구분 (중요)
- 이번 Step10에서 A/B/C/grid-search로 바꾼 `threshold/k/warning/critical` 값은 **튜닝 실험값**이다.
- 목적: 성능(FPR/Recall/F1) 변화 추세를 확인하고 후보를 고르는 것.
- 의미: 실험값은 "비교용"이지, 자동으로 운영 정책으로 확정되지 않는다.

- 현재 결론
  - 실험 관점 후보: `C(th=0.88, k=3)`
  - 운영 확정값: 별도 승인/결정 전까지 기존 정책값 유지

- 운영 반영 원칙
  1. 실험으로 후보 선정
  2. 실차 라벨/시연 검증
  3. 팀 합의 후 정책 파일(`threshold_policy.json`)에 최종 반영

- 한 줄 요약
  - "지금 돌린 값들은 실험값이고, 운영값은 아직 확정 전"이 맞다.

## 2026-02-24 | Step12: Finalization Scope

### 목표
- Step11 결과를 운영 문서 기준으로 고정하고 발표/시연 준비를 마무리한다.

### 범위
- 운영값 vs 실험값 분리 명시
- synthetic benchmark 최종 후보/지표 고정
- API 스모크 로그/테스트 통과 로그 링크 정리
- 발표용 요약(지표/한계/다음 단계) 확정

### 완료 기준
- 문서 최종본 1개로 상태 설명 가능
- 지표표 1개 + 핵심 결론 3줄 확정
- 시연 절차/멘트 초안 확정

### Step12 API/평가 스모크 로그 (2026-02-24)
- Sample smoke (`ai/scripts/obd_engine/run_obd_anomaly_sample.py`)
  - 결과: `is_anomaly=true`, `engine.is_anomaly=true`
  - 이벤트: `ENGINE_HARD_LIMIT_ANOMALY`, `ENGINE_POLICY_ANOMALY`
- Real-case smoke (`2026-02-03_(2015_grandeur-hg_battery-case).csv`)
  - 결과: `is_anomaly=false`, `engine.is_anomaly=false`, `electrical.is_anomaly=false`
  - 이벤트: `VOLTAGE_ON_WARNING_LOW`(WARNING), `INSUFFICIENT_CORE_FEATURES`(INFO)
- Synthetic eval smoke
  - 실행: `python -m ai.app.services.obd_anomaly.offline.scripts.eval_synthetic_metrics ...`
  - 산출물:
    - `ai/app/services/obd_anomaly/offline/datasets/vfinal/synthetic_eval_step12.json`
    - `ai/app/services/obd_anomaly/offline/datasets/vfinal/synthetic_eval_step12_report.md`
  - 상태: `[OK] synthetic metrics evaluated`

## 발표용 1페이지 요약 (Step12)

### 1) 문제 정의
- 실차 이상 라벨이 충분하지 않아 supervised 방식의 직접 성능평가가 제한됨.
- 따라서 one-class(정상 중심) + 정책 기반 탐지로 운영 가능한 형태를 우선 구축함.

### 2) 접근 방법
- 엔진 도메인: Hybrid(IF + LSTM-AE)
- 입력 품질 저하 시: IF_ONLY fallback
- 정책 파라미터: threshold / k_consecutive / cooldown / severity
- synthetic anomaly를 생성해 정량 지표(FPR/Precision/Recall/F1)로 비교 평가

### 3) 핵심 결과
- Step11 제약 기반 grid 결과(조건: recall>=0.5):
  - 후보: `th=0.87, k=3, warning=0.78, critical=0.86`
  - 성능: Precision=0.50, Recall=0.50, F1=0.50, FPR=0.25
  - CM: TP=3, FP=3, TN=9, FN=3
- Top 후보 출력은 eligible pool 기준으로 정렬되도록 수정 완료.

### 4) 운영 해석
- FPR과 Recall은 임계값 기반 탐지 특성상 trade-off 관계.
- 현재 후보는 과탐/미탐 균형점이며, 운영 목표(예: FPR<=0.20, Recall>=0.60)에는 추가 검증이 필요함.
- 실험값과 운영값은 분리 관리하며, 운영 정책은 별도 승인 후 반영.

### 5) 한계 및 다음 단계
- 한계: 실고장 라벨 부족, synthetic 기반 검증 비중이 큼.
- 다음:
  1. 실차 라벨 확충
  2. 동일 파이프라인으로 재평가
  3. 운영 정책 최종 확정 및 API 반영

## Step12 LOCKED Final (발표/시연 기준 고정)

### 고정 후보(실험값)
- `threshold=0.87`, `k_consecutive=3`, `warning=0.78`, `critical=0.86`

### 고정 지표
- `Precision=0.50`
- `Recall=0.50`
- `F1=0.50`
- `FPR=0.25`
- `CM: TP=3, FP=3, TN=9, FN=3`

### 운영 해석
- 위 값은 Step11 synthetic benchmark 기준 **실험 후보값**이다.
- 운영 정책값(`threshold_policy.json`)은 별도 승인 전까지 기존 운영값 유지.
- 발표 시에는 “실험값과 운영값 분리 관리”를 명확히 설명한다.

### Step12 스모크 요약
- Sample: anomaly 경로 정상 동작 확인
- Real-case(battery): 엔진/전기 도메인 응답 및 이벤트 경로 확인
- Synthetic eval: 지표 산출 파일 생성 확인

### 남은 마감 작업(최소)
- 보드 카드 상태 최종 업데이트
- 최종 커밋/푸시
- 3분 리허설 1회
