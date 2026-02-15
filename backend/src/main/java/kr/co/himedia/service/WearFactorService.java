package kr.co.himedia.service;

import kr.co.himedia.common.constants.ConsumableConstants;
import kr.co.himedia.entity.Notification.NotificationType;
import kr.co.himedia.entity.TripSummary;
import kr.co.himedia.entity.User;
import kr.co.himedia.entity.Vehicle;
import kr.co.himedia.entity.VehicleConsumable;
import kr.co.himedia.repository.ConsumableItemRepository;
import kr.co.himedia.repository.UserRepository;
import kr.co.himedia.repository.VehicleConsumableRepository;
import kr.co.himedia.repository.VehicleRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Duration;
import java.util.List;

/**
 * 소모품 마모 계수 계산 서비스 (규칙 기반 로컬 구현)
 *
 * AI 서버 의존성을 제거하고, Python 공식과 동일한 규칙 기반 계산을 Java로 구현합니다.
 * 5가지 소모품(타이어, 엔진오일, 냉각수, 에어필터, 브레이크패드)의 마모 계수를 계산합니다.
 *
 * <p>미지원 PID: obd_logs에는 해당 컬럼이 null로 저장됨. TripService 집계 시 null은 0으로 취급해
 * trip_summaries에 반영하므로, 집계값이 0이 될 수 있음. 공식에서 필수 입력이 null/무의미하면
 * factor=1.0(주행거리만 반영)으로 fallback.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class WearFactorService {

    private static final double CONSUMABLE_ALERT_THRESHOLD = 30.0;

    // ==================== 의존성 ====================
    private final VehicleRepository vehicleRepository;
    private final VehicleConsumableRepository vehicleConsumableRepository;
    private final ConsumableItemRepository consumableItemRepository;
    private final NotificationService notificationService;
    private final UserRepository userRepository;

    // ==================== 메인 통합 메서드 ====================

    /**
     * 주행 종료 시 호출 - 해당 차량의 모든 소모품에 대해 규칙 기반 마모 계수 계산 (동기)
     *
     * @param trip 완료된 주행 요약 (통계가 계산된 상태)
     */
    @Transactional
    public void calculateWearFactorsLocal(TripSummary trip) {
        log.info("[WearFactor] 규칙 기반 마모 계수 계산 시작 [Vehicle: {}, Distance: {} km]",
                trip.getVehicleId(), trip.getDistance());

        Vehicle vehicle = vehicleRepository.findById(trip.getVehicleId())
                .orElseThrow(() -> new RuntimeException("차량을 찾을 수 없습니다: " + trip.getVehicleId()));

        // 향후 createDefaultMapping()에서 사용 예정
        @SuppressWarnings("unused")
        Double currentTotalMileage = vehicle.getTotalMileage() != null ? vehicle.getTotalMileage() : 0.0;

        // 1. 해당 차량의 모든 소모품 조회
        List<VehicleConsumable> allConsumables = vehicleConsumableRepository.findByVehicle(vehicle);

        // 2. 추가 통계 계산 (TripSummary에 없는 필드)
        Double highRpmRatio = trip.getHighRpmRatio();
        if (highRpmRatio == null) {
            highRpmRatio = 0.0;
        }
        Double idleRatio = calculateIdleRatio(trip);

        log.info("[WearFactor] 추가 통계: highRpmRatio={}, idleRatio={}",
                String.format("%.3f", highRpmRatio), String.format("%.3f", idleRatio));

        // 3. 각 소모품별 마모 계수 계산
        for (VehicleConsumable vc : allConsumables) {
            if (vc.getConsumableItem() == null)
                continue;

            String itemCode = vc.getConsumableItem().getCode();
            if ("OTHER".equals(itemCode)) {
                continue;
            }

            try {
                // 3-1. 마모 계수(multiplier) 계산
                Double factor = calculateFactorByItemCode(itemCode, trip, vehicle, highRpmRatio, idleRatio);

                // 3-2. 마모 계수 저장
                vc.setWearFactor(factor);

                // 3-3. 증분 수명 차감 (보존 메서드 사용)
                updateRemainingLifeIncremental(vc, trip.getDistance());

                log.info("[WearFactor] {} : factor={}, remainingLife={}%",
                        itemCode, String.format("%.3f", factor),
                        vc.getRemainingLife() != null ? String.format("%.1f", vc.getRemainingLife()) : "N/A");

                // 3-4. 잔존 수명 30% 이하 시 알림 발송
                if (vc.getRemainingLife() != null && vc.getRemainingLife() <= CONSUMABLE_ALERT_THRESHOLD) {
                    sendConsumableAlert(vehicle, vc);
                }

                vehicleConsumableRepository.save(vc);

            } catch (Exception e) {
                log.error("[WearFactor] {} 마모 계수 계산 실패: {}", itemCode, e.getMessage());
            }
        }

        log.info("[WearFactor] 규칙 기반 마모 계수 계산 완료 [Vehicle: {}]", trip.getVehicleId());
    }

    /**
     * 소모품 코드에 따라 적절한 계산 메서드를 호출합니다.
     * 공식이 없는 소모품은 factor=1.0(주행거리만 반영)으로 수명 차감.
     */
    private Double calculateFactorByItemCode(String itemCode, TripSummary trip,
            Vehicle vehicle, Double highRpmRatio, Double idleRatio) {
        return switch (itemCode) {
            case "TIRE_FL", "TIRE_FR", "TIRE_RL", "TIRE_RR" -> calculateTireFactor(trip);
            case "ENGINE_OIL" -> calculateEngineOilFactor(trip, highRpmRatio, idleRatio);
            case "COOLANT" -> calculateCoolantFactor(trip);
            case "AIR_FILTER" -> calculateAirFilterFactor(trip, vehicle);
            case "BRAKE_PAD_FRONT", "BRAKE_PAD_REAR" -> calculateBrakePadFactor(trip);
            case "BATTERY_12V" -> calculateBatteryFactor(trip, idleRatio);
            case "MISSION_OIL" -> calculateMissionOilFactor(trip);
            case "SPARK_PLUG" -> calculateSparkPlugFactor(trip, highRpmRatio, idleRatio);
            default -> 1.0;
        };
    }

    // ==================== 5개 마모 계수 계산 메서드 ====================

    /**
     * 1. 타이어 마모 계수 계산
     *
     * 공식: factor = 1.0 + (hard_accel + hard_brake) * 0.03
     * factor = min(factor, 3.0)
     * 미지원(속도 등 없음)이면 주행거리만 반영 → 1.0
     */
    private Double calculateTireFactor(TripSummary trip) {
        Integer hardAccelCount = trip.getHardAccelCount();
        Integer hardBrakeCount = trip.getHardBrakeCount();
        if (hardAccelCount == null && hardBrakeCount == null) {
            return 1.0;
        }
        if (hardAccelCount == null)
            hardAccelCount = 0;
        if (hardBrakeCount == null)
            hardBrakeCount = 0;

        double factor = 1.0 + (hardAccelCount + hardBrakeCount)
                * ConsumableConstants.TIRE_ACCEL_BRAKE_COEF;

        factor = Math.min(factor, ConsumableConstants.TIRE_MAX_FACTOR);

        return factor;
    }

    /**
     * 2. 엔진오일 마모 계수 계산
     *
     * 공식: cold_penalty = 1.5 if trip_distance < 5 else 1.0
     * rpm_penalty = 1.0 + high_rpm_ratio * 0.8
     * idle_penalty = 1.0 + idle_ratio * 0.5
     * factor = cold_penalty * rpm_penalty * idle_penalty
     * factor = min(factor, 2.5)
     * RPM 미지원(avgRpm null)이면 주행거리만 반영 → 1.0
     */
    private Double calculateEngineOilFactor(TripSummary trip, Double highRpmRatio, Double idleRatio) {
        if (trip.getAvgRpm() == null) {
            return 1.0;
        }
        // 1. Cold start penalty
        Double tripDistanceKm = trip.getDistance();
        double coldPenalty = (tripDistanceKm != null
                && tripDistanceKm < ConsumableConstants.COLD_START_THRESHOLD_KM)
                        ? ConsumableConstants.COLD_START_PENALTY
                        : 1.0;

        // 2. High RPM penalty (⭐ highRpmRatio 사용)
        if (highRpmRatio == null)
            highRpmRatio = 0.0;
        double rpmPenalty = 1.0 + highRpmRatio * ConsumableConstants.RPM_PENALTY_COEF;

        // 3. Idle penalty
        if (idleRatio == null)
            idleRatio = 0.0;
        double idlePenalty = 1.0 + idleRatio * ConsumableConstants.IDLE_PENALTY_COEF;

        // 4. Calculate factor
        double factor = coldPenalty * rpmPenalty * idlePenalty;

        // 5. Apply max cap
        factor = Math.min(factor, ConsumableConstants.ENGINE_OIL_MAX_FACTOR);

        return factor;
    }

    /**
     * 3. 냉각수 마모 계수 계산 (Arrhenius 방정식)
     *
     * 공식: overheat_damage = 2 ^ (max(0, max_coolant_temp - 90) / 10)
     * factor = overheat_damage
     * 냉각수 온도 미지원(null 또는 0 이하)이면 주행거리만 반영 → 1.0
     */
    private Double calculateCoolantFactor(TripSummary trip) {
        Double maxCoolantTemp = trip.getMaxCoolantTemp();
        if (maxCoolantTemp == null || maxCoolantTemp <= ConsumableConstants.COOLANT_NORMAL_TEMP) {
            return 1.0;
        }

        double tempExcess = Math.max(0, maxCoolantTemp - ConsumableConstants.COOLANT_NORMAL_TEMP);

        double factor = Math.pow(
                ConsumableConstants.COOLANT_ARRHENIUS_BASE,
                tempExcess / ConsumableConstants.COOLANT_TEMP_DIVISOR);
        return Math.min(factor, ConsumableConstants.COOLANT_MAX_FACTOR);
    }

    /**
     * 4. 에어필터 마모 계수 계산
     *
     * 공식: efficiency = avg_maf / (baseline_maf * avg_throttle)
     * factor = 1.5 ^ (max(0, 1.0 - efficiency) / 0.1)
     *
     * NOTE: avgThrottlePos는 0~100 범위이므로 0~1로 정규화합니다.
     */
    private Double calculateAirFilterFactor(TripSummary trip, Vehicle vehicle) {
        Double avgMaf = trip.getAvgMaf();
        Double avgThrottle = trip.getAvgThrottlePos();

        // MAF/스로틀 미지원이면 주행거리만 반영
        if (avgMaf == null || avgThrottle == null) {
            return 1.0;
        }

        String vehicleModel = vehicle.getModelNameKo();
        Double baselineMaf = ConsumableConstants.getBaselineMaf(vehicleModel);

        // 스로틀 정규화 (0~100 → 0~1)
        double throttleNormalized = avgThrottle;
        if (avgThrottle > 1.0) {
            throttleNormalized = avgThrottle / 100.0;
        }

        // 0으로 나누기 방지 → 주행거리만 반영
        if (throttleNormalized <= 0.0 || baselineMaf <= 0.0) {
            return 1.0;
        }

        // 효율 계산
        double efficiency = avgMaf / (baselineMaf * throttleNormalized);

        // 효율 손실
        double efficiencyLoss = Math.max(0, 1.0 - efficiency);

        // 지수 함수 계수
        double factor = Math.pow(
                ConsumableConstants.AIR_FILTER_EFFICIENCY_BASE,
                efficiencyLoss / ConsumableConstants.AIR_FILTER_EFFICIENCY_DIVISOR);
        return Math.min(factor, ConsumableConstants.AIR_FILTER_MAX_FACTOR);
    }

    /**
     * 5. 브레이크패드 마모 계수 계산
     *
     * 공식: brake_energy = hard_brake_count * (avg_speed ^ 2) / 10000
     * city_mult = 1.3 if avg_speed < 30 else 1.0
     * factor = (1.0 + brake_energy) * city_mult
     * 속도 미지원(avgSpeed null)이면 주행거리만 반영 → 1.0
     */
    private Double calculateBrakePadFactor(TripSummary trip) {
        Integer hardBrakeCount = trip.getHardBrakeCount();
        Double avgSpeed = trip.getAverageSpeed();
        if (avgSpeed == null) {
            return 1.0;
        }
        if (hardBrakeCount == null)
            hardBrakeCount = 0;

        // 브레이크 에너지 (속도 제곱에 비례)
        double brakeEnergy = hardBrakeCount * Math.pow(avgSpeed, 2)
                / ConsumableConstants.BRAKE_ENERGY_DIVISOR;

        // 시내 주행 배수
        double cityMult = (avgSpeed < ConsumableConstants.CITY_SPEED_THRESHOLD)
                ? ConsumableConstants.CITY_MULT
                : 1.0;

        double factor = (1.0 + brakeEnergy) * cityMult;
        return Math.min(factor, ConsumableConstants.BRAKE_PAD_MAX_FACTOR);
    }

    /**
     * 6. 12V 배터리 마모 계수 계산
     *
     * 저전압·짧은 주행(부분충전)·공회전 비율로 보정.
     * 전압 미지원(minBatteryVoltage null)이면 주행거리만 반영 → 1.0
     */
    private Double calculateBatteryFactor(TripSummary trip, Double idleRatio) {
        Double minVoltage = trip.getMinBatteryVoltage();
        if (minVoltage == null) {
            return 1.0;
        }
        double factor = 1.0;
        if (minVoltage > 0 && minVoltage < ConsumableConstants.BATTERY_LOW_VOLTAGE_THRESHOLD) {
            factor *= ConsumableConstants.BATTERY_LOW_VOLTAGE_PENALTY;
        }
        Double distance = trip.getDistance();
        if (distance != null && distance > 0 && distance < ConsumableConstants.BATTERY_SHORT_TRIP_THRESHOLD_KM) {
            factor *= ConsumableConstants.BATTERY_SHORT_TRIP_PENALTY;
        }
        if (idleRatio != null && idleRatio > 0) {
            factor *= (1.0 + idleRatio * ConsumableConstants.BATTERY_IDLE_PENALTY_COEF);
        }
        return Math.min(factor, ConsumableConstants.BATTERY_MAX_FACTOR);
    }

    /**
     * 7. 미션 오일 마모 계수 계산
     *
     * 고온·고부하 시 열화 가속. max_coolant_temp(트랜스 열부하 대리), max_engine_load 사용.
     * 둘 다 null이면 주행거리만 반영 → 1.0
     */
    private Double calculateMissionOilFactor(TripSummary trip) {
        Double maxCoolantTemp = trip.getMaxCoolantTemp();
        Double maxEngineLoad = trip.getMaxEngineLoad();
        if (maxCoolantTemp == null && maxEngineLoad == null) {
            return 1.0;
        }
        double factor = 1.0;
        if (maxCoolantTemp != null && maxCoolantTemp > ConsumableConstants.MISSION_OIL_TEMP_THRESHOLD) {
            double excess = maxCoolantTemp - ConsumableConstants.MISSION_OIL_TEMP_THRESHOLD;
            factor += excess * ConsumableConstants.MISSION_OIL_TEMP_PENALTY_COEF;
        }
        if (maxEngineLoad != null && maxEngineLoad > ConsumableConstants.MISSION_OIL_LOAD_THRESHOLD) {
            double excess = maxEngineLoad - ConsumableConstants.MISSION_OIL_LOAD_THRESHOLD;
            factor += excess * ConsumableConstants.MISSION_OIL_LOAD_PENALTY_COEF;
        }
        return Math.min(factor, ConsumableConstants.MISSION_OIL_MAX_FACTOR);
    }

    /**
     * 8. 스파크 플러그 마모 계수 계산
     *
     * 고RPM·고부하 구간 비율로 점화 부담 반영.
     * RPM 미지원(avgRpm null)이면 주행거리만 반영 → 1.0
     */
    private Double calculateSparkPlugFactor(TripSummary trip, Double highRpmRatio, Double idleRatio) {
        if (trip.getAvgRpm() == null) {
            return 1.0;
        }
        if (highRpmRatio == null) {
            highRpmRatio = 0.0;
        }
        Double avgLoad = trip.getAvgEngineLoad();
        if (avgLoad == null) {
            avgLoad = 0.0;
        }
        double rpmPenalty = 1.0 + highRpmRatio * ConsumableConstants.SPARK_PLUG_RPM_PENALTY_COEF;
        double loadPenalty = 1.0 + avgLoad * ConsumableConstants.SPARK_PLUG_LOAD_PENALTY_COEF; // avgLoad 0~100
        double factor = rpmPenalty * loadPenalty;
        if (idleRatio != null && idleRatio > 0) {
            factor *= (1.0 + idleRatio * 0.2);
        }
        return Math.min(factor, ConsumableConstants.SPARK_PLUG_MAX_FACTOR);
    }

    // ==================== 헬퍼 메서드 ====================

    /**
     * 공회전 비율을 계산합니다.
     * idleRatio = idleTime(초) / totalDuration(초)
     */
    private Double calculateIdleRatio(TripSummary trip) {
        if (trip.getStartTime() == null || trip.getEndTime() == null) {
            return 0.0;
        }

        long durationSec = Duration.between(trip.getStartTime(), trip.getEndTime()).toSeconds();
        if (durationSec <= 0) {
            return 0.0;
        }

        int idleTime = trip.getIdleTime() != null ? trip.getIdleTime() : 0;
        double idleRatio = (double) idleTime / durationSec;

        // 비율은 0.0 ~ 1.0 사이로 제한
        return Math.min(1.0, Math.max(0.0, idleRatio));
    }

    /**
     * 마모 계수로부터 잔여 주행거리를 계산합니다.
     */
    private int calculateRemainingKm(Double wearFactor, int replacementCycle) {
        if (wearFactor == null || wearFactor >= 1.0)
            return 0;
        return (int) ((1.0 - wearFactor) * replacementCycle);
    }

    /**
     * 마모 상태에 따른 사유 코드를 생성합니다.
     */
    private String generateReasonCode(String itemCode, Double wearFactor) {
        if (wearFactor == null)
            return "UNKNOWN";
        if (wearFactor < 0.5)
            return "NORMAL";
        if (wearFactor < 0.8)
            return "MODERATE_WEAR";
        return "HIGH_WEAR";
    }

    // ==================== 보존 메서드 (기존 코드 AS-IS) ====================

    /**
     * 소모품 코드에 해당하는 ConsumableItem이 없을 경우 기본 VehicleConsumable 생성
     * [PRESERVED] 원본 Line 146-159
     */
    private VehicleConsumable createDefaultMapping(Vehicle vehicle, String itemCode, Double currentTotalMileage) {
        return consumableItemRepository.findByCode(itemCode)
                .map(item -> {
                    VehicleConsumable vc = new VehicleConsumable();
                    vc.setVehicle(vehicle);
                    vc.setConsumableItem(item);
                    vc.setWearFactor(1.0);
                    // 초기 생성 시: 사용자가 현재 시점부터 관리한다고 가정하고 수명 100%
                    vc.setLastReplacedMileage(currentTotalMileage);
                    vc.setRemainingLife(100.0);
                    return vc;
                })
                .orElse(null);
    }

    /**
     * [PRESERVED] 증분 수명 차감 로직
     * 남은 수명 -= (이번 주행 거리 * 마모계수 / 전체 수명 주기) * 100
     * 원본 Line 161-183
     */
    private void updateRemainingLifeIncremental(VehicleConsumable vc, double tripDistance) {
        if (tripDistance <= 0)
            return;

        Integer interval = vc.getConsumableItem().getDefaultIntervalMileage();
        if (interval == null || interval <= 0)
            return;

        double currentLife = vc.getRemainingLife() != null ? vc.getRemainingLife() : 100.0;
        double wearFactor = vc.getWearFactor() != null ? vc.getWearFactor() : 1.0;

        // 마모된 거리 (가중치 적용)
        double wornDistance = tripDistance * wearFactor;

        // 수명 감소량 (%)
        double lifeDecreasePercent = (wornDistance / interval) * 100.0;

        // 최종 수명 계산 (0% 미만 방지)
        double newLife = Math.max(0.0, currentLife - lifeDecreasePercent);

        vc.updateRemainingLife(newLife);
    }

    /**
     * [PRESERVED] 소모품 수명 임계치 도달 시 FCM 알림 발송
     * 원본 Line 185-207
     */
    private void sendConsumableAlert(Vehicle vehicle, VehicleConsumable vc) {
        User owner = userRepository.findById(vehicle.getUserId()).orElse(null);
        if (owner == null) {
            log.warn("[WearFactor] 차량 소유자 없음, 알림 스킵: {}", vehicle.getVehicleId());
            return;
        }

        String itemName = vc.getConsumableItem().getName();
        String vehicleName = vehicle.getModelNameKo() != null ? vehicle.getModelNameKo() : "차량";
        double remainingLife = vc.getRemainingLife();

        String title = "[소모품 교체 알림] " + itemName;
        String body = String.format("%s %s 잔존 수명이 %.0f%%입니다. 정비를 권장합니다.",
                vehicleName, itemName, remainingLife);

        notificationService.sendNotification(owner, title, body, NotificationType.MAINTENANCE_ALERT);

        log.info("[WearFactor] 소모품 알림 발송: {} -> {} ({}%)",
                owner.getNickname(), itemName, remainingLife);
    }
}
