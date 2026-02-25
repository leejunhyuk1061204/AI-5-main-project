# OBD Metrics Register (Meaningful Numbers)

## 1) Operation Policy (Current)
- threshold: 0.795981228351593
- k_consecutive: 2
- cooldown_sec: 60
- severity.warning: 0.70
- severity.critical: 0.85
- gating.ae_min_coverage: 0.80
- gating.ae_max_gap: 3
- gating.both_min_coverage: 0.60
- gating.w_coverage_c0: 0.60
- gating.w_coverage_c1: 0.95
- ae_score.error_min: 0.20534303784370422
- ae_score.error_max: 4.375852990150459
- source: `ai/app/services/obd_anomaly/models/artifacts/v1/threshold_policy.json`

## 2) Hybrid Policy Eval (Val-Normal)
- q50: 0.256836
- q90: 0.433243
- q95: 0.632952
- q99: 0.795981
- alarms_per_hour: 0.226986
- source: `ai/app/services/obd_anomaly/offline/datasets/vfinal/policy_report.md`

## 3) IF Train Report
- windows: 6332
- features: 42
- q50: 0.41828445767538397
- q90: 0.5029150469170065
- q95: 0.5439460241256392
- q99: 0.595616468781157
- source: `ai/app/services/obd_anomaly/offline/datasets/vfinal/iforest_report.json`

## 4) LSTM-AE Train Report
- windows: 6332
- features: 7
- epochs: 10
- final_loss: 0.36000039217749025
- loss_curve_start: 0.5237413857019309
- loss_curve_end: 0.36000039217749025
- source: `ai/app/services/obd_anomaly/offline/datasets/vfinal/lstm_ae_report.json`

## 5) Synthetic Eval (Sample-Level)
- Baseline (`synthetic_eval.json`)
  - TP/FP/TN/FN: 5/9/3/1
  - precision/recall/f1/fpr/accuracy: 0.3571428571 / 0.8333333333 / 0.5 / 0.75 / 0.4444444444
- A (`synthetic_eval_A.json`)
  - TP/FP/TN/FN: 3/4/8/3
  - precision/recall/f1/fpr/accuracy: 0.4285714286 / 0.5 / 0.4615384615 / 0.3333333333 / 0.6111111111
- B (`synthetic_eval_B.json`)
  - TP/FP/TN/FN: 0/0/12/6
  - precision/recall/f1/fpr/accuracy: 0 / 0 / 0 / 0 / 0.6666666667
- C (`synthetic_eval_C.json`)
  - TP/FP/TN/FN: 3/3/9/3
  - precision/recall/f1/fpr/accuracy: 0.5 / 0.5 / 0.5 / 0.25 / 0.6666666667

## 6) Synthetic Eval (Multi-Granularity)
- sample
  - evaluated_units: 18
  - f1/fpr: 0.5 / 0.75
- window_60s
  - evaluated_units: 1251
  - f1/fpr: 0 / 0
- chunk_900s
  - evaluated_units: 73
  - f1/fpr: 0.1052631579 / 0.1791044776
- source: `ai/app/services/obd_anomaly/offline/datasets/vfinal/synthetic_eval_granularity.json`

## 7) Synthetic Grid Search (Best Candidate)
- threshold: 0.87
- k_consecutive: 3
- warning: 0.78
- critical: 0.86
- TP/FP/TN/FN: 3/3/9/3
- precision/recall/f1/fpr/accuracy: 0.5 / 0.5 / 0.5 / 0.25 / 0.6666666667
- num_runs: 112
- eligible_count: 80
- source: `ai/app/services/obd_anomaly/offline/datasets/vfinal/synthetic_grid_search.json`

## 8) Inference Latency (Measured)
- environment: conda env `ai5` (Python 3.10.19), local CPU session
- input: first sample of `val_synthetic.jsonl`, engine domain only, window=60, stride=30
- runs: 8 (after 1 warmup)
- mean_ms_per_request: 50.5485749891
- p95_ms_per_request: 56.0600999743
- min_ms_per_request: 39.9116000626
- max_ms_per_request: 57.8373000026
- request_num_windows: 3
- source: `docs/OBD_LATENCY_REPORT.json`

