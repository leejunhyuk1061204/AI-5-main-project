# Engine Hybrid (Stat One-Class + LSTM-AE) Training Log

이 문서는 엔진 anomaly hybrid 실험 로그이며, legacy LSTM-AE-only 기록은 하단에 보관.
앞으로 신규 실험 기록은 `Hybrid Engine Runs` 섹션을 메인으로 사용한다.

## Section Guide
아래는 각 섹션이 의미하는 내용과 하위 항목 설명이다.

1) `Run Info`
- 이번 실행의 데이터/전처리 조건을 기록한다.
- `Date`: 실행 날짜/시간
- `Env`: 실행 환경(Local/RunPod)
- `Dataset`: 학습에 사용한 데이터셋
- `Split`: train/val/test 분할 방식(누수 방지 포함)
- `window_sec`: 윈도우 길이(초)
- `stride_sec`: 윈도우 이동 간격(초)
- `sampling_hz`: 샘플링 주기(Hz)
- `normalize`: 정규화 방식(zscore 등)
- `min_coverage`: 결측 허용 기준
- `fill_method`: 결측 보정 방식
- `Schema`: core feature 스키마 버전/구성

2) `Training Params`
- 학습 하이퍼파라미터를 기록한다.
- `epochs`: 학습 반복 횟수
- `batch_size`: 한 번에 학습하는 샘플 수
- `lr`: 학습률
- `device`: `cpu` 또는 `cuda(gpu)`
- IF(Stat One-Class)는 epoch 대신 모델 파라미터(`n_estimators` 등)를 기록한다.

3) `Loss Log`
- 학습 과정의 손실값 변화를 기록한다.
- `epoch 01~N`: 각 epoch 종료 시점의 loss
- 추세(감소/정체/진동)를 통해 학습 안정성을 확인한다.

4) `Output`
- 실행 결과물을 기록한다.
- `model_path`: 저장 모델 파일 위치
- `scaler_path`: 스케일러 파일 위치
- `report_path`: 실행 리포트 파일 위치
- `time`/`elapsed_sec`: 총 소요 시간
- `notes`: 특이사항(중단, 재시작, 경고 등)

5) `Policy` / `Eval` (vFinal)
- 정책 확정에 필요한 검증 결과를 기록한다.
- `threshold`, `k_consecutive`, `cooldown` 확정값
- 정상 점수 분포(quantiles), 시간당 알람 빈도(alarms/hour)
- top_signals 예시와 해석

6) `Training Progress` (vFinal)
- IF / LSTM-AE / Policy 단계별 완료 상태를 한눈에 관리한다.
- 각 단계 산출물 경로와 핵심 수치를 요약한다.

## Hybrid Engine Runs

### Run: <RUN_ID>
#### Run Info
#### One-Class Data Policy
- normal_labels: normal,frei,stau
- train_filter: is_normal=true only
- excluded_from_train: is_normal=false (val/test/replay only)

- Date:
- Env: Local | RunPod
- Dataset: OBD normal | OBD normal+frei+stau | ...
- Split: trip/session-based (train/val/test), leakage-prevention: enabled
- window_sec:
- stride_sec:
- sampling_hz:
- normalize: zscore (fit on train normal)
- fill_method: ffill
- min_coverage:
- Schema: core10-v1 (list the 10 features)
- Missing feature handling: align + mask; AE SKIPPED rules: <min_features>, <min_coverage>

#### Model(s)
- Stat One-Class:
  - method: IsolationForest | RobustZ
  - input: window summary stats + coverage
- LSTM-AE:
  - architecture: (brief)
  - input: (T,F) aligned core features
- Ensemble:
  - final_score = w1*score_stat + w2*score_ae
  - weights: w1=, w2=
  - fallback: if AE SKIPPED => final_score=score_stat

#### Training Params
- Stat One-Class:
  - params:
- LSTM-AE:
  - epochs:
  - batch_size:
  - lr:
  - device:

#### Loss Log (LSTM-AE)
- epoch 01:
...

#### Eval
- Threshold selection: method (val quantile / target alarm rate / etc)
- threshold T:
- K consecutive:
- cooldown:
- Normal test metrics:
  - alarm/hour:
  - false alarm rate:
  - score distribution notes:
- (optional) ROC-AUC:
- (optional) PR-AUC:

