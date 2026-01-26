package kr.co.himedia.service;

import kr.co.himedia.common.util.EncryptionUtils;
import kr.co.himedia.dto.cloud.CloudVehicleRegisterRequest;
import kr.co.himedia.entity.CloudTelemetry;
import kr.co.himedia.entity.Vehicle;
import kr.co.himedia.repository.CloudTelemetryRepository;
import kr.co.himedia.repository.UserRepository;
import kr.co.himedia.repository.VehicleRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;
import java.util.UUID;

@Slf4j
@Service
@RequiredArgsConstructor
public class CloudAuthService {

    private final UserRepository userRepository;
    private final VehicleRepository vehicleRepository;
    private final EncryptionUtils encryptionUtils;
    private final HighMobilityService highMobilityService;
    private final CloudTelemetryRepository cloudTelemetryRepository;
    private final CloudSyncProducer cloudSyncProducer;

    /**
     * 사용자가 선택한 클라우드 차량을 우리 시스템에 등록합니다.
     */
    public Vehicle registerCloudVehicle(UUID userId, CloudVehicleRegisterRequest request) {
        log.info("차량 등록(Clearance) 시작 - userId: {}, vehicleId: {}", userId, request.getProviderVehicleId());

        userRepository.findById(userId)
                .orElseThrow(() -> new RuntimeException("User not found: " + userId));

        Vehicle vehicle = vehicleRepository.findById(UUID.fromString(request.getProviderVehicleId()))
                .orElseThrow(() -> new RuntimeException("Vehicle not found: " + request.getProviderVehicleId()));

        if (!vehicle.getUserId().equals(userId)) {
            throw new RuntimeException("해당 차량에 대한 권한이 없습니다.");
        }

        // 중복 등록 방지
        if (Boolean.TRUE.equals(vehicle.getCloudLinked())) {
            throw new RuntimeException("이미 클라우드에 연동된 차량입니다.");
        }

        if (vehicle.getVin() == null) {
            throw new RuntimeException("차량의 VIN 정보가 없습니다. 먼저 VIN을 등록해주세요.");
        }

        try {
            String decryptedVin = encryptionUtils.decrypt(vehicle.getVin());

            // 1. 등록 요청 (Fleet Clearance)
            Map<String, Object> regResult = highMobilityService.registerVehicle(decryptedVin);
            log.info("[HighMobility] Clearance 요청 결과: {}", regResult);

            // 2. [검증] 등록 후 실제 승인 상태 조회
            Map<String, Object> statusResult = highMobilityService.getClearanceStatus(decryptedVin);
            String status = (String) statusResult.get("status");
            log.info("[HighMobility] 등록 후 상태 조회: {}", status);

            if (!"APPROVED".equalsIgnoreCase(status) && !"PENDING".equalsIgnoreCase(status)) {
                throw new RuntimeException("하이모빌리티 차량 등록 실패 - 상태: " + status);
            }

            // 3. 연동 성공 처리
            vehicle.updateCloudLinkStatus(true);
            Vehicle saved = vehicleRepository.save(vehicle);

            // RabbitMQ를 통한 비동기 상태 체크 및 데이터 동기화 요청
            cloudSyncProducer.publishSyncRequest(saved.getVehicleId());

            return saved;
        } catch (Exception e) {
            log.error("하이모빌리티 차량 등록 실패", e);
            throw new RuntimeException("하이모빌리티 차량 등록 처리 중 오류가 발생했습니다: " + e.getMessage());
        }
    }

