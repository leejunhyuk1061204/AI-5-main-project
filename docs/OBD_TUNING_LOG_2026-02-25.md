# OBD 이상탐지 튜닝 기록 (2026-02-25)

## 1) 데이터셋 변경
- 파일: `ai/app/services/obd_anomaly/offline/datasets/vfinal/split/val_synthetic.jsonl`
- 조치: 기존 synthetic를 엔진-only 주입 버전으로 교체
- 근거 스크립트: `ai/app/services/obd_anomaly/offline/scripts/generate_synthetic_anomaly.py`
- 변경 내용: `vehicle_speed_kmh` 조작 제거 (rpm_spike / stall_suspect / throttle_mismatch)

## 2) 동일 조건 재평가 결과
- 조건: `window=60s`, `stride=30s`, `min_recall>=0.8`, `alarms/h<=2.0`

### HYBRID
- threshold=0.775, k=2, cooldown=180
- precision=0.5000, recall=1.0000, f1=0.6667, fpr=0.5000
- alarms_per_hour=1.0472
- TP/FP/TN/FN=6/6/6/0

### AE_ONLY
- threshold=0.800, k=2, cooldown=180
- precision=0.5000, recall=0.8333, f1=0.6250, fpr=0.4167
- alarms_per_hour=0.9724
- TP/FP/TN/FN=5/5/7/1

### IF_ONLY
- threshold=0.700, k=2, cooldown=180
- precision=0.3571, recall=0.8333, f1=0.5000, fpr=0.7500
- alarms_per_hour=1.7952
- TP/FP/TN/FN=5/9/3/1

## 3) 해석
- 오탐률(FPR) 기준: `AE_ONLY`가 최저
- 재현율 기준: `HYBRID`가 최고(1.0)
- IF_ONLY는 현 조건에서 오탐/알람량 불리

## 4) 결론
- 정책(threshold/k/cooldown) 튜닝만으로는 성능 개선 한계 확인
- 다음 단계는 모델/데이터 개선(재학습, 주입 시나리오 고도화) 필요

---

# OBD 학습 에폭 결정 기록 (2026-02-25)

## 목적
- Hybrid 운영 구조 유지 전제에서 LSTM-AE 학습 epoch를 `5`와 `10`으로 비교 후 최종 채택값 확정.

## 평가 조건
- 데이터: `val.jsonl` + 엔진-only `val_synthetic.jsonl`
- 비교 모드: `HYBRID`, `AE_ONLY`, `IF_ONLY`
- 공통 조건: `window=60s`, `stride=30s`, `min_recall>=0.8`, `alarms_per_hour<=2.0`
- 평가 스크립트: `ai/app/services/obd_anomaly/offline/scripts/optimize_policy_precision.py`

## 학습 실행 결과
- epoch=5 학습 시간: 약 48분 17초 (`ELAPSED 2897.30s`)
- epoch=10 학습 시간: 약 36분 44초 (`ELAPSED 2203.82s`)

## 핵심 비교 (Best policy 기준)

### HYBRID
- epoch=5: precision=0.5556, recall=0.8333, f1=0.6667, fpr=0.3333, alarms/h=0.7480
- epoch=10: precision=0.5556, recall=0.8333, f1=0.6667, fpr=0.3333, alarms/h=0.7480
- 판단: 동일

### AE_ONLY
- epoch=5: precision=0.5556, recall=0.8333, f1=0.6667, fpr=0.3333, alarms/h=0.7480
- epoch=10: precision=0.6250, recall=0.8333, f1=0.7143, fpr=0.2500, alarms/h=0.5984
- 판단: epoch=10 우세

### IF_ONLY
- epoch=5: precision=0.3571, recall=0.8333, f1=0.5000, fpr=0.7500, alarms/h=1.7952
- epoch=10: precision=0.3571, recall=0.8333, f1=0.5000, fpr=0.7500, alarms/h=1.7952
- 판단: 동일

## 최종 결정
- 운영 모드가 Hybrid로 확정되어 있으므로 `epoch=5` 채택.
- 근거: Hybrid 지표가 epoch 5/10에서 동일하며, 학습/반복 실험 효율을 고려해 더 가벼운 설정을 선택.

## 채택 기준값 (Hybrid)
- policy: threshold=0.85, k_consecutive=2, cooldown_sec=180
- metrics: precision=0.5556, recall=0.8333, f1=0.6667, fpr=0.3333, alarms_per_hour=0.7480

