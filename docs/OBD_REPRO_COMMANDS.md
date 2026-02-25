# OBD Repro Commands

Run from repo root (`AI-5-main-project`).

```powershell
$env:PYTHONPATH='C:\Users\seona\Desktop\dev\AI-5-main-project'
C:\Users\seona\miniconda3\condabin\conda.bat run --no-capture-output -n ai5 python ai\app\services\obd_anomaly\offline\scripts\eval_model_modes_hardening.py --val-jsonl ai\app\services\obd_anomaly\offline\datasets\vfinal\split\val.jsonl --val-synthetic-jsonl ai\app\services\obd_anomaly\offline\datasets\vfinal\split\val_synthetic.jsonl --policy-json ai\app\services\obd_anomaly\models\artifacts\v1\threshold_policy.json --window-sec 60 --stride-sec 30 --boot-iters 500 --seed 42 --latency-runs 100 --latency-warmup 10 --out-compare-csv docs\OBD_MODEL_COMPARE.csv --out-compare-md docs\OBD_MODEL_COMPARE.md --out-sensitivity-csv docs\OBD_POLICY_SENSITIVITY.csv --out-latency-csv docs\OBD_LATENCY_BENCHMARK.csv
```
