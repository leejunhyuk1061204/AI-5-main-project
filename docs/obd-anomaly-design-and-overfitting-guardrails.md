# OBD Anomaly vFinal: 설계 및 과적합 방어 기준

## 1) 현재 설계 요약
- 구조: `Hybrid ML + Quality Gating + Policy`
- Hybrid ML:
  - `LSTM-AE`: 시계열 복원 오차 기반 이상 점수
  - `IsolationForest`: 통계 요약 기반 이상 점수
- Quality Gating:
  - 품질 지표(`n_present`, `coverage`, `max_gap`, `uniform_ts`)를 먼저 계산
  - `AE_ONLY` / `IF_ONLY` / `BOTH` 선택
  - 입력 품질이 나쁘면 자동으로 IF 중심 fallback
- Policy:
  - `threshold`, `k_consecutive`, `cooldown_sec`, `severity` 적용
  - 운영 알람은 정책 기준으로 확정

## 2) 왜 과적합이 걱정되는가
- 시계열 데이터는 같은 주행 구간이 train/test에 섞이면 성능이 과대평가되기 쉬움
- LSTM-AE는 정상 패턴 복원에 민감해, 분할/튜닝 방식이 잘못되면 실제 환경에서 성능 저하 가능

## 3) 현재 적용된 과적합 방어 장치
- Group split: `trip_id`(또는 `session_id`) 단위 분할
  - 같은 주행이 train/val/test로 찢어지지 않음
- 분할 비율: `train/val/test = 70/15/15`
- One-class 학습 원칙:
  - `is_normal=true`만 학습
  - `normal/frei/stau`를 정상으로 간주
- 정책값은 train이 아니라 `val`에서 확정
- 저품질 데이터는 IF fallback으로 운영 안정성 확보

## 4) 성능 확인 기준 (운영 관점)
- 정상 데이터(오탐 관리):
  - `alarms/hour`가 목표 범위 이내인지 확인
- 이상 데이터(탐지력):
  - 실차 케이스(배터리 방전/시동 꺼짐)에서 탐지 성공 여부
  - 탐지 지연 시간(`detection latency`) 확인
- 응답 정합성:
  - `is_anomaly`, `anomaly_score`, `events`가 모순 없이 일치해야 함

## 5) 추가 방어 계획 (필요 시 적용)
- Early stopping:
  - val 지표 기반으로 LSTM epoch 자동 조기 종료
- Seed 반복:
  - 여러 seed로 재학습해 성능 분산 확인
- Test 고정:
  - test split은 최종 검증에만 1회 사용 (튜닝 금지)
- 장시간 정상 리플레이:
  - 정상 장주행에서 오탐률 재확인

## 6) 최종 판단 기준
- 정상 데이터에서 오탐이 운영 기준 이하
- 실차 이상 2케이스 탐지 성공
- 응답 정합성 이슈 없음
- fallback 동작(저품질 입력 시 IF_ONLY) 안정 확인

