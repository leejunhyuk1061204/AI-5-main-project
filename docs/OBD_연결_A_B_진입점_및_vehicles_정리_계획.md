# OBD 어댑터 연결 A+B 진입점 및 vehicles.obd_device_id 정리 계획

---

## 요약 (뭘 하겠는지)

1. **OBD 연결 진입점 2곳 추가**
   - **A**: 설정 > 차량 및 서비스에 "OBD 어댑터 연결" 메뉴 → 누르면 "어떤 차량에 연결할까요?" 선택 후 스캔/연결.
   - **B**: 설정 > 내 차량 관리 > 각 차량 ⋮ 메뉴에 "OBD 연결" → 그 차량으로 바로 스캔/연결.

2. **연결 시 서버·로컬 반영**
   - 서버에 기기 등록(`registerDevice`) + 차량과 연결 기록(`recordConnect`) + 현재 주행/업로드용 차량 설정(`setVehicleId`).
   - 로컬 "연결 목록" 갱신(`loadAndCacheDevices()`)해서 백그라운드 자동 재연결에 새 기기가 포함되도록 함.

3. **vehicles.obd_device_id 제거**
   - 사용하지 않는 컬럼이라 제거. 관계는 `obd_device_vehicle_history` 테이블로만 유지.
   - 수정: db/schema.sql, Vehicle 엔티티, VehicleDto, frontend vehicleApi 타입, (선택) 문서 3/4/6.

4. **백엔드/DB**
   - 새 API·테이블 없음. 기존 `obd_devices`, `obd_device_vehicle_history`와 기존 API만 사용.

---

## 1. DB/백엔드 정리 (저장 구조)

이미 필요한 테이블과 API가 있습니다. 추가 마이그레이션 없이 사용 가능합니다.

| 저장소 | 용도 |
|--------|------|
| **obd_devices** | 사용자별 OBD 기기 등록 (user_id, device_id 유일, device_type, name). |
| **obd_device_vehicle_history** | 기기–차량 연결 이력 (obd_device_id, vehicles_id, last_connected_at, calid/cvn). |

- **recordConnect** 시: `ObdDeviceVehicleHistory`에 (device, vehicle, last_connected_at) 저장/갱신.
- **vehicles.obd_device_id**: 제거 대상(아래 섹션 참고).

**연결 성공 시 프론트엔드에서 호출할 API (이미 존재):**

1. `POST /api/v1/obd/devices` — deviceId, deviceType(`ble`|`classic`), name.
2. `PUT /api/v1/obd/devices/{deviceId}/connect` — vehicleId (필수), calid/cvn(선택).

---

## 2. vehicles.obd_device_id 제거 작업

관계는 `obd_device_vehicle_history`로만 유지하므로 `vehicles.obd_device_id` 컬럼을 제거합니다. 아래 모든 위치를 수정합니다.

### 2.1 DB / 스키마

- **[db/schema.sql](db/schema.sql)**  
  - `vehicles` 테이블 정의에 `obd_device_id` 컬럼이 있으면 제거.
  - 현재 schema.sql의 `vehicles`(86–103라인)에는 없을 수 있음. 다른 브랜치/환경에서 추가돼 있다면 제거.
  - 이미 운영 DB에 컬럼이 존재하면, 별도 마이그레이션에서 `ALTER TABLE vehicles DROP COLUMN IF EXISTS obd_device_id;` 실행.

### 2.2 백엔드

- **[backend/src/main/java/kr/co/himedia/entity/Vehicle.java](backend/src/main/java/kr/co/himedia/entity/Vehicle.java)**  
  - 필드 `obdDeviceId` 제거.  
  - Builder/생성자 인자 및 대입 제거.

- **[backend/src/main/java/kr/co/himedia/dto/vehicle/VehicleDto.java](backend/src/main/java/kr/co/himedia/dto/vehicle/VehicleDto.java)**  
  - `RegistrationRequest.obdDeviceId` 필드 제거.  
  - `toEntity()` 내 `.obdDeviceId(obdDeviceId)` 제거.  
  - `Response.obdDeviceId` 필드 제거.  
  - `Response.from()` 내 `setObdDeviceId(vehicle.getObdDeviceId())` 제거.