#### Policy
- severity definition:
- event generation rules (if any):

#### Artifacts
- schema_core.json:
- scaler.json:
- iforest.pkl (or stat params file):
- lstm_ae.pt:
- threshold_policy.json:
- model_version:
- schema_version:
- policy_version:

#### Notes / Next Actions
- notes:
- next:

---

### Run: Hybrid Run (OBD normal+frei+stau)
#### Run Info
#### One-Class Data Policy
- normal_labels: normal,frei,stau
- train_filter: is_normal=true only
- excluded_from_train: is_normal=false (val/test/replay only)

- Date:
- Env: Local | RunPod
- Dataset: OBD normal+frei+stau
- Split: trip/session-based (train/val/test), leakage-prevention: enabled
- Train trips:
- Val trips:
- Test trips:
- window_sec:
- stride_sec:
- sampling_hz:
- normalize: zscore (fit on train normal)
- fill_method: ffill
- min_coverage:
- Schema: core10-v1 (list the 10 features)
- Missing feature handling: align + mask; AE SKIPPED rules: <min_features>, <min_coverage>

#### Model(s)
- Stat One-Class:
  - method: IsolationForest | RobustZ
  - input: window summary stats + coverage
- LSTM-AE:
  - architecture: (brief)
  - input: (T,F) aligned core features
- Ensemble:
  - final_score = w1*score_stat + w2*score_ae
  - weights: w1=, w2=
  - fallback: if AE SKIPPED => final_score=score_stat

#### Training Params
- Stat One-Class:
  - params:
- LSTM-AE:
  - epochs:
  - batch_size:
  - lr:
  - device:

#### Loss Log (LSTM-AE)
- epoch 01:
...

---

### Run: vFinal Step6 - Data Prep (pre-train)
#### Run Info
#### One-Class Data Policy
- normal_labels: normal,frei,stau
- train_filter: is_normal=true only
- excluded_from_train: is_normal=false (val/test/replay only)

- Date: 2026-02-18
- Env: Local
- Dataset: OBD normal+frei+stau (raw csv)
- Split: trip/session-based (train/val/test), leakage-prevention: enabled
- rows_total: 2732486
- trips_total: 81
- Train trips: 56
- Val trips: 12
- Test trips: 13
- window_sec: 60
- stride_sec: 30
- sampling_hz: 10
- normalize: pending (fit on train only)
- fill_method: pending
- min_coverage: pending
- Schema: core7-v1
- Missing feature handling: align + mask; AE SKIPPED rules: policy 기반

#### Training Progress
- Stat One-Class (IsolationForest):
  - status: done
  - windows: 6332
  - model_path: ai/app/services/obd_anomaly/models/artifacts/v1/iforest.pkl
  - report_path: ai/app/services/obd_anomaly/offline/datasets/vfinal/iforest_report.json
- LSTM-AE:
  - status: done
  - start_time: 2026-02-19 10:50:56
  - end_time: 2026-02-19 11:20:44
  - elapsed_sec: 1788.76
  - final_loss: 0.360000
  - model_path: ai/app/services/obd_anomaly/models/artifacts/v1/lstm_ae.pt
  - scaler_path: ai/app/services/obd_anomaly/models/artifacts/v1/scaler.json
  - report_path: ai/app/services/obd_anomaly/offline/datasets/vfinal/lstm_ae_report.json
- Policy Eval:
  - status: done
  - threshold: 0.795981228351593
  - k_consecutive: 2
  - cooldown_sec: 60
  - alarms_per_hour (val): 0.226986
  - policy_path: ai/app/services/obd_anomaly/models/artifacts/v1/threshold_policy.json
  - report_path: ai/app/services/obd_anomaly/offline/datasets/vfinal/policy_report.md

#### Notes / Next Actions
- notes: data prep 완료 후 IF 학습까지 완료. 현재 LSTM-AE 학습 대기 상태.
- next: LSTM-AE 학습 -> policy(eval) 순으로 실행.

---

### Run: vFinal Step7 - LSTM-AE Train (template)
#### Run Info
#### One-Class Data Policy
- normal_labels: normal,frei,stau
- train_filter: is_normal=true only
- excluded_from_train: is_normal=false (val/test/replay only)

