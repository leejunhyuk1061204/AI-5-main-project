# ObdAnomalyRequest vs obd_logs(ObdLog) 매핑

## 요청 최상위 필드

| 필드 | obd_logs에 있음? | 비고 |
|------|-------------------|------|
| vehicle_id | 있음 | ObdLog.vehicleId (청크 단위 동일 차량) |
| trip_id | **obd_logs에는 없음** | **가져올 수 있음** — `DiagSession.getTripId()`. 트립 연동 진단(예: 주행 종료 후 자동 진단)이면 tripId가 설정됨. 없으면 `session-{sessionId}`로 대체 |
| mode | 없음 | **기본값 전송** (DRIVING). API 스키마 필수라 보냄 |
| duration_sec | 없음 | **기본값/계산** — data 개수 또는 구간으로 계산 |
| sampling_hz | 없음 | **기본값 전송** (1) |
| timestamp_unit | 없음 | **기본값 전송** ("s") |
| options | 없음 | **기본값 전송** (window_sec, stride_sec 등) |

---

## data[] 안 (ObdSample)

### data[].t

| 항목 | obd_logs에서 채울 수 있음? |
|------|---------------------------|
| t | **가능** — ObdLog.time → epoch 초 또는 상대 인덱스(0,1,2,...)로 변환 |

### data[].features — obd_logs에서 채울 수 있는 것

| features 키 | ObdLog 소스 |
|-------------|-------------|
| rpm | rpm |
| speed | speed |
| battery_voltage_v | voltage |
| coolant_temp | coolantTemp |
| engine_load | engineLoad |
| fuel_trim_short | fuelTrimShort |
| fuel_trim_long | fuelTrimLong |
| intake_temp | intakeTemp |
| map | map |
| maf | maf |
| throttle_pos | throttlePos |
| engine_runtime | engineRuntime |
| (기타) | jsonExtra JSON 파싱 시 추가 가능 |

### data[].features — obd_logs에서 채울 수 없는 것

| features 키 | 설명 |
|-------------|------|
| brake_pressure_kpa | brake 도메인 rule용. ObdLog에 없음 → 해당 도메인 UNSUPPORTED |
| tire_pressure_fl_kpa, tire_pressure_fr_kpa, tire_pressure_rl_kpa, tire_pressure_rr_kpa | **제조사 클라우드에서 가져올 수 있음** — Smartcar 등 연동 시 `cloud_telemetry`에 저장됨(`tire_pressure_fl`, `tire_pressure_fr`, `tire_pressure_rl`, `tire_pressure_rr`). 해당 차량 최신 CloudTelemetry 조회 후 features에 넣으면 LSTM tire 도메인 사용 가능. ObdLog만 쓰면 UNSUPPORTED. |

요약: **data 안에서 obd_logs로 채우는 것** = t + features(rpm, speed, voltage→battery_voltage_v, coolantTemp, engineLoad, fuelTrim*, intakeTemp, map, maf, throttlePos, engineRuntime, jsonExtra). **obd_logs로는 못 채움** = brake_pressure_kpa. **제조사 클라우드(cloud_telemetry)로 채울 수 있음** = tire_pressure_*_kpa.
