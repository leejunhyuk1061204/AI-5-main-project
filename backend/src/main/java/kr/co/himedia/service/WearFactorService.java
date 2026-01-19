package kr.co.himedia.service;

import org.springframework.scheduling.annotation.Async;
import kr.co.himedia.dto.maintenance.ai.AiWearFactorRequest;
import kr.co.himedia.dto.maintenance.ai.AiWearFactorResponse;
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

    private final VehicleRepository vehicleRepository;
    private final VehicleConsumableRepository vehicleConsumableRepository;
    private final kr.co.himedia.repository.TripSummaryRepository tripSummaryRepository;
    private final ConsumableItemRepository consumableItemRepository;
    private final AiClient aiClient;

    /**
     * 운행 종료 시 호출 - 해당 차량의 모든 AI 지원 소모품에 대해 마모율 일괄 계산 (비동기 처리)
     */
    @Async
    @Transactional
    public void calculateAndSaveWearFactors(UUID vehicleId, Double currentTotalMileage) {
        log.info("[WearFactor] 마모율 일괄 계산 시작 [Vehicle: {}, Mileage: {}]", vehicleId, currentTotalMileage);

        Vehicle vehicle = vehicleRepository.findById(vehicleId)
                .orElseThrow(() -> new RuntimeException("차량을 찾을 수 없습니다: " + vehicleId));

        // 1. 공통 데이터 준비 (운전 습관 및 메타데이터)
        AiWearFactorRequest.DrivingHabits habits = getRecentDrivingHabits(vehicle.getVehicleId());
        AiWearFactorRequest commonRequest = AiWearFactorRequest.builder()
                .vehicleMetadata(AiWearFactorRequest.VehicleMetadata.builder()
                        .modelYear(vehicle.getModelYear() != null ? vehicle.getModelYear() : 2023)
                        .fuelType(vehicle.getFuelType() != null ? vehicle.getFuelType().name() : "GASOLINE")
                        .totalMileage(currentTotalMileage.intValue()) // Use passed mileage
                        .build())
                .drivingHabits(habits)
                .build();

        // 2. AI 서버 일괄 요청
        try {
            AiWearFactorResponse response = aiClient.getWearFactor(commonRequest);
            if (response != null && response.getWearFactors() != null) {
                updateAllFactors(vehicle, response.getWearFactors(), currentTotalMileage);
            }
        } catch (Exception e) {
            log.error("[WearFactor] 일괄 마모율 계산 실패: {}", e.getMessage());
        }

        log.info("[WearFactor] 마모율 일괄 계산 프로세스 종료 [Vehicle: {}]", vehicleId);
    }

    @Transactional
    public void updateAllFactors(Vehicle vehicle, java.util.Map<String, Double> factors, Double currentTotalMileage) {
        // 거리 정보는 로깅용으로만 조회 (실제 계산은 TotalMileage 사용)
        Double tripDistanceKm = tripSummaryRepository.findLatestTripByVehicleId(vehicle.getVehicleId())
                .map(kr.co.himedia.entity.TripSummary::getDistance)
                .orElse(0.0);

        // double currentTotalMileage = vehicle.getTotalMileage(); // REMOVED: Use
        // passed value

        for (java.util.Map.Entry<String, Double> entry : factors.entrySet()) {
            String itemCode = entry.getKey();
            Double wearFactor = entry.getValue();

            try {
                // 1. 매핑 테이블 조회 (ConsumableItem Code 기준)
                VehicleConsumable vehicleConsumable = vehicleConsumableRepository
                        .findByVehicleAndConsumableItem_Code(vehicle, itemCode)
                        .orElse(null);

                // 2. 없으면 생성 (마스터 데이터 참조)
                if (vehicleConsumable == null) {
                    vehicleConsumable = createDefaultMapping(vehicle, itemCode, currentTotalMileage);
                }

                if (vehicleConsumable == null) {
                    log.warn("[WearFactor] 유효하지 않은 소모품 코드(Master 없음): {}", itemCode);
                    continue;
                }

                // 3. 마모율 업데이트
                vehicleConsumable.setWearFactor(wearFactor);

                // 4. 잔존 수명 재계산 및 업데이트 (캐싱)
                updateRemainingLife(vehicleConsumable, currentTotalMileage);

                vehicleConsumableRepository.save(vehicleConsumable);
                log.info("[WearFactor] Updated {}: factor={}, remainingLife={}%", itemCode, wearFactor,
                        vehicleConsumable.getRemainingLife());

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
                    // 초기 생성 시: 사용자가 현재 시점부터 관리한다고 가정하고 수명 100% (LastReplaced = CurrentMileage)
                    vc.setLastReplacedMileage(currentTotalMileage);
                    vc.setRemainingLife(100.0);
                    return vc;
                })
                .orElse(null);
    }

    private void updateRemainingLife(VehicleConsumable vc, double currentTotalMileage) {
        double lastReplaced = vc.getLastReplacedMileage() != null ? vc.getLastReplacedMileage() : 0.0;
        double distanceDriven = currentTotalMileage - lastReplaced;
        if (distanceDriven < 0)
            distanceDriven = 0; // 역전 방지

        // 거리 보정 (마모율 적용)
        double adjustedDistance = distanceDriven * vc.getWearFactor();

        // 표준 교체 주기
        int defaultInterval = vc.getConsumableItem().getDefaultIntervalMileage();

        // 수명 계산 (%)
        double lifePercentage = 100.0 - (adjustedDistance / defaultInterval * 100.0);

        // 잔존 수명 업데이트
        vc.updateRemainingLife(lifePercentage);
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
