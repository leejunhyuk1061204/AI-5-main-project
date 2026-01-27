package kr.co.himedia.service;

import org.springframework.scheduling.annotation.Async;
import kr.co.himedia.dto.maintenance.ai.AiWearFactorRequest;
import kr.co.himedia.dto.maintenance.ai.AiWearFactorResponse;
import kr.co.himedia.entity.Notification.NotificationType;
import kr.co.himedia.entity.User;
import kr.co.himedia.entity.Vehicle;
import kr.co.himedia.entity.VehicleConsumable;
import kr.co.himedia.repository.VehicleConsumableRepository;
import kr.co.himedia.repository.VehicleRepository;
import kr.co.himedia.repository.ConsumableItemRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.UUID;

@Slf4j
@Service
@RequiredArgsConstructor
public class WearFactorService {

    private static final double CONSUMABLE_ALERT_THRESHOLD = 15.0;

    private final VehicleRepository vehicleRepository;
    private final VehicleConsumableRepository vehicleConsumableRepository;
    private final kr.co.himedia.repository.TripSummaryRepository tripSummaryRepository;
    private final ConsumableItemRepository consumableItemRepository;
    private final AiClient aiClient;
    private final NotificationService notificationService;
    private final kr.co.himedia.repository.UserRepository userRepository;

    /**
     * 운행 종료 시 호출 - 해당 차량의 모든 AI 지원 소모품에 대해 마모율 일괄 계산 (비동기 처리)
     * [Modified] 증분 업데이트를 위해 tripDistance 추가
     */
    @Async
    @Transactional
    public void calculateAndSaveWearFactors(UUID vehicleId, Double currentTotalMileage, Double tripDistance) {
        log.info("[WearFactor] 마모율 일괄 계산 시작 [Vehicle: {}, Mileage: {}, Trip: {}]", vehicleId, currentTotalMileage,
                tripDistance);

        Vehicle vehicle = vehicleRepository.findById(vehicleId)
                .orElseThrow(() -> new RuntimeException("차량을 찾을 수 없습니다: " + vehicleId));

        // 1. 해당 차량의 모든 소모품 컨텍스트 빌드
        List<VehicleConsumable> allConsumables = vehicleConsumableRepository.findByVehicle(vehicle);
        List<AiWearFactorRequest.ConsumableContext> consumableContexts = allConsumables.stream()
                .map(vc -> AiWearFactorRequest.ConsumableContext.builder()
                        .code(vc.getConsumableItem().getCode())
                        .lastReplacedMileage(vc.getLastReplacedMileage() != null ? vc.getLastReplacedMileage() : 0.0)
                        .isInferred(vc.getIsInferred() != null ? vc.getIsInferred() : false) // [Fix] 기본적으로 false 취급하여
                                                                                             // 안정성 확보
                        .build())
                .collect(java.util.stream.Collectors.toList());

        // 2. 공통 데이터 준비 (운전 습관 및 메타데이터)
        AiWearFactorRequest.DrivingHabits habits = getRecentDrivingHabits(vehicle.getVehicleId());
        AiWearFactorRequest request = AiWearFactorRequest.builder()
                .vehicleMetadata(AiWearFactorRequest.VehicleMetadata.builder()
                        .modelYear(vehicle.getModelYear() != null ? vehicle.getModelYear() : 2023)
                        .fuelType(vehicle.getFuelType() != null ? vehicle.getFuelType().name() : "GASOLINE")
                        .totalMileage(currentTotalMileage.intValue())
                        .build())
                .drivingHabits(habits)
                .consumables(consumableContexts)
                .build();

        // 3. AI 서버 일괄 요청
        try {
            AiWearFactorResponse response = aiClient.getWearFactor(request);
            if (response != null && response.getWearFactors() != null) {
                updateAllFactors(vehicle, response, currentTotalMileage, tripDistance);
            }
        } catch (Exception e) {
            log.error("[WearFactor] 일괄 마모율 계산 실패: {}", e.getMessage());
        }

        log.info("[WearFactor] 마모율 일괄 계산 프로세스 종료 [Vehicle: {}]", vehicleId);
    }

