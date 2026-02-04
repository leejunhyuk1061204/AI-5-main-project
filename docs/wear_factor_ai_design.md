# AI 기반 소모품 마모도 예측 설계서 (Hybrid AI Approach)

이 문서는 대규모 실제 정답(Ground Truth) 데이터가 부재한 상황에서, **공학적 계산식(Engineering Formula)을 "기초 정답(Proxy Label)"으로 활용하여 XGBoost 모델을 학습시키는 하이브리드 접근법**을 정의합니다.

---

## 1. 개요 (Concept)

### 1-1. 배경 및 문제점
- **Data Scarcity**: 실제 부품이 파손되거나 교체된 시점의 정확한 "수명 종료" 데이터가 절대적으로 부족함 (동일 차종 Fleet Data 부재).
- **Cold Start**: 서비스 초기 단계에서 AI 기능을 제공해야 함.
- **Rule-Based Limitation**: 단순 공학식 만으로는 다양한 운전 패턴의 **복합적인 상호작용**(예: "냉간 시 급가속" vs "열간 시 급가속")을 부드럽게 반영하기 어려움.

### 1-2. 핵심 전략: Teacher-Student Learning
- **Teacher (공학식)**: 물리적 도메인 지식(Formula)을 이용해 주행 데이터에 대한 **가혹도 점수(Wear Severity)**를 계산합니다. (Soft Labeling)
- **Student (XGBoost)**: 주행 통계 데이터(Features)와 가혹도 점수(Label) 간의 비선형적 관계를 학습합니다.
- **목표**: 향후 실제 교체 데이터가 쌓이면 Teacher를 실제 데이터로 교체(Fine-tuning)하기 쉬운 구조를 선점합니다.

---

## 2. 시스템 아키텍처 (Architecture)

### Phase 1: 학습 데이터 생성 (Offline Training)

```mermaid
graph LR
    A[Raw OBD Logs] --> B(Feature Extractor);
    B --> C[Statistical Features\n(X: 통계 지표)];
    
    A --> D(Label Generator\nDocs/Physics Logic);
    D --> E[Pseudo-Labels\n(Y: 공학적 가혹도)];
    
    C --> F{XGBoost Trainer};
    E --> F;
    F --> G[Wear Factor Model];
```

### Phase 2: 실시간 추론 (Online Serving)

```mermaid
graph LR
    User[주행 종료] --> A[Raw OBD Logs];
    A --> B(Feature Extractor);
    B --> C[Statistical Features];
    C --> D{Wear Factor Model};
    D --> E[Final Wear Severity\n(예: 1.2배 가혹)];
```

---

## 3. 데이터 명세 (Data Specification)

### 3-1. Input Features ($X$)
OBD 로우 데이터를 **단일 주행(Trip) 단위의 통계적 지표**로 요약합니다.

| 카테고리 | 변수명 | 설명 | 비고 |
|:---:|:---|:---|:---|
| **기초 통계** | `avg_speed_kmh` | 평균 속도 | 저속 주행 여부 판단 |
| | `max_rpm` | 최대 RPM | 엔진 부하 피크 |
| | `avg_rpm` | 평균 RPM | 전반적인 부하 수준 |
| | `avg_coolant_temp` | 평균 냉각수 온도 | 열 관리 상태 |
| | `max_coolant_temp` | 최대 냉각수 온도 | 과열 여부 |
| **비율 지표** | `idle_ratio` | 공회전 시간 비율 | `speed < 1` & `rpm > 0` |
| | `high_rpm_ratio` | 고RPM 비율 | `rpm > 3000` (차종별 조정 가능) |
| | `cold_start_ratio` | 냉간 주행 비율 | 냉각수 온도 < 65°C 구간 비율 |
| **운전 패턴** | `hard_accel_count_km` | km당 급가속 횟수 | 공격적 운전 성향 |
| | `hard_brake_count_km` | km당 급제동 횟수 | 공격적 운전 성향 |
| **환경** | `ambient_temp` | 외기 온도 | (가능 시) 극한 기온 보정 |

### 3-2. Target Labels ($Y$)
`docs/wear_factor_logic.md`의 공식을 통해 산출된 **"표준 대비 가혹도(Severity Ratio)"**를 사용합니다.

- **범위**: 0.5 (매우 얌전) ~ 3.0 (매우 가혹)
- **기준**: 1.0 (표준 운전 조건)
- **산출 예시**:
    $$ Y_{engine} = \frac{\text{Formula Calculated Wear}}{\text{Standard Wear (Distance Only)}} $$
    > *예: 10km 주행했는데 공학식 마모도가 15km치라면, $Y = 1.5$*

---

## 4. 모델링 전략 (Modeling Strategy)

### 4-1. 모델 선택: XGBoost Regressor
- **이유**:
    1. **Tabular Data SOTA**: 통계적 피처(Table 형태) 처리에 가장 강력함.
    2. **Explainability**: `Feature Importance`를 통해 사용자에게 "왜 점수가 나쁜지" 설명 가능.
    3. **Lightweight**: 모바일/임베디드 환경(On-device) 또는 경량 서버에서도 매우 빠름.

### 4-2. 기대 효과
1. **일관성 확보**: 공학식의 들쭉날쭉한 경계값을 부드럽게 만들어줌 (Smoothing).
2. **복합 패턴 발견**: "공회전이 많지만 급가속은 없는 경우" vs "공회전도 많고 급가속도 많은 경우"의 가중치를 데이터 분포에 맞게 최적화.
3. **개인화 리포트**: 
    > *"고객님은 **공회전 비율(25%)**이 높아 엔진오일 수명이 예상보다 **1.2배** 빠르게 줄고 있습니다."*

---

## 5. 향후 확장 (Next Steps)
1. **Anomaly Detection 결합**: LSTM/AutoEncoder로 탐지된 `anomaly_score`를 피처 $X$에 추가하여, 기계적 이상 징후를 마모도에 반영.
2. **Human Feedback**: 정비소 실제 교체 데이터를 소량이라도 확보하면, 이를 통해 XGBoost 모델을 Fine-tuning (Teacher Weight 감소, Real Data Weight 증가).