- Date: 2026-02-19
- Env: Local (ai5)
- Dataset: OBD normal+frei+stau
- Split: trip/session-based (train/val/test), leakage-prevention: enabled
- Train trips: 56
- Val trips: 12
- Test trips: 13
- window_sec: 60
- stride_sec: 30
- sampling_hz: 10
- normalize: zscore (fit on train)
- fill_method: impute_nan(mean per feature in window)
- min_coverage: n/a (script-level filter 없음)
- Schema: core7-v1

#### Training Params
- epochs: 10
- batch_size: 32
- lr: 1e-3
- device: cpu | cuda

#### Runtime (fill after run)
- start_time: 2026-02-19 10:50:56
- end_time: 2026-02-19 11:20:44
- elapsed_sec: 1788.76

#### Loss Log (fill after run)
- epoch 01: 0.523741
- epoch 02: 0.398712
- epoch 03: 0.392678
- epoch 04: 0.378054
- epoch 05: 0.379739
- epoch 06: 0.373941
- epoch 07: 0.370592
- epoch 08: 0.368786
- epoch 09: 0.370557
- epoch 10: 0.360000

#### Output (fill after run)
- model_path: ai/app/services/obd_anomaly/models/artifacts/v1/lstm_ae.pt
- scaler_path: ai/app/services/obd_anomaly/models/artifacts/v1/scaler.json
- report_path: ai/app/services/obd_anomaly/offline/datasets/vfinal/lstm_ae_report.json
- notes: loss가 10 epoch 동안 전반적으로 감소(0.523741 -> 0.360000)하여 정상 패턴 복원 학습이 안정적으로 진행됨.

#### Next
- 통합 테스트 실행 및 API 엔진 응답 검증

#### Eval
- Threshold selection: method (val quantile / target alarm rate / etc)
- threshold T:
- K consecutive:
- cooldown:
- Normal test metrics:
  - alarm/hour:
  - false alarm rate:
  - score distribution notes:
- (optional) ROC-AUC:
- (optional) PR-AUC:

#### Policy
- severity definition:
- event generation rules (if any):

#### Artifacts
- schema_core.json:
- scaler.json:
- iforest.pkl (or stat params file):
- lstm_ae.pt:
- threshold_policy.json:
- model_version:
- schema_version:
- policy_version:

#### Notes / Next Actions
- notes:
- next:

---

## RunPod Runs (Training/Inference)

### RunPod: <RUN_ID>
- Image/Repo commit:
- RunPod instance type:
- GPU:
- vCPU/RAM:
- Data source (S3):
- Data upload location (S3 path):
- Output artifacts (S3 or repo path):
- Command:
- Time: start/end, duration
- Notes:

---

## Real-car Final Test (No Training)

### Run: Hybrid Eval on Real-car cases (학습X, 최종 테스트)
#### Run Info
- Date:
- Env: Local | RunPod
- Dataset: real-car labeled/unlabeled cases
- Split: no training (final test only)
- Schema: core10-v1 (list the 10 features)
- Missing feature handling: align + mask; AE SKIPPED rules: <min_features>, <min_coverage>

#### Model(s)
- Stat One-Class:
  - method: IsolationForest | RobustZ
- LSTM-AE:
  - model_version:
- Ensemble:
  - final_score = w1*score_stat + w2*score_ae
  - fallback: if AE SKIPPED => final_score=score_stat

#### Eval
- Threshold selection: fixed from validation (no re-fit)
- threshold T:
- K consecutive:
- cooldown:
- Case metrics:
  - detection latency:
  - false alarms outside anomaly window:
  - score distribution notes:

#### Policy
- severity definition:
- event generation rules (if any):

#### Artifacts
- threshold_policy.json:
- model_version:
- schema_version:
- policy_version:

#### Notes / Next Actions
- notes:
- next:

### Case: Battery Discharge
- data_source:
- expected anomaly window:
- observed anomaly_score:
- notes:

### Case: Engine Stall
- data_source:
- expected anomaly window:
- observed anomaly_score:
- notes:

---

## Optional Kaggle Bench (Not used for MVP)
- Use for MVP? [ ] Yes  [x] No
- reason:
- results (if executed):