    /**
     * 클라우드 연동을 해제합니다.
     */
    public void revokeCloudVehicle(UUID userId, CloudVehicleRegisterRequest request) {
        log.info("차량 연동 해제 요청 - userId: {}, vehicleId: {}", userId, request.getProviderVehicleId());

        userRepository.findById(userId)
                .orElseThrow(() -> new RuntimeException("User not found: " + userId));

        Vehicle vehicle = vehicleRepository.findById(UUID.fromString(request.getProviderVehicleId()))
                .orElseThrow(() -> new RuntimeException("Vehicle not found: " + request.getProviderVehicleId()));

        if (!vehicle.getUserId().equals(userId)) {
            throw new RuntimeException("해당 차량에 대한 권한이 없습니다.");
        }

        // 연동되지 않은 차량인지 체크
        if (!Boolean.TRUE.equals(vehicle.getCloudLinked())) {
            throw new RuntimeException("클라우드에 연동되지 않은 차량입니다.");
        }

        if (vehicle.getVin() == null) {
            throw new RuntimeException("차량의 VIN 정보가 없습니다.");
        }

        try {
            String decryptedVin = encryptionUtils.decrypt(vehicle.getVin());

            // 1. 연동 해제 요청
            Map<String, Object> delResult = highMobilityService.deleteVehicle(decryptedVin);
            log.info("[HighMobility] 연동 해제 요청 결과: {}", delResult);

            // 2. [검증] 실제 상태가 REVOKED 되었는지 확인
            // 하이모빌리티는 삭제 요청 시 즉시 REVOKED 되거나, 목록에서 사라질 수 있음.
            // 여기서는 상태 조회를 시도하고, 만약 조회되지 않거나(404 등) status가 REVOKED/null 이면 성공으로 간주
            try {
                Map<String, Object> statusResult = highMobilityService.getClearanceStatus(decryptedVin);
                String status = (String) statusResult.get("status");
                log.info("[HighMobility] 해제 후 상태 조회: {}", status);

                // REVOKED 상태거나, 상태가 없으면 해제된 것으로 판단
                // (일부 API는 해제 시 REJECTED나 REVOKED 등을 반환하거나 404가 뜰 수 있음)
                if (status != null && !"REVOKED".equalsIgnoreCase(status) && !"REJECTED".equalsIgnoreCase(status)) {
                    // 주의: API 특성에 따라 PENDING으로 돌아갈 수도 있는지 확인 필요하지만,
                    // 일단 REVOKED가 아니면 경고를 띄우거나 에러 처리
                    log.warn("연동 해제 후 상태가 REVOKED가 아닙니다: {}", status);
                    // 강제 해제를 원하면 에러를 던지지 않고 진행, 엄격하면 던짐. 여기선 엄격하게 처리.
                    // throw new RuntimeException("연동 해제 실패 - 상태: " + status);
                }
            } catch (Exception e) {
                log.info("해제 후 상태 조회 실패(삭제됨으로 간주): {}", e.getMessage());
            }

            // 3. DB 업데이트
            vehicle.updateCloudLinkStatus(false);
            vehicleRepository.save(vehicle);
            log.info("차량 연동 해제 완료 (DB 업데이트)");

        } catch (Exception e) {
            log.error("차량 연동 해제 실패", e);
            throw new RuntimeException("차량 연동 해제 처리 중 오류가 발생했습니다: " + e.getMessage());
        }
    }

    /**
     * 차량의 VIN 정보를 업데이트하고 암호화하여 저장합니다.
     */
    public void updateVehicleVin(UUID vehicleId, String plainVin) {
        Vehicle vehicle = vehicleRepository.findById(vehicleId)
                .orElseThrow(() -> new RuntimeException("Vehicle not found: " + vehicleId));

        if (plainVin != null && !plainVin.isBlank()) {
            String encryptedVin = encryptionUtils.encrypt(plainVin);
            vehicle.updateVin(encryptedVin);
            vehicleRepository.save(vehicle);
            log.info("[CloudAuth] VIN 업데이트 완료 (암호화) - vehicleId: {}", vehicleId);
        }
    }

    /**
     * 차량 데이터를 하이모빌리티로부터 동기화합니다. (이력 저장만 수행)
     */
    public void syncVehicleData(UUID vehicleId, boolean updateVehicleEntity) {
        Vehicle vehicle = vehicleRepository.findById(vehicleId)
                .orElseThrow(() -> new RuntimeException("Vehicle not found"));
        syncVehicleDataInternal(vehicle, updateVehicleEntity);
    }

