package kr.co.himedia.smartcar.service;

import com.smartcar.sdk.AuthClient;
import com.smartcar.sdk.data.*;
import com.smartcar.sdk.SmartcarException;
import com.smartcar.sdk.Smartcar;
import com.smartcar.sdk.Vehicle;
import kr.co.himedia.common.util.EncryptionUtils;
import kr.co.himedia.entity.ChargingStatus;
import kr.co.himedia.entity.CloudTelemetry;
import kr.co.himedia.entity.RegistrationSource;
import kr.co.himedia.repository.CloudTelemetryRepository;
import kr.co.himedia.repository.VehicleRepository;
import kr.co.himedia.smartcar.dto.SmartcarSyncResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Arrays;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Slf4j
@Service
@RequiredArgsConstructor
public class SmartcarService {

    private final AuthClient authClient;
    private final VehicleRepository vehicleRepository;
    private final CloudTelemetryRepository cloudTelemetryRepository;
    private final EncryptionUtils encryptionUtils;

    public String getAuthUrl() {
        // 모든 필요한 데이터 요청 권한 포함
        String[] scope = {
                "read_vehicle_info",
                "read_vin",
                "read_odometer",
                "read_fuel",
                "read_battery",
                "read_charge",
                "read_location",
                "read_tires",
                "read_engine_oil",
                "read_security",
                "control_security",
                "control_charge"
        };
        return authClient.authUrlBuilder(scope).build();
    }

    public Auth exchangeCodeForToken(String code) throws SmartcarException {
        return authClient.exchangeCode(code);
    }

    public VehicleIds getVehicles(String accessToken) throws SmartcarException {
        return Smartcar.getVehicles(accessToken);
    }

    public VehicleAttributes getVehicleAttributes(String vehicleId, String accessToken) throws SmartcarException {
        Vehicle vehicle = new Vehicle(vehicleId, accessToken);
        return vehicle.attributes();
    }

    // --- Vehicle Control Methods ---

    public void lockVehicle(String vehicleId, String accessToken) throws SmartcarException {
        Vehicle vehicle = new Vehicle(vehicleId, accessToken);
        vehicle.lock();
    }

    public void unlockVehicle(String vehicleId, String accessToken) throws SmartcarException {
        Vehicle vehicle = new Vehicle(vehicleId, accessToken);
        vehicle.unlock();
    }

    public void startCharging(String vehicleId, String accessToken) throws SmartcarException {
        Vehicle vehicle = new Vehicle(vehicleId, accessToken);
        vehicle.startCharge();
    }

    public void stopCharging(String vehicleId, String accessToken) throws SmartcarException {
        Vehicle vehicle = new Vehicle(vehicleId, accessToken);
        vehicle.stopCharge();
    }