### Run: Optional Kaggle Bench (참고용, MVP에는 미사용)
#### Run Info
- Date:
- Env: Local | RunPod
- Dataset: Kaggle benchmark
- Split: trip/session-equivalent or source-provided split, leakage-prevention: enabled
- window_sec:
- stride_sec:
- sampling_hz:
- normalize: zscore (fit on train normal)
- fill_method:
- min_coverage:
- Schema: core10-v1 mapping + fallback
- Missing feature handling: align + mask; AE SKIPPED rules: <min_features>, <min_coverage>

#### Model(s)
- Stat One-Class:
  - method: IsolationForest | RobustZ
- LSTM-AE:
  - architecture: (brief)
- Ensemble:
  - final_score = w1*score_stat + w2*score_ae
  - fallback: if AE SKIPPED => final_score=score_stat

#### Training Params
- Stat One-Class:
  - params:
- LSTM-AE:
  - epochs:
  - batch_size:
  - lr:
  - device:

#### Loss Log (LSTM-AE)
- epoch 01:
...

#### Eval
- Threshold selection: method (val quantile / target alarm rate / etc)
- threshold T:
- K consecutive:
- cooldown:
- Normal test metrics:
  - alarm/hour:
  - false alarm rate:
  - score distribution notes:
- (optional) ROC-AUC:
- (optional) PR-AUC:

#### Policy
- severity definition:
- event generation rules (if any):

#### Artifacts
- schema_core.json:
- scaler.json:
- iforest.pkl (or stat params file):
- lstm_ae.pt:
- threshold_policy.json:
- model_version:
- schema_version:
- policy_version:

#### Notes / Next Actions
- notes:
- next:

---

## Legacy: LSTM-AE-only Runs (kept for history)

# LSTM-AE Training Log

<!--
사용 방법:
- Local/RunPod 중 실제 사용한 환경 섹션만 기록합니다.
- Training Params는 실행 전에, Loss/Output은 실행 후 채웁니다.
-->

<!--
섹션 의미:
- Run Info: 이번 실행의 데이터/전처리 조건 기록
- Training Params: 학습 하이퍼파라미터 기록
- Loss Log: epoch별 손실값 기록
- Output: 결과 모델 경로/소요시간/특이사항 기록
- Eval: 검증 결과(AUC/threshold 등) 기록
-->

<!--
실차 데이터 관련:
- 실차 데이터는 별도 확보된 2개 케이스(배터리 방전/시동 꺼짐)이며, 전처리 JSONL만 S3에 업로드한다.
-->

## Local (OBD)

### Run Info (Baseline, no normalization)
- Date: 2026-02-07 22:05:01
- Model: LSTM-AE
- Dataset: OBD normal
- Features: 10 (engine core)
- window_sec: 60
- stride_sec: 20
- sampling_hz: 10
- normalize: zscore
- min_coverage: 0.9
- fill_method: ffill
- resample: none

### Training Params (Baseline)
- epochs: 10
- batch_size: 16
- lr: 1e-3
- device: cpu

### Loss Log (Baseline)
- epoch 01: 0.491319
- epoch 02: 0.426928
- epoch 03: 0.410614
- epoch 04: 0.403561
- epoch 05: 0.408622
- epoch 06: 0.400010
- epoch 07: 0.405023
- epoch 08: 0.393583
- epoch 09: 0.385183
- epoch 10: 0.382424

### Output (Baseline)
- model_path: ai/weights/runs/20260207_220501/lstm_ae.pt
- time: 8238.8s (137m 19s)
- notes: loss가 0.49 → 0.38로 감소하여 정상 패턴 복원 오차가 줄고 있음. 중반(5~7 epoch)에서 소폭 흔들림 있으나 이후 다시 감소해 수렴 경향 확인됨. 검증 세트가 없으므로 과적합 여부는 아직 판단 불가하며, 정상/이상 분포 분리 확인이 필요함.

---

## Local (#1 EFD)

### S3 Upload (Kaggle EFD JSONL)
- date: 2026-02-09
- bucket: ai-5-main-project-car-bom
- path: dataset/obd/jsonl/kaggle_efd/20260209/
- files:
  - normal.jsonl (1.2MB)
  - fault.jsonl (632.5KB)
- method: AWS Console (manual)
- script: ai/scripts/obd_engine/upload_jsonl_to_s3.py

