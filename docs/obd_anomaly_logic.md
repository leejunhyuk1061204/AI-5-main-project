# OBD 이상 탐지(Anomaly Detection) 알고리즘 설계서

이 문서는 차량의 OBD(On-Board Diagnostics) 데이터를 분석하여 차량의 기계적/전기적 이상 징후를 탐지하는 **AI 진단 시스템**의 구조와 알고리즘을 설명합니다.

---

## 1. 시스템 구조 (Ensemble Architecture)

진단 시스템은 고도화된 머신러닝 모델(LSTM-AE)과 즉각적인 판별이 가능한 규칙 기반(Rule-based) 엔진이 결합된 앙상블 구조를 가집니다.

### ① Core Engine: LSTM-AE
- **목적**: 엔진 및 주요 시스템의 비정상적인 거동 패턴 탐지
- **알고리즘**: LSTM Autoencoder (비지도 학습)
- **방식**: 정상 데이터를 학습한 오토인코더가 입력 데이터를 재구성(Reconstruct)할 때 발생하는 오차(Reconstruction Error)를 점수화하여 이상 여부 판단

### ② Extension Engines: Rule-based
- **목적**: 특정 도메인(브레이크, 타이어, 전압 등)의 물리적 한계치 초과 탐지
- **도메인별 규칙**:
  - **Brake**: 제동 압력이 비정상적으로 높은 경우
  - **Electrical**: 배터리 전압이 임계치 이하로 떨어지는 경우
  - **Tire**: 타이어 공기압이 기준치 미만인 경우
  - **Idle**: 공회전 상태에서의 특정 파라미터 일탈

## 2. 매개변수 제어 및 API 요청

사용자는 API 요청 시 `options` 필드를 통해 분석 정밀도를 직접 동적으로 지정할 수 있습니다.

- **전달 경로**: `ObdAnomalyRequest` -> `options` (Options 모델)
- **주요 필드**:
    - `window_sec`: 윈도우 크기 (기본값: 60s, 최소: 1s)
    - `stride_sec`: 이동 간격 (기본값: 60s, 최소: 1s)
- **동작 방식**: 
    1. 클라이언트(App/Web)에서 진단 요청 시 원하는 정밀도 값을 포함하여 POST 요청을 보냅니다.
    2. 서버 내부의 `ObdAnomalyService`가 이 값을 받아 `make_windows` 함수로 전달하여 데이터를 원하는 규격으로 절삭합니다.

---

## 3. 데이터 처리 흐름

전체 분석은 **Windowing -> Inference -> Aggregation**의 3단계로 진행됩니다.

### Step 1: Sliding Windowing
- 전체 주행 데이터를 일정한 시간 단위(예: 60초)로 쪼개어 분석합니다.
- 조절 매개변수 및 정밀도 영향:
    - **`window_sec` (윈도우 크기)**: 분석 1회당 포함되는 데이터의 양입니다.
        - **확대 (예: 120s)**: 긴 호흡의 패턴(엔진 부하 추이 등)을 분석하기 좋으나, 짧은 순간의 노이즈나 피크(Peak)성 이상은 무시될 확률이 높아집니다.
        - **축소 (예: 10s)**: 미세한 데이터 변화에 민감하게 반응(High Sensitivity)하여 순간적인 이상을 잘 잡아내지만, 전체적인 맥락 파악은 어렵습니다.
    - **`stride_sec` (이동 간격)**: 다음 분석 시작점까지의 도약 거리입니다. **"왜 윈도우 크기(60s)와 다르게 설정하나요?"**에 대한 핵심 답변은 **중첩(Overlap)**에 있습니다.
        - **비중첩 (Stride = Window, 예: 60s/60s)**: 데이터를 60초 단위로 딱딱 끊어서 분석합니다. (0-60, 60-120...) 구조가 단순하고 연산량이 적지만, **60초 경계선 부분에서 발생한 짧은 이상**은 두 조각으로 나뉘어 탐지되지 않을 위험이 있습니다.
        - **중첩 (Stride < Window, 예: 60s/10s)**: 60초 분량을 분석한 뒤, 딱 10초만 옆으로 밀어서 다시 60초를 분석합니다. (0-60, 10-70, 20-80...) 
            - **장점 1. 경계면 보완**: 분석 구간이 겹치므로, 특정 시점에 걸쳐 있는 이상 징후를 놓치지 않고 포착합니다.
            - **장점 2. 시간 정밀도(Resolution)**: 이상이 발생했을 때, "어느 60초 구간"이 아니라 "몇 초 지점부터" 발생했는지 훨씬 정밀하게(10초 단위로) 특정할 수 있습니다.
            - **장점 3. 빈번한 업데이트**: 60초를 기다릴 필요 없이 10초마다 새로운 진단 결과를 얻을 수 있습니다.