    /**
     * AI 응답에 따른 소모품 상태 업데이트
     * [Fix] is_inferred 여부와 무관하게 모든 항목에 대해 '증분(Incremental)' 업데이트 적용
     * AI의 절대 수명 예측값(remainingLifes)은 사용하지 않음 (안정성 문제 해소)
     */
    @Transactional
    public void updateAllFactors(Vehicle vehicle, AiWearFactorResponse response, Double currentTotalMileage,
            Double tripDistance) {
        java.util.Map<String, Double> wearFactors = response.getWearFactors();
        java.util.Map<String, Double> remainingLifes = response.getRemainingLifes();

        for (java.util.Map.Entry<String, Double> entry : wearFactors.entrySet()) {
            String itemCode = entry.getKey();
            Double wearFactor = entry.getValue();

            try {
                VehicleConsumable vehicleConsumable = vehicleConsumableRepository
                        .findByVehicleAndConsumableItem_Code(vehicle, itemCode)
                        .orElse(null);

                if (vehicleConsumable == null) {
                    vehicleConsumable = createDefaultMapping(vehicle, itemCode, currentTotalMileage);
                }

                if (vehicleConsumable == null) {
                    log.warn("[WearFactor] 유효하지 않은 소모품 코드(Master 없음): {}", itemCode);
                    continue;
                }

                // 마모율 업데이트
                vehicleConsumable.setWearFactor(wearFactor);

                // [Fix] is_inferred 여부에 따른 분기 처리
                // true: AI 예측값으로 덮어쓰기 (사용자 요청 사항)
                // false: 증분 업데이트 (안정성 확보)
                Boolean isInferred = vehicleConsumable.getIsInferred();
                if (isInferred != null && isInferred && remainingLifes != null
                        && remainingLifes.containsKey(itemCode)) {
                    Double aiLife = remainingLifes.get(itemCode);
                    vehicleConsumable.updateRemainingLife(aiLife);
                    log.info("[WearFactor] 보정 모드(Inferred) - {}: AI 수명 덮어쓰기={}%", itemCode, aiLife);
                } else {
                    updateRemainingLifeIncremental(vehicleConsumable, tripDistance);
                    log.info("[WearFactor] 증분 모드(Standard) - {}: 차감 반영 완료 (Factor={})", itemCode, wearFactor);
                }

                // 잔존 수명 15% 이하 시 알림 발송
                if (vehicleConsumable.getRemainingLife() != null
                        && vehicleConsumable.getRemainingLife() <= CONSUMABLE_ALERT_THRESHOLD) {
                    sendConsumableAlert(vehicle, vehicleConsumable);
                }

                vehicleConsumableRepository.save(vehicleConsumable);

            } catch (Exception e) {
                log.error("Failed to process wear factor for " + itemCode, e);
            }
        }
    }

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
     * [New] 증분 수명 차감 로직
     * 남은 수명 -= (이번 주행 거리 * 마모계수 / 전체 수명 주기) * 100
     */
    private void updateRemainingLifeIncremental(VehicleConsumable vc, double tripDistance) {
        if (tripDistance <= 0)
            return;

        double currentLife = vc.getRemainingLife() != null ? vc.getRemainingLife() : 100.0;
        int defaultInterval = vc.getConsumableItem().getDefaultIntervalMileage();
        double wearFactor = vc.getWearFactor() != null ? vc.getWearFactor() : 1.0;

        // 마모된 거리 (가중치 적용)
        double wornDistance = tripDistance * wearFactor;

        // 수명 감소량 (%)
        double lifeDecreasePercent = (wornDistance / defaultInterval) * 100.0;

        // 최종 수명 계산 (0% 미만 방지)
        double newLife = Math.max(0.0, currentLife - lifeDecreasePercent);

        vc.updateRemainingLife(newLife);
    }

    /**
     * 소모품 수명 임계치 도달 시 FCM 알림 발송
     */
    private void sendConsumableAlert(Vehicle vehicle, VehicleConsumable vc) {
        User owner = userRepository.findById(vehicle.getUserId()).orElse(null);
        if (owner == null) {
            log.warn("[WearFactor] 차량 소유자 없음, 알림 스킵: {}", vehicle.getVehicleId());
            return;
        }

        String itemName = vc.getConsumableItem().getName();
        String vehicleName = vehicle.getModelName() != null ? vehicle.getModelName() : "차량";
        double remainingLife = vc.getRemainingLife();

        String title = "[소모품 교체 알림] " + itemName;
        String body = String.format("%s %s 잔존 수명이 %.0f%%입니다. 정비를 권장합니다.",
                vehicleName, itemName, remainingLife);

        notificationService.sendNotification(owner, title, body, NotificationType.MAINTENANCE_ALERT);

        log.info("[WearFactor] 소모품 알림 발송: {} -> {} ({}%)",
                owner.getNickname(), itemName, remainingLife);
    }

    private AiWearFactorRequest.DrivingHabits getRecentDrivingHabits(UUID vehicleId) {
        try {
            List<kr.co.himedia.entity.TripSummary> recentTrips = tripSummaryRepository
                    .findByVehicleIdOrderByStartTimeDesc(vehicleId);
            if (recentTrips.isEmpty()) {
                return AiWearFactorRequest.DrivingHabits.builder()
                        .avgRpm(2000.0).hardAccelCount(0).hardBrakeCount(0).idleRatio(0.1).build();
            }

            // 최대 5개 계산
            int limit = Math.min(recentTrips.size(), 5);
            double sumScore = 0;
            double sumSpeed = 0;

            for (int i = 0; i < limit; i++) {
                kr.co.himedia.entity.TripSummary trip = recentTrips.get(i);
                sumScore += (trip.getDriveScore() != null ? trip.getDriveScore() : 100);
                sumSpeed += (trip.getAverageSpeed() != null ? trip.getAverageSpeed() : 0);
            }

            double avgScore = sumScore / limit;
            double avgSpeed = sumSpeed / limit;

            // Heuristic conversion
            int estimatedHardEvents = (int) ((100.0 - avgScore) / 5.0);

            return AiWearFactorRequest.DrivingHabits.builder()
                    .avgRpm(2000.0 + (100 - avgScore) * 50)
                    .hardAccelCount(Math.max(0, estimatedHardEvents / 2))
                    .hardBrakeCount(Math.max(0, estimatedHardEvents / 2))
                    .idleRatio(0.1)
                    .build();
        } catch (Exception e) {
            log.warn("Failed to calculate driving habits, using defaults", e);
            return AiWearFactorRequest.DrivingHabits.builder()
                    .avgRpm(2000.0).hardAccelCount(0).hardBrakeCount(0).idleRatio(0.1).build();
        }
    }
}
