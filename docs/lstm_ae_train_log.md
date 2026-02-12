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

## Local (#2 Failure Detection) — Data Prep Only

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

## Local (#3 Engine Health) — Data Prep Only

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