    /**
     * Smartcar 계정에 연동된 차량들을 우리 DB와 동기화합니다.
     * VIN이 일치하는 기존 차량은 CLOUD 상태로 업데이트하고, 없는 차량은 신규 등록합니다.
     * 
     * @return 동기화 결과 리스트
     */
    @Transactional
    public List<SmartcarSyncResponse.VehicleSyncResult> syncVehicles(UUID userId, String accessToken)
            throws SmartcarException {
        log.info("[SmartcarService] 차량 동기화 시작 - userId: {}", userId);
        VehicleIds vehicleIds = getVehicles(accessToken);
        String[] ids = vehicleIds.getVehicleIds();

        List<SmartcarSyncResponse.VehicleSyncResult> syncResults = new java.util.ArrayList<>();
        List<kr.co.himedia.entity.Vehicle> userVehicles = vehicleRepository
                .findByUserIdAndDeletedAtIsNullOrderByCreatedAtAsc(userId);

        for (String vid : ids) {
            try {
                Vehicle vehicle = new Vehicle(vid, accessToken);
                VehicleAttributes attrs = vehicle.attributes();
                com.smartcar.sdk.data.VehicleVin vinRes = vehicle.vin();
                String smartcarVin = vinRes.getVin();

                log.info("[SmartcarService] Smartcar 차량 발견 - VIN: {}, Make: {}, Model: {}",
                        smartcarVin, attrs.getMake(), attrs.getModel());

                // 2. 스마트카 정보와 우리 DB 정보 비교
                log.info("[SmartcarService] Smartcar 수신 VIN: {}", smartcarVin);

                // VIN 비교 (복호화 후 트림 및 대소문자 무시)
                Optional<kr.co.himedia.entity.Vehicle> existingVehicle = userVehicles.stream()
                        .filter(v -> v.getVin() != null
                                && smartcarVin.trim().equalsIgnoreCase(encryptionUtils.decrypt(v.getVin()).trim()))
                        .findFirst();

                String status;
                if (existingVehicle.isPresent()) {
                    // [기존 차량 있음] -> 상태 업데이트
                    kr.co.himedia.entity.Vehicle v = existingVehicle.get();
                    v.updateCloudLinkStatus(true);
                    log.info("[SmartcarService] 기존 차량 매칭 성공 (VIN 일치) - vehicleId: {}", v.getVehicleId());

                    // 실시간 데이터 수집 및 저장
                    syncTelemetry(v, vehicle);
                    status = "CONNECTED";
                } else {
                    // [기존 차량 없음] -> 신규 등록
                    kr.co.himedia.entity.Vehicle newVehicle = kr.co.himedia.entity.Vehicle.builder()
                            .userId(userId)
                            .vin(encryptionUtils.encrypt(smartcarVin))
                            .manufacturer(attrs.getMake())
                            .modelName(attrs.getModel())
                            .modelYear(attrs.getYear())
                            .registrationSource(RegistrationSource.CLOUD)
                            .nickname(attrs.getMake() + " " + attrs.getModel())
                            .isPrimary(userVehicles.isEmpty() && syncResults.isEmpty())
                            .build();

                    newVehicle.updateCloudLinkStatus(true);
                    kr.co.himedia.entity.Vehicle savedVehicle = vehicleRepository.save(newVehicle);
                    log.info("[SmartcarService] 신규 차량 등록 완료 (일치하는 VIN 없음) - VIN: {}", smartcarVin);

                    // 실시간 데이터 수집 및 저장
                    syncTelemetry(savedVehicle, vehicle);
                    status = "REGISTERED";
                }

                syncResults.add(SmartcarSyncResponse.VehicleSyncResult.builder()
                        .manufacturer(attrs.getMake())
                        .modelName(attrs.getModel())
                        .vin(smartcarVin)
                        .status(status)
                        .build());

            } catch (Exception e) {
                log.error("[SmartcarService] 개별 차량 동기화 실패 - vehicleId: {}, error: {}", vid, e.getMessage(), e);
            }
        }

        return syncResults;
    }

