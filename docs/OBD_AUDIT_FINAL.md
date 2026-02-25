# OBD Audit Final (4h Pack)

## Scope
- Audit date: 2026-02-24
- Goal: operational/presentation readiness check for OBD anomaly pipeline
- Constraint: no plan assumes new real anomaly collection

## Final Verdict
- Pipeline implementation: READY
- Operational quantification: READY (with one-class limitation noted)
- LSTM vs IF same-condition comparison: READY (same condition report generated)

## Code-based Pipeline (Implemented)
1. Request schema -> `ai/app/schemas/obd_anomaly_schema.py`
2. API route -> `ai/app/api/v1/routes/obd_anomaly_router.py`
3. Windowing -> `ai/app/services/obd_anomaly/windowing.py`
4. Quality guard (`coverage`, `max_gap`, `uniform_ts`, `mask`) ->
   - `ai/app/services/obd_anomaly/core/scorers/feature_alignment.py`
   - `ai/app/services/obd_anomaly/core/scorers/engine_scorer.py`
5. Engine scoring (IF + LSTM-AE hybrid with gate) ->
   - `ai/app/services/obd_anomaly/core/scorers/iforest_scorer.py`
   - `ai/app/services/obd_anomaly/core/scorers/lstm_ae_scorer.py`
   - `ai/app/services/obd_anomaly/core/scorers/engine_scorer.py`
6. Policy (`threshold`, `k_consecutive`, `cooldown`) ->
   - `ai/app/services/obd_anomaly/core/policy/threshold_policy.py`
   - `ai/app/services/obd_anomaly/models/artifacts/v1/threshold_policy.json`
7. Final response (`domains`, `events`) -> `ai/app/services/obd_anomaly/obd_anomaly_service.py`

## Grounded Metrics Snapshot
- Operating policy:
  - threshold: 0.795981228351593
  - k_consecutive: 2
  - cooldown_sec: 60
- Alarm frequency:
  - alarms_per_hour: 0.226986
- Hybrid score quantiles (policy eval):
  - q50: 0.256836
  - q90: 0.433243
  - q95: 0.632952
  - q99: 0.795981
- IF score quantiles (train report):
  - q50: 0.41828445767538397
  - q90: 0.5029150469170065
  - q95: 0.5439460241256392
  - q99: 0.595616468781157
- Synthetic benchmark candidate (policy experiment):
  - threshold=0.87, k=3, warning=0.78, critical=0.86
  - precision=0.50, recall=0.50, f1=0.50, fpr=0.25

## Same-Condition Comparison Status
- Executed with fixed condition:
  - window_sec=60, stride_sec=30
  - threshold=0.795981228351593, k=2, cooldown_sec=60
  - injection types: coolant_overheat, rpm_spike, stall_suspect, throttle_mismatch
- Outputs:
  - `docs/OBD_MODEL_COMPARE.md`
  - `docs/OBD_MODEL_COMPARE.csv`
  - `docs/OBD_POLICY_SENSITIVITY.csv`
  - `docs/OBD_LATENCY_BENCHMARK.csv`
  - `docs/OBD_REPRO_COMMANDS.md`
- Current result snapshot:
  - HYBRID alarms_per_hour: 1.720376 (CI95: 0.169877 ~ 3.882955)
  - IF_ONLY alarms_per_hour: 2.842361 (CI95: 0.811665 ~ 5.644480)
  - AE_ONLY alarms_per_hour: 1.720376 (CI95: 0.167809 ~ 3.833187)
  - HYBRID sample_f1: 0.625
  - IF_ONLY sample_f1: 0.5
  - AE_ONLY sample_f1: 0.705882
  - HYBRID gate rates (IF_ONLY/AE_ONLY/BOTH): 0.0 / 0.808323 / 0.191677
  - request-latency p99(ms): HYBRID=285.140, IF_ONLY=61.384, AE_ONLY=551.718

## Required Fixes (No Real-Anomaly Collection Assumption)
1. Completed: model-mode evaluator (IF_ONLY / AE_ONLY / HYBRID) under same window/stride/policy.
2. Completed: operational KPI table exported by mode (`OBD_MODEL_COMPARE.csv`).
3. Completed: latency smoke + request-level benchmark generated (`OBD_LATENCY_REPORT.json`, `OBD_LATENCY_BENCHMARK.csv`).
4. In progress: keep docs aligned to canonical API spec and mark experiment vs operation values.
5. Completed: replayable command bundle documented (`OBD_REPRO_COMMANDS.md`).