### Run Info
- Date: 2026-02-09 10:49:49
- Model: LSTM-AE (EFD)
- Dataset: Kaggle EFD
- Features: 11
- window_sec: 60
- stride_sec: 60
- sampling_hz: 1
- normalize: none
- min_coverage: n/a
- fill_method: n/a
- resample: none

### Training Params
- epochs: 10
- batch_size: 32
- lr: 1e-3
- device: cpu

### Loss Log
- epoch 01: 917187.979167
- epoch 02: 918329.895833
- epoch 03: 917617.416667
- epoch 04: 916286.687500
- epoch 05: 916619.416667
- epoch 06: 917253.916667
- epoch 07: 915194.770833
- epoch 08: 914262.229167
- epoch 09: 913480.250000
- epoch 10: 911960.833333

### Output
- model_path: ai/weights/efd/runs/20260209_104949/lstm_ae_efd.pt
- time: 3.3s (0m 3s)
- notes: EFD 원시 스케일로 학습되어 loss 절대값이 큼(정규화 미적용). 분포 비교/AUC로 성능 확인 필요.

### EFD Eval (Baseline, no normalization)
- AUC: 0.4770
- threshold (q=0.99): 1,132,182.75
- notes: 정규화 미적용 상태에서 정상/고장 분리 성능이 낮음 → 정규화 적용 후 재학습/재평가 필요.

---

### Normalized (zscore) 재학습

### Run Info (Normalized, zscore)
- Date: 2026-02-09 12:04:30
- Model: LSTM-AE (EFD)
- Dataset: Kaggle EFD
- Features: 11
- window_sec: 60
- stride_sec: 60
- sampling_hz: 1
- normalize: zscore (normal 기준)
- min_coverage: n/a
- fill_method: n/a
- resample: none

### Training Params (Normalized)
- epochs: 10
- batch_size: 32
- lr: 1e-3
- device: cpu

### Loss Log (Normalized)
- epoch 01: 1.003659
- epoch 02: 1.001054
- epoch 03: 0.999720
- epoch 04: 1.000817
- epoch 05: 1.000395
- epoch 06: 0.999602
- epoch 07: 0.999458
- epoch 08: 0.999037
- epoch 09: 0.999239
- epoch 10: 0.999234

### Output (Normalized)
- model_path: ai/weights/efd/runs/20260209_120430/lstm_ae_efd.pt
- scaler_path: ai/weights/efd/scaler_efd.json
- time: 3.0s (0m 3s)
- notes: 정규화 적용으로 loss 스케일이 안정화됨. 다만 분리 성능은 AUC 기준으로 추가 개선 필요.

### EFD Eval (Normalized, zscore)
- AUC: 0.4966
- threshold (q=0.99): 1.067330
- notes: 정규화 후 AUC가 소폭 개선되었으나 여전히 분리 성능이 낮음 → 채널/전처리/모델 구조 재검토 필요.

---

## Local (#2 Failure Detection) - Data Prep Only

### Data Prep
- source_csv: ai/app/services/obd_anomaly/offline/raw/kaggle_efd2/engine_failure_dataset.csv
- output_jsonl: ai/app/services/obd_anomaly/offline/datasets/kaggle_efd2/labeled.jsonl
- label_col: Fault_Condition (values: 0,1,2,3)
- channels: Temperature (∑C), RPM, Fuel_Efficiency, Vibration_X, Vibration_Y, Vibration_Z, Torque, Power_Output (kW)
- sampling_hz: 1
- window_sec: 60
- stride_sec: 60
- rows_total: 1000
- notes: 결측/중복 0% 확인. 라벨 포함 JSONL로 변환 완료.

---

## Local (#3 Engine Health) - Data Prep Only

### Data Prep
- source_csv: ai/app/services/obd_anomaly/offline/raw/kaggle_engine_health/engine_data.csv
- output_jsonl: ai/app/services/obd_anomaly/offline/datasets/kaggle_engine_health/labeled.jsonl
- label_col: Engine Condition (values: 0,1)
- channels: Engine rpm, Lub oil pressure, Fuel pressure, Coolant pressure, lub oil temp, Coolant temp
- sampling_hz: 1
- window_sec: 60
- stride_sec: 60
- rows_total: 19535
- notes: 결측/중복 0% 확인. 라벨 포함 JSONL로 변환 완료.

