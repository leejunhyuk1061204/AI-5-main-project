# ELM327-emulator 시나리오 스크립트

이 디렉토리에는 ELM327-emulator에서 사용할 수 있는 시나리오 스크립트가 있습니다.

## 사용 방법

### 1. ELM327-emulator 서버 시작

```bash
python3 -m elm -s car -n 35000
```

또는 시리얼 모드:
```bash
python3 -m elm -s car
```

### 2. 시나리오 실행

ELM327-emulator 대화형 모드(`CMD>` 프롬프트)에서:

#### 시나리오 1: 정상 주행
```python
import threading
exec(open('emulator/scenarios/scenario1_normal_driving.py').read())
threading.Thread(target=scenario1_normal_driving, daemon=True).start()
```

또는:
```python
exec(open('emulator/scenarios/scenario1_normal_driving.py').read())
run()  # 내장된 run() 함수 사용
```

#### 시나리오 2: 고장 발생
```python
import threading
exec(open('emulator/scenarios/scenario2_dtc_failure.py').read())
threading.Thread(target=scenario2_dtc_failure, daemon=True).start()
```

또는:
```python
exec(open('emulator/scenarios/scenario2_dtc_failure.py').read())
run()  # 내장된 run() 함수 사용
```

## 시나리오 상세

### 시나리오 1: 정상 주행 (`scenario1_normal_driving.py`)

**타임라인:**
1. 시동 걸고 1분 대기 (RPM: 800-1000, 속도: 0)
2. 5분 주행 (RPM: 1500-3000, 속도: 40-100 km/h)
3. 1분 대기 (RPM: 800-1200, 속도: 0)
4. 시동 끄기

**총 소요 시간:** 약 7분

### 시나리오 2: 고장 발생 (`scenario2_dtc_failure.py`)

**타임라인:**
1. 시동 걸고 30초 주행 (RPM: 1500-2500, 속도: 40-80 km/h)
2. 2분 추가 주행 (RPM: 1500-2800, 속도: 50-100 km/h)
3. **DTC 발생** (MIL 켜짐, 고장 코드 저장)
   - P0301: 실린더 1 미스파이어
   - P0171: 시스템 너무 희박 (Bank 1)
   - P0420: 촉매 변환기 효율 저하 (Bank 1)
   - P0128: 냉각수 온도 센서 범위/성능 문제
4. 갓길에 세워서 1분 대기 (RPM: 800-1000, 속도: 0)
5. 시동 끄기

**총 소요 시간:** 약 3분 30초

## 테스트 방법

시나리오 실행 후 다른 터미널에서 앱을 실행하거나, ELM327-emulator 대화형 모드에서:

```bash
# DTC 상태 확인
test 0101

# DTC 코드 읽기
test 03

# RPM 확인
test 010C

# 속도 확인
test 010D
```

## 주의사항

- 시나리오는 백그라운드 스레드로 실행되므로, 실행 중에도 다른 명령어를 입력할 수 있습니다.
- 시나리오 실행 중에는 `quit` 명령어로 종료할 수 있습니다.
- 시나리오가 완료되면 자동으로 `engineoff` 시나리오로 전환됩니다.