## 9) Important Limitation (Must State)
- `val/test` are normal-only(one-class) in main setting, so PR/F1 from synthetic cannot be directly generalized to real anomaly distribution.
- source: `docs/obd-anomaly-progress.md`

## 10) LSTM(AE) vs IF Same-Condition (Completed)
- fixed condition
  - window_sec: 60
  - stride_sec: 30
  - threshold: 0.795981228351593
  - k_consecutive: 2
  - cooldown_sec: 60
  - injection types: coolant_overheat, rpm_spike, stall_suspect, throttle_mismatch (4 types)
- HYBRID
  - alarms_per_hour: 1.7203764882 (CI95: 0.169877 ~ 3.882955)
  - alert_rate_per_window: 0.0384615385
  - sample_f1 / window_f1: 0.625 / 0.3037974684
  - sample_f1 CI95: 0.25 ~ 0.857143
  - event_hit_rate: 0.8333333333
  - ttd_mean_sec: 115.22
  - latency mean/p95 (ms per window): 71.510 / 92.016
  - gate_if_only/ae_only/both: 0.0 / 0.8083228247 / 0.1916771753
- IF_ONLY
  - alarms_per_hour: 2.8423611544 (CI95: 0.811665 ~ 5.644480)
  - alert_rate_per_window: 0.0523329130
  - sample_f1 / window_f1: 0.5 / 0.0459770115
  - sample_f1 CI95: 0.142857 ~ 0.74375
  - event_hit_rate: 0.8333333333
  - ttd_mean_sec: 1035.9
  - latency mean/p95 (ms per window): 18.653 / 25.835
  - gate_if_only/ae_only/both: 1.0 / 0.0 / 0.0
- AE_ONLY
  - alarms_per_hour: 1.7203764882 (CI95: 0.167809 ~ 3.833187)
  - alert_rate_per_window: 0.0390920555
  - sample_f1 / window_f1: 0.7058823529 / 0.325
  - sample_f1 CI95: 0.4 ~ 0.9
  - event_hit_rate: 1.0
  - ttd_mean_sec: 98.183
  - latency mean/p95 (ms per window): 80.176 / 105.747
  - gate_if_only/ae_only/both: 0.0 / 1.0 / 0.0
- compare_status: VALID
- source: `docs/OBD_MODEL_COMPARE.md`, `docs/OBD_MODEL_COMPARE.csv`

## 11) Timestamp Unit Note (Important)
- For 10Hz data, integer `t` with `timestamp_unit=s` cannot represent 0.1s intervals exactly.
- In comparison/evaluation, request timestamps were encoded as integer milliseconds (`timestamp_unit=ms`) to satisfy uniform_ts checks.
- source: `ai/app/services/obd_anomaly/core/scorers/feature_alignment.py`, `ai/app/schemas/obd_anomaly_schema.py`, `ai/app/services/obd_anomaly/offline/scripts/eval_model_modes_hardening.py`

## 12) Latency Benchmark (Request-level, n=100)
- benchmark condition: first synthetic sample trimmed to 90 seconds, window=60, stride=30
- HYBRID request latency (ms): p50=189.379, p95=215.594, p99=285.140, mean=194.245
- IF_ONLY request latency (ms): p50=39.215, p95=56.168, p99=61.384, mean=40.997
- AE_ONLY request latency (ms): p50=213.326, p95=347.415, p99=551.718, mean=229.470
- source: `docs/OBD_LATENCY_BENCHMARK.csv`

## 13) Sensitivity Grid (Policy)
- evaluated grid: threshold in {base-0.05, base, base+0.05}, k in {1,2,3}, cooldown in {30,60,120}
- total runs: 81 (= 3 modes x 27 policies)
- source: `docs/OBD_POLICY_SENSITIVITY.csv`
