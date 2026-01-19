package kr.co.himedia.service;

import org.springframework.scheduling.annotation.Async;
import kr.co.himedia.dto.maintenance.ai.AiWearFactorRequest;
import kr.co.himedia.dto.maintenance.ai.AiWearFactorResponse;
import kr.co.himedia.entity.ConsumableItem;
import kr.co.himedia.entity.MaintenanceHistory;
import kr.co.himedia.entity.MaintenanceItem;
import kr.co.himedia.entity.Vehicle;
import kr.co.himedia.entity.VehicleConsumable;
import kr.co.himedia.repository.ConsumableItemRepository;
import kr.co.himedia.repository.MaintenanceHistoryRepository;
import kr.co.himedia.repository.VehicleConsumableRepository;
import kr.co.himedia.repository.VehicleRepository;
import kr.co.himedia.service.AiClient;
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

    private final VehicleRepository vehicleRepository;
    private final VehicleConsumableRepository vehicleConsumableRepository;
    private final ConsumableItemRepository consumableItemRepository;
    private final MaintenanceHistoryRepository maintenanceHistoryRepository;
    private final kr.co.himedia.repository.TripSummaryRepository tripSummaryRepository;
    private final FcmService fcmService;
    private final UserService userService;
    private final AiClient aiClient;

    // AI 마모율 계산 지원 소모품 목록 (Hardcoded for now, or could be a flag in DB)
    private static final List<String> AI_SUPPORTED_CODES = List.of(
            "ENGINE_OIL",
            "TIRE",
            "BRAKE_PAD");

    /**
     * 운행 종료 시 호출 - 해당 차량의 모든 AI 지원 소모품에 대해 마모율 계산 (비동기 처리)
     */
    @Async
    @Transactional
    public void calculateAndSaveWearFactors(UUID vehicleId) {
        log.info("[WearFactor] 마모율 계산 시작 [Vehicle: {}]", vehicleId);

        Vehicle vehicle = vehicleRepository.findById(vehicleId)
                .orElseThrow(() -> new RuntimeException("차량을 찾을 수 없습니다: " + vehicleId));

        for (String code : AI_SUPPORTED_CODES) {
            consumableItemRepository.findByCode(code).ifPresent(item -> {
                try {
                    calculateAndSaveForItem(vehicle, item);
                } catch (Exception e) {
                    log.error("[WearFactor] {} 마모율 계산 실패: {}", code, e.getMessage());
                }
            });
        }

        log.info("[WearFactor] 마모율 계산 완료 [Vehicle: {}]", vehicleId);
    }

    private void calculateAndSaveForItem(Vehicle vehicle, ConsumableItem item) {
        // 해당 소모품 상태 조회 (없으면 생성)
        VehicleConsumable consumable = vehicleConsumableRepository
                .findByVehicleAndConsumableItem(vehicle, item)
                .orElseGet(() -> createDefaultConsumable(vehicle, item));

        // 마지막 정비 이력 조회
        MaintenanceHistory lastHistory = maintenanceHistoryRepository
                .findTopByVehicleAndConsumableItemOrderByMaintenanceDateDesc(vehicle, item)
                .orElse(null);

        // 운전 습관 데이터 조회 (최근 5회 주행 평균)
        AiWearFactorRequest.DrivingHabits habits = getRecentDrivingHabits(vehicle.getVehicleId());

        // AI 요청 생성
        AiWearFactorRequest request = AiWearFactorRequest.builder()
                .targetItem(mapToAiItem(item.getCode()))
                .lastReplaced(AiWearFactorRequest.LastReplaced.builder()
                        .date(lastHistory != null ? lastHistory.getMaintenanceDate()
                                : java.time.LocalDate.now().minusYears(1))
                        .mileage(lastHistory != null ? lastHistory.getMileageAtMaintenance().intValue() : 0)
                        .build())
                .vehicleMetadata(AiWearFactorRequest.VehicleMetadata.builder()
                        .modelYear(vehicle.getModelYear() != null ? vehicle.getModelYear() : 2023)
                        .fuelType(vehicle.getFuelType() != null ? vehicle.getFuelType().name() : "GASOLINE")
                        .totalMileage(vehicle.getTotalMileage().intValue())
                        .build())
                .drivingHabits(habits)
                .build();

        // AI 서버 호출
        AiWearFactorResponse response = aiClient.getWearFactor(request);

        if (response != null && response.getPredictedWearFactor() != null) {
            consumable.updateWearFactor(response.getPredictedWearFactor());
            vehicleConsumableRepository.save(consumable);
            log.info("[WearFactor] {} 마모율 저장 완료: {}", item.getName(), response.getPredictedWearFactor());

            // 소모품 교체 알림 체크
            checkAndSendNotification(vehicle, item, consumable, lastHistory);
        }
    }

    private AiWearFactorRequest.DrivingHabits getRecentDrivingHabits(UUID vehicleId) {
        // 최근 5개 주행 기록 조회 (Repository에 메소드가 없다면 상위 서비스에서 가져오거나, 여기서 Repository 사용)
        // TripSummaryRepository가 필요함. 필드에 추가해야 함.
        try {
            List<kr.co.himedia.entity.TripSummary> recentTrips = tripSummaryRepository
                    .findByVehicleIdOrderByStartTimeDesc(vehicleId);
            if (recentTrips.isEmpty()) {
                return AiWearFactorRequest.DrivingHabits.builder()
                        .avgRpm(2000.0).hardAccelCount(0).hardBrakeCount(0).idleRatio(0.1).build();
            }

            // 최대 5개만 계산
            int limit = Math.min(recentTrips.size(), 5);
            double sumScore = 0;
            double sumSpeed = 0;

            for (int i = 0; i < limit; i++) {
                kr.co.himedia.entity.TripSummary trip = recentTrips.get(i);
                sumScore += (trip.getDriveScore() != null ? trip.getDriveScore() : 100);
                sumSpeed += (trip.getAverageSpeed() != null ? trip.getAverageSpeed() : 0);
            }

            double avgScore = sumScore / limit; // 100점 만점
            double avgSpeed = sumSpeed / limit;

            // Heuristic conversion: 점수가 낮을수록 급가속/급감속이 많았다고 가정
            int estimatedHardEvents = (int) ((100.0 - avgScore) / 5.0); // ex: 80점 -> 4회

            return AiWearFactorRequest.DrivingHabits.builder()
                    .avgRpm(avgSpeed * 50) // Speed to RPM rough estimation if RPM not avail (or use placeholder 2000 if
                                           // totally unknown)
                    // 사실 RPM 데이터가 있다면 좋겠지만, TripSummary에 RPM 평균이 없다면 log에서 가져오긴 너무 무거움.
                    // 임시로 '2000' 기본값 대신 조금 더 그럴싸한 값(속도 * ratio) 혹은 그냥 2000 유지.
                    // 여기서는 avgSpeed * 30 + 1000 정도로 단순 처리하거나 고정값 2000 사용.
                    // 사용자가 "꼼수 코드 고쳐"라고 했으므로 최대한 있는 데이터 활용.
                    // TripSummary에 DriveScore가 있으므로 이를 활용.
                    .avgRpm(2000.0 + (100 - avgScore) * 50) // 점수가 낮으면(운전 거칠면) RPM 높게 추정
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

    private void checkAndSendNotification(Vehicle vehicle, ConsumableItem item, VehicleConsumable vc,
            MaintenanceHistory lastHistory) {
        try {
            double currentMileage = vehicle.getTotalMileage();
            double lastMileage = (lastHistory != null && lastHistory.getMileageAtMaintenance() != null)
                    ? lastHistory.getMileageAtMaintenance()
                    : 0.0;

            double interval = (vc.getCustomIntervalMileage() != null) ? vc.getCustomIntervalMileage()
                    : (item.getDefaultIntervalMileage() != null ? item.getDefaultIntervalMileage() : 10000.0);

            double wearFactor = vc.getWearFactor() != null ? vc.getWearFactor() : 1.0;
            double usedMileage = (currentMileage - lastMileage) * wearFactor;

            double remainingPct = 100.0 - (usedMileage / interval * 100.0);

            if (remainingPct < 15.0) { // 15% 미만 시 알림 (좀 더 여유있게)
                String fcmToken = userService.getFcmToken(vehicle.getUserId());
                if (fcmToken != null) {
                    String title = "소모품 교체 요망";
                    String body = String.format("%s 수명이 약 %.1f%% 남았습니다. 정비를 예약하세요.", item.getName(), remainingPct);

                    java.util.Map<String, String> data = new java.util.HashMap<>();
                    data.put("type", "CONSUMABLE_ALERT");
                    data.put("itemCode", item.getCode());

                    fcmService.sendMessage("User-" + vehicle.getUserId(), fcmToken, title, body, data);
                    log.info("Sent Consumable Alert for {} [Vehicle: {}]", item.getCode(), vehicle.getVehicleId());
                }
            }
        } catch (Exception e) {
            log.error("Failed to send consumable alert", e);
        }
    }

    private VehicleConsumable createDefaultConsumable(Vehicle vehicle, ConsumableItem item) {
        VehicleConsumable consumable = VehicleConsumable.builder()
                .vehicle(vehicle)
                .consumableItem(item)
                .wearFactor(1.0)
                .build();
        return vehicleConsumableRepository.save(consumable);
    }

    private String mapToAiItem(String code) {
        return switch (code) {
            case "ENGINE_OIL" -> "ENGINE_OIL";
            case "TIRE" -> "TIRES";
            case "BRAKE_PAD" -> "BRAKE_PADS";
            default -> throw new IllegalArgumentException("AI 미지원 소모품: " + code);
        };
    }
}