### Step 2: Distributed Inference
- 각 윈도우에 대해 Core Engine과 활성화된 Extension들을 병렬 또는 순차적으로 실행합니다.
- **Common Envelope**: 모든 분석 결과는 동일한 포맷(상태, 점수, 임계치, 이벤트 정보)으로 표준화되어 반환됩니다.

### Step 3: Result Aggregation
- **이중 구조 응답**: 분석 결과는 '개별 윈도우 상세 리스트'와 '전체 구간 요약(Aggregated)' 정보를 동시에 반환합니다.
    - **상세 결과 (`window_results`)**: 15분 데이터를 60초씩 쪼갠 15개의 결과가 모두 포함됩니다. (시계열 차트 그리거나 정밀 분석 시 사용)
    - **요약 결과 (`core`, `extensions`)**: 15개의 결과 중 가장 핵심적인 내용을 하나로 합친 정보입니다. (사용자에게 "문제가 있다/없다"를 즉시 알려줄 때 사용)
- **종합(Aggregation) 규칙**:
  - **Score**: 15개 윈도우 중 가장 위험했던 순간의 점수(**Max**)를 대표로 선택합니다.
  - **Is Anomaly**: 15회 중 단 한 번이라도 이상이 있었다면, "이 주행 세션은 이상이 있었다(**Any**)"고 판단합니다.
  - **Details**: 이상이 발생한 모든 윈도우의 인덱스(`anomaly_windows`)와 해당 지점들의 상세 이벤트(`events`)를 **누적하여(Flatten)** 제공합니다. 사용자는 요약본만 보고도 "어느 지점에서 어떤 수치 때문에" 이상이 발생했는지 한눈에 파악할 수 있습니다.

### Step 4: Advance & Expansion (Roadmap)
현재 시스템은 아래와 같은 고도화 방향을 지원하도록 설계되었습니다:
- **Engine Feature Attribution**: AI가 찾아낸 이상 패턴에서 어떤 센서(RPM, Load 등)가 가장 큰 영향을 주었는지 기여도를 계산하여 `events`에 포함합니다.
- **Rule Expansion**: `obd_logs`의 표준 컬럼들을 활용하여 냉각 계통(Coolant Temp), 연료 계통(Fuel Trim), 흡기 계통(MAF/MAP) 등에 대한 공학적 임계치 규칙을 지속적으로 추가할 수 있습니다.

---

## 3. 상세 도메인별 점검 항목 (Extensions)

| 도메인 | 주요 입력 피처(Feature) | 이상 트리거(Trigger) 조건 |
| :--- | :--- | :--- |
| **Engine (Core)** | RPM, Load, Coolant Temp, MAF 등 | LSTM 재구성 오차 > 0.70 |
| **Electrical** | `battery_voltage_v` | 전압 < 11.8V |
| **Brake** | `brake_pressure_kpa` | 제동압 > 20,000 kPa |
| **Tire** | `tire_pressure_fl/fr/rl/rr_kpa` | 어느 한 곳이라도 < 200 kPa |

---

## 4. 공통 결과 규격 (Common Envelope)

모든 분석 결과(엔진 코어, 전력, 브레이크 등)는 **API 명세서 v2.0(Part 2 - 3.2)**을 엄격히 준수하여 아래와 같은 **Common Envelope** 형태로 반환됩니다. 이는 요약 리포트와 개별 윈도우 결과 모두에 적용되는 표준 인터페이스입니다.

### ① 데이터 구조 (JSON 예시)
```json
{
  "domain": "engine",
  "status": "PROCESSED",
  "method": "ml",
  "score": 0.85,
  "threshold": 0.70,
  "is_anomaly": true,
  "details": {
    "model": { "name": "lstm_ae", "version": "v1.0" },
    "anomaly_windows": [7, 8, 9],
    "events": []
  }
}
```

### ② 필드 상세 설명
- **`domain`**: 분석 대상 영역 (engine, electrical, brake, tire, idle)
- **`status`**: 분석 수행 상태 (`PROCESSED`, `SKIPPED`, `UNSUPPORTED`, `ERROR`)
- **`method`**: 분석 방법 (`ml`, `rule`, `hybrid`)
- **`score`**: 이상 점수 (0~1 사이의 값)
- **`threshold`**: 이상 판단 기준치
- **`is_anomaly`**: 최종 이상 여부 (True/False)
- **`details`**: 도메인별 추가 데이터 (검출된 규칙 리스트, 이벤트 등)

---

## 5. 진단 결과 상태 (Status) Definition
- **PROCESSED**: 분석이 정상적으로 완료됨
- **SKIPPED**: 주행 모드 부적합(예: 주행 중인데 공회전 정밀 진단 요청) 등으로 분석 건너뜀
- **UNSUPPORTED**: 차량이 해당 피처를 지원하지 않아 분석 불가
- **ERROR**: 데이터 결손 또는 시스템 내부 오류 발생