    /**
     * 차량의 실시간 텔레메트리 데이터를 수집하여 DB에 저장합니다.
     */
    private void syncTelemetry(kr.co.himedia.entity.Vehicle vehicleEntity, Vehicle smartcarVehicle) {
        log.info("[SmartcarService] 실시간 데이터 수집 시도 - vehicleId: {}", vehicleEntity.getVehicleId());
        try {
            CloudTelemetry.CloudTelemetryBuilder builder = CloudTelemetry.builder()
                    .vehicle(vehicleEntity);

            // 1. 주행거리 (Odometer)
            try {
                com.smartcar.sdk.data.VehicleOdometer odo = smartcarVehicle.odometer();
                double odometer = odo.getDistance();
                builder.odometer(odometer);
                vehicleEntity.updateTotalMileage(odometer);
                log.info("[SmartcarService] 주행거리 수집 성공: {} km", odometer);
            } catch (Exception e) {
                log.warn("[SmartcarService] 주행거리 수집 실패: {}", e.getMessage());
            }

            // 2. 연료/배터리
            try {
                builder.fuelLevel(smartcarVehicle.fuel().getPercentRemaining());
                log.info("[SmartcarService] 연료 잔량 수집 성공");
            } catch (Exception e) {
                log.warn("[SmartcarService] 연료 잔량 수집 실패: {}", e.getMessage());
            }
            try {
                builder.batterySoc(smartcarVehicle.battery().getPercentRemaining());
                log.info("[SmartcarService] 배터리 SOC 수집 성공");
            } catch (Exception e) {
                log.warn("[SmartcarService] 배터리 SOC 수집 실패: {}", e.getMessage());
            }
            try {
                String chargeStatus = smartcarVehicle.charge().getState();
                if ("CHARGING".equals(chargeStatus))
                    builder.chargingStatus(ChargingStatus.CHARGING);
                else if ("FULLY_CHARGED".equals(chargeStatus))
                    builder.chargingStatus(ChargingStatus.FULL);
                else
                    builder.chargingStatus(ChargingStatus.DISCONNECTED);
                log.info("[SmartcarService] 충전 상태 수집 성공: {}", chargeStatus);
            } catch (Exception e) {
                log.warn("[SmartcarService] 충전 상태 수집 실패: {}", e.getMessage());
            }

            // 2-1. 배터리 용량 (Battery Capacity)
            try {
                com.smartcar.sdk.data.VehicleBatteryCapacity cap = smartcarVehicle.batteryCapacity();
                builder.batteryCapacity(cap.getCapacity());
                log.info("[SmartcarService] 배터리 용량 수집 성공: {} kWh", cap.getCapacity());
            } catch (Exception e) {
                log.warn("[SmartcarService] 배터리 용량 수집 실패 (지원안함/권한없음): {}", e.getMessage());
            }

            // 2-2. 충전 제한 (Charge Limit)
            // try {
            // com.smartcar.sdk.data.VehicleChargeLimit limit =
            // smartcarVehicle.getChargeLimit();
            // // builder.chargeLimit(limit.getLimit()); // SDK Method lookup failed
            // // log.info("[SmartcarService] 충전 제한 수집 성공: {}", limit);
            // } catch (Exception e) {
            // log.warn("[SmartcarService] 충전 제한 수집 실패 (지원안함/권한없음): {}", e.getMessage());
            // }

            // 3. 위치 (Location)
            try {
                com.smartcar.sdk.data.VehicleLocation loc = smartcarVehicle.location();
                builder.latitude(loc.getLatitude());
                builder.longitude(loc.getLongitude());
                log.info("[SmartcarService] 위치 정보 수집 성공: Lat={}, Lng={}", loc.getLatitude(), loc.getLongitude());
            } catch (Exception e) {
                log.warn("[SmartcarService] 위치 정보 수집 실패: {}", e.getMessage());
            }

            // 4. 타이어 공기압
            try {
                com.smartcar.sdk.data.VehicleTirePressure tires = smartcarVehicle.tirePressure();
                builder.tirePressureFl(tires.getFrontLeft());
                builder.tirePressureFr(tires.getFrontRight());
                builder.tirePressureRl(tires.getBackLeft());
                builder.tirePressureRr(tires.getBackRight());
                log.info("[SmartcarService] 타이어 공기압 수집 성공");
            } catch (Exception e) {
                log.warn("[SmartcarService] 타이어 공기압 수집 실패: {}", e.getMessage());
            }

            // 5. 엔진오일 수명
            try {
                builder.engineOilLife(smartcarVehicle.engineOil().getLifeRemaining());
                log.info("[SmartcarService] 엔진오일 수명 수집 성공");
            } catch (Exception e) {
                log.warn("[SmartcarService] 엔진오일 수명 수집 실패: {}", e.getMessage());
            }

            CloudTelemetry telemetry = builder.build();
            cloudTelemetryRepository.save(telemetry);
            log.info("[SmartcarService] 실시간 데이터(Telemetry) DB 저장 성공");

        } catch (Exception e) {
            log.error("[SmartcarService] 실시간 데이터 수집 중 치명적 오류 - vehicleId: {}, error: {}",
                    vehicleEntity.getVehicleId(), e.getMessage(), e);
        }
    }
}
