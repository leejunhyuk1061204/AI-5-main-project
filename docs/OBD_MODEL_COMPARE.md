# LSTM(AE) vs IF Same-Condition Comparison

- condition: window_sec=60, stride_sec=30, threshold=0.795981228351593, k=2, cooldown=60
- compare_status: VALID

| mode | alarms_per_hour | alarms_ci95 | sample_f1 | sample_f1_ci95 | window_f1 | event_hit_rate | ttd_mean_sec | latency_mean_ms/window | latency_p95_ms/window |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| HYBRID | 1.720376 | [0.169877, 3.882955] | 0.625000 | [0.250000, 0.857143] | 0.303797 | 0.833333 | 115.220 | 71.510 | 92.016 |
| IF_ONLY | 2.842361 | [0.811665, 5.644480] | 0.500000 | [0.142857, 0.743750] | 0.045977 | 0.833333 | 1035.900 | 18.419 | 25.800 |
| AE_ONLY | 1.720376 | [0.167809, 3.833187] | 0.705882 | [0.400000, 0.900000] | 0.325000 | 1.000000 | 98.183 | 80.176 | 105.747 |

## Notes
- one-class normal setting: synthetic PR/F1 has generalization limits to real anomaly distribution
- bootstrap CI: sample-level resampling for sample_f1, normal-trip resampling for alarms_per_hour