### 2.3 프론트엔드

- **[frontend/api/vehicleApi.ts](frontend/api/vehicleApi.ts)**  
  - `VehicleResponse`의 `obdDeviceId` 제거.  
  - 차량 등록 요청 타입에 `obdDeviceId`가 있으면 제거.

### 2.4 문서 (선택)

- **[docs/3.DB 설계서.md](docs/3.DB 설계서.md)** — vehicles 테이블의 obd_device_id 설명 제거 또는 수정.
- **[docs/4.API 명세서.md](docs/4.API 명세서.md)** — 차량 응답/요청 예시에서 obdDeviceId 제거 또는 수정.
- **[docs/6.MENTORING.md](docs/6.MENTORING.md)** — vehicles obd_device_id 언급 제거 또는 수정.

---

## 3. 로컬 연결 목록(캐시) 최신화

블루투스 백그라운드 자동 재연결은 **ObdService.tryAutoConnectFromCache()**가 **AsyncStorage의 `obd_devices_cache`(STORAGE_KEY_OBD_DEVICES)** 목록을 읽어 라운드로빈으로 시도합니다. 이 목록은 **서버 GET /obd/devices** 결과로 채워지며, **ObdService.loadAndCacheDevices()**를 호출할 때만 갱신됩니다.

- **saveLastDevice**: 연결 성공 시 `setClassicDevice`/`setTargetDevice` 안에서 호출됨 → "마지막 1대"만 저장(STORAGE_KEY_LAST_DEVICE). 이미 반영됨.
- **연결 목록(여러 대)**: `registerDevice`로 서버에 기기를 넣은 뒤, **반드시 loadAndCacheDevices()**를 호출해야 로컬 캐시에 새 기기가 들어가고, 백그라운드 재연결 대상이 됨.

따라서 A/B 플로우에서 **연결 성공 처리 시 loadAndCacheDevices() 호출**을 포함합니다.

---

## 4. 플로우 요약 (A/B 구현)

- **A**: 설정 > 차량 및 서비스 > "OBD 어댑터 연결" → (어떤 차량?) → ObdConnect 모달 → 연결 성공 시 registerDevice, recordConnect, setVehicleId, **loadAndCacheDevices()**.
- **B**: 설정 > 내 차량 관리 > [차량] ⋮ > "OBD 연결" → ObdConnect 모달 → 동일 시퀀스.

연결 성공 시: `obdDeviceApi.registerDevice(...)` → `obdDeviceApi.recordConnect(deviceId, { vehicleId })` → `ObdService.setVehicleId(selectedVehicleId)` → **`ObdService.loadAndCacheDevices()`** (로컬 연결 목록 최신화).

---

## 5. 구현 체크리스트

| 구분 | 내용 |
|------|------|
| vehicles 제거 | db/schema.sql — vehicles에 obd_device_id 있으면 제거; 필요 시 마이그레이션 DROP COLUMN |
| vehicles 제거 | Vehicle.java, VehicleDto.java (RegistrationRequest, Response, from, toEntity) |
| vehicles 제거 | frontend vehicleApi.ts (VehicleResponse, 등록 요청 타입) |
| vehicles 제거 | docs 3/4/6 (선택) |
| A | SettingMain에 "OBD 어댑터 연결" 항목 추가 |
| A | ObdConnectFlow 화면 추가(차량 선택 → ObdConnect → 연결 성공 시 registerDevice, recordConnect, setVehicleId) |
| A | App.tsx에 ObdConnectFlow 스크린 등록 |
| B | CarManage ⋮ 메뉴에 "OBD 연결" 추가, selectedVehicleIdForObd state 유지 |
| B | handleObdConnected에서 registerDevice + recordConnect + setVehicleId 호출 |
| 공통 | onConnected 시 deviceId/deviceType/name을 BLE·Classic에 맞게 매핑 |
| 공통 | 연결 성공 후 ObdService.loadAndCacheDevices() 호출 — 로컬 연결 목록(백그라운드 재연결용) 최신화 |