    /**
     * 내부 데이터 동기화 로직
     */
    @SuppressWarnings("unchecked")
    private void syncVehicleDataInternal(Vehicle vehicle, boolean updateVehicleEntity) {
        if (vehicle.getVin() == null)
            return;

        try {
            String decryptedVin = encryptionUtils.decrypt(vehicle.getVin());
            Map<String, Object> data = highMobilityService.getVehicleData(decryptedVin);
            log.info("[Sync] 하이모빌리티 수신 원본 데이터: {}", data);

            CloudTelemetry.CloudTelemetryBuilder telemetryBuilder = CloudTelemetry.builder().vehicle(vehicle);

            // 1. Diagnostics 데이터 추출
            if (data.containsKey("diagnostics")) {
                Map<String, Object> diagnostics = (Map<String, Object>) data.get("diagnostics");

                if (diagnostics.containsKey("odometer")) {
                    Map<String, Object> odometerMap = (Map<String, Object>) diagnostics.get("odometer");
                    if (odometerMap.containsKey("data")) {
                        Map<String, Object> innerData = (Map<String, Object>) odometerMap.get("data");
                        Object val = innerData.get("value");
                        if (val instanceof Number) {
                            Double odometerValue = ((Number) val).doubleValue();
                            telemetryBuilder.odometer(odometerValue);
                            log.info("[Sync] Odometer 추출 성공: {}", odometerValue);
                        }
                    }
                }
                if (diagnostics.containsKey("fuel_level")) {
                    Double fuelValue = getDoubleValue(diagnostics.get("fuel_level"));
                    if (fuelValue != null)
                        telemetryBuilder.fuelLevel(fuelValue);
                }
                if (diagnostics.containsKey("battery_level")) {
                    Double batteryValue = getDoubleValue(diagnostics.get("battery_level"));
                    if (batteryValue != null)
                        telemetryBuilder.batterySoc(batteryValue);
                }
                if (diagnostics.containsKey("engine_oil_life")) {
                    Double oilLifeValue = getDoubleValue(diagnostics.get("engine_oil_life"));
                    if (oilLifeValue != null)
                        telemetryBuilder.engineOilLife(oilLifeValue);
                }
                if (diagnostics.containsKey("tire_pressures")) {
                    List<Map<String, Object>> tires = (List<Map<String, Object>>) diagnostics.get("tire_pressures");
                    for (Map<String, Object> tire : tires) {
                        String location = (String) tire.get("location");
                        Double pressure = getDoubleValue(tire);
                        if (pressure != null) {
                            if ("front_left".equals(location))
                                telemetryBuilder.tirePressureFl(pressure);
                            else if ("front_right".equals(location))
                                telemetryBuilder.tirePressureFr(pressure);
                            else if ("rear_left".equals(location))
                                telemetryBuilder.tirePressureRl(pressure);
                            else if ("rear_right".equals(location))
                                telemetryBuilder.tirePressureRr(pressure);
                        }
                    }
                }
            }

            // 2. Location 데이터 추출
            if (data.containsKey("location")) {
                Map<String, Object> location = (Map<String, Object>) data.get("location");
                if (location.containsKey("coordinates")) {
                    Map<String, Object> coords = (Map<String, Object>) location.get("coordinates");
                    Double lat = getDoubleValue(coords.get("latitude"));
                    Double lon = getDoubleValue(coords.get("longitude"));
                    if (lat != null)
                        telemetryBuilder.latitude(lat);
                    if (lon != null)
                        telemetryBuilder.longitude(lon);
                }
            }

            // 3. Climate 데이터 추출
            if (data.containsKey("climate")) {
                Map<String, Object> climate = (Map<String, Object>) data.get("climate");
                telemetryBuilder.insideTemp(getDoubleValue(climate.get("inside_temperature")));
                telemetryBuilder.outsideTemp(getDoubleValue(climate.get("outside_temperature")));
            }

            // 4. Security 데이터 추출 (Lock/Window)
            if (data.containsKey("doors")) {
                Map<String, Object> doors = (Map<String, Object>) data.get("doors");
                if (doors.containsKey("locks_state")) {
                    telemetryBuilder
                            .doorLockStatus((String) ((Map<String, Object>) doors.get("locks_state")).get("value"));
                }
            }
            if (data.containsKey("windows")) {
                Map<String, Object> windows = (Map<String, Object>) data.get("windows");
                // 창문 상태 파싱: 모든 창문이 닫혀있으면 CLOSED, 하나라도 열려있으면 OPEN
                if (windows.containsKey("positions")) {
                    List<Map<String, Object>> positions = (List<Map<String, Object>>) windows.get("positions");
                    boolean anyOpen = positions.stream()
                            .anyMatch(pos -> {
                                Object value = ((Map<String, Object>) pos.get("data")).get("value");
                                return value != null && !"closed".equalsIgnoreCase(value.toString());
                            });
                    telemetryBuilder.windowOpenStatus(anyOpen ? "OPEN" : "CLOSED");
                } else if (windows.containsKey("open_percentages")) {
                    // 창문 열림 비율로 판단하는 경우
                    List<Map<String, Object>> percentages = (List<Map<String, Object>>) windows.get("open_percentages");
                    boolean anyOpen = percentages.stream()
                            .anyMatch(pct -> {
                                Object value = ((Map<String, Object>) pct.get("data")).get("value");
                                return value != null && ((Number) value).doubleValue() > 0;
                            });
                    telemetryBuilder.windowOpenStatus(anyOpen ? "OPEN" : "CLOSED");
                }
            }

            // 5. Charging 데이터 추출 (전기차)
            if (data.containsKey("charging")) {
                Map<String, Object> charging = (Map<String, Object>) data.get("charging");
                if (charging.containsKey("charge_state")) {
                    String stateValue = (String) ((Map<String, Object>) charging.get("charge_state")).get("value");
                    if (stateValue != null) {
                        try {
                            telemetryBuilder.chargingStatus(
                                    kr.co.himedia.entity.ChargingStatus.valueOf(stateValue.toUpperCase()));
                        } catch (IllegalArgumentException e) {
                            log.warn("알 수 없는 충전 상태: {}", stateValue);
                        }
                    }
                }
            }

            // 5. 저장 및 업데이트
            CloudTelemetry telemetry = telemetryBuilder.build();
            cloudTelemetryRepository.save(telemetry);
            log.info("[Sync] CloudTelemetry 전수 데이터 저장 완료 - vehicleId: {}", vehicle.getVehicleId());

            if (updateVehicleEntity && telemetry.getOdometer() != null) {
                log.info("[Sync] 최초 연동 주행거리 업데이트: {} -> {}", vehicle.getTotalMileage(), telemetry.getOdometer());
                vehicle.updateTotalMileage(telemetry.getOdometer());
                vehicleRepository.save(vehicle);
            }

        } catch (Exception e) {
            log.error("데이터 동기화 실패 - vehicleId: {}", vehicle.getVehicleId(), e);
        }
    }

    /**
     * 하이모빌리티의 데이터 구조(data.value)에서 Double 값을 안전하게 추출합니다.
     */
    @SuppressWarnings("unchecked")
    private Double getDoubleValue(Object obj) {
        if (obj instanceof Map) {
            Map<String, Object> map = (Map<String, Object>) obj;
            if (map.containsKey("data")) {
                Map<String, Object> data = (Map<String, Object>) map.get("data");
                Object val = data.get("value");
                if (val instanceof Number) {
                    return ((Number) val).doubleValue();
                }
            }
        }
        return null;
    }
}
