# Latency Smoke Note

Status: MEASURED

Measured environment:
- conda env: `ai5`
- python: `3.10.19`
- runtime: local CPU session
- command path: `conda run -n ai5 ...`

Measured input:
- source: `ai/app/services/obd_anomaly/offline/datasets/vfinal/split/val_synthetic.jsonl` first sample
- domain: engine only
- request options: `window_sec=60`, `stride_sec=30`, `return=summary`
- request windows: 3

Latency result (per request):
- runs: 8 (after warmup 1)
- mean_ms: 50.5485749890795
- p95_ms: 56.060099974274635
- min_ms: 39.91160006262362
- max_ms: 57.83730000257492

Output file:
- `docs/OBD_LATENCY_REPORT.json`

Caution:
- This is a smoke-level local measurement, not production SLA.
- Model load warning observed (`torch.load(weights_only=False)` future warning).
