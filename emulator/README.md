# OBD 에뮬레이터

ELM327 프로토콜을 시뮬레이션합니다. **서버 1개 = 포트 1개 = 차량 1개**로 동작합니다.

## 실행 방법

기본 설정(config.yml)으로 실행:

```bash
cd emulator
python run_emulator.py
```

다른 COM 포트 / 차량으로 실행:

```bash
python run_emulator.py --port COM4 --vehicle DEV_002
```

차량별 config 파일을 두고 실행:

```bash
python run_emulator.py config_sonata.yml   # COM3 + DEV_001
python run_emulator.py config_k5.yml      # COM4 + DEV_002
```

(각 yml에 `connection.port`와 `vehicle_id`를 넣어 두면 됨.)

## 설정 (config.yml)

- **vehicle_id**: 사용할 차량 ID. `vehicles` 중 하나. 없으면 첫 번째 차량.
- **connection.port**: 시리얼 포트 (예: COM3). BLE 동글으로 가상 COM이 생성되면 그 포트 번호 지정.
- **mode**: `replay`(CSV 재생) 또는 `static`(초기값만).
- **vehicles**: 차량별 id, name, vin, **calid**, **cvn**, csv_file, mappings, dtcs.
  - **vin**: 09 02 응답 (차량 특정 1단계). 백엔드 `vehicles.vin`과 맞추면 VIN 매칭 테스트 가능.
  - **calid**: 09 04 응답 (ASCII). **cvn**: 09 06 응답 (8자 hex, 예: `A1B2C3D4`). 백엔드 `obd_device_vehicle_history`에 넣어 둔 값과 맞추면 CALID/CVN 경로 테스트 가능.

## 차량 특정 로직(VIN/CALID/CVN) 앱 테스트

앱이 09 모드로 읽은 VIN/CALID/CVN을 서버 `resolveVehicle`에 보내고, 서버가 **VIN → CALID → CVN → 마지막 접속 → 대표 차량** 순으로 차량을 정하는 흐름을 검증하려면:

1. **config.yml에서 보낼 값 지정**  
   - `emulator/config.yml`의 `vehicles[].vin`, `calid`, `cvn`을 원하는 값으로 설정. (이미 DEV_001 등에 예시가 있음.)
2. **백엔드와 맞추기**  
   - **VIN 경로**: 앱 로그인 계정으로 등록한 차량 중 **한 대의 VIN**을 config의 `vin`과 동일하게 넣어 둠. (DB에 해당 vehicle이 있어야 함.)  
   - **CALID/CVN 경로**: 한 번이라도 해당 deviceId + vehicleId로 `recordConnect(calid, cvn)`가 호출된 적 있으면, 같은 `calid`/`cvn`을 config에 넣어 두면 서버가 이력으로 매칭.
3. **에뮬레이터 실행**  
   - COM3가 블루투스 수신 포트라면: `connection.port: "COM3"` 인 상태로 `python run_emulator.py` 실행 (또는 `--port COM3 --vehicle DEV_001`).
4. **앱에서 연결**  
   - 폰에서 PC(블루투스)로 OBD SPP 연결 후, 앱에서 해당 기기 선택해 연결.
5. **결과 확인**  
   - 앱: 연결된 차량명이 헤더 등에 표시되는지 확인.  
   - 백엔드 로그: `[resolveVehicle] step=VIN|CALID|CVN|LAST_CONNECTED|PRIMARY` 로 어느 단계에서 결정됐는지 확인.

**COM3에서 폰으로 보내는 값**은 모두 **config.yml의 해당 vehicle의 vin, calid, cvn**으로 지정됩니다. 값을 바꾼 뒤 에뮬레이터를 다시 실행하면 됩니다.

## PC 블루투스(BLE 5.0 동글) + 폰 연결

1. PC에 USB BLE 동글 연결.
2. 동글/드라이버가 BLE 연결 시 **가상 COM 포트**를 만들면, config의 `connection.port`를 그 포트로 설정.
3. 에뮬레이터 실행 후, 폰에서 해당 기기(PC)로 BLE/SPP 연결.
4. 앱에서 OBD 연결 후 주행/테스트.

여러 차량을 쓰려면 COM 포트를 여러 개 두고, 에뮬레이터를 **차량마다 한 번씩** 실행(위 `--port` / `--vehicle` 또는 config 파일 분리).

## Ircama ELM327-emulator로 검증

앱이 표준 ELM327 동작과 맞는지 [Ircama/ELM327-emulator](https://github.com/Ircama/ELM327-emulator)로 교차 검증할 수 있습니다.

1. 설치: `pip install ELM327-emulator`
2. Windows 블루투스에서 **수신** COM 포트 추가(예: COM6).
3. **에뮬레이터를 먼저** 실행한 뒤, 폰에서 해당 COM으로 SPP 연결.

```bash
# 기본: 클라이언트가 CR(\r)로 명령 종료 (우리 앱과 동일)
python -m elm -p COM6 -s car

# 클라이언트가 NL(\n)로 명령 종료하는 경우
python -m elm -p COM6 -s car -l
```

- `-s car`: Toyota Auris Hybrid 시나리오(일반 OBD PIDs).
- 응답 형식: 기본 `\r\r>` (우리 커스텀 에뮬과 동일). 앱은 `>` 없이 오는 수신(Classic delimiter `>`)도 처리함.
- Ircama에서 `ATH1` 사용 시 CAN 헤더(7E8 04 등)가 붙어도, 앱 파서는 `41 0C` 등 데이터 부분을 찾아 파싱함.

**앱–Ircama 정합성 (실차 테스트용)**  
- 앱은 OBD 명령을 **공백 없이** 전송합니다 (`010C`, `0902`, `03` 등). Ircama 기본/`car` 시나리오의 Request 정규식(`^010C`, `^0902` 등)과 일치해, 별도 merge 없이 `python -m elm -s car`로 검증 가능합니다.  
- AT 초기화: `ATZ` → `ATE0` → `ATL0` → `ATS0` → `ATH0` → `ATAT1` → **`ATCAF1`** → `ATSP0`. `ATCAF0`을 쓰면 Ircama는 수신을 ISO-TP로 해석(앞 2자=PCI 길이)해 `010C`가 `0C`로 잘리고 `0902`는 Invalid ISO-TP 오류가 난다. `ATCAF1`(기본값)으로 두면 전체 문자열이 OBD로 매칭된다.
