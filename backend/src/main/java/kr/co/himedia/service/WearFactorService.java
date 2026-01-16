// 운행 종료 시 XGBoost 마모율 계산 및 저장 서비스
package kr.co.himedia.service;

import kr.co.himedia.dto.maintenance.ai.AiWearFactorRequest;
import kr.co.himedia.dto.maintenance.ai.AiWearFactorResponse;
import kr.co.himedia.entity.MaintenanceItem;
import kr.co.himedia.entity.Vehicle;
import kr.co.himedia.entity.VehicleConsumable;
import kr.co.himedia.repository.VehicleConsumableRepository;
import kr.co.himedia.repository.VehicleRepository;
import kr.co.himedia.service.ai.AiClient;
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
    private final AiClient aiClient;

    // AI 마모율 계산 지원 소모품 목록
    private static final List<MaintenanceItem> AI_SUPPORTED_ITEMS = List.of(
            MaintenanceItem.ENGINE_OIL,
            MaintenanceItem.TIRE,
            MaintenanceItem.BRAKE_PAD);

    /**
     * 운행 종료 시 호출 - 해당 차량의 모든 AI 지원 소모품에 대해 마모율 계산
     */
    @Transactional
    public void calculateAndSaveWearFactors(UUID vehicleId) {
        log.info("[WearFactor] 마모율 계산 시작 [Vehicle: {}]", vehicleId);

        Vehicle vehicle = vehicleRepository.findById(vehicleId)
                .orElseThrow(() -> new RuntimeException("차량을 찾을 수 없습니다: " + vehicleId));

        for (MaintenanceItem item : AI_SUPPORTED_ITEMS) {
            try {
                calculateAndSaveForItem(vehicle, item);
            } catch (Exception e) {
                log.error("[WearFactor] {} 마모율 계산 실패: {}", item, e.getMessage());
                // 개별 항목 실패해도 다른 항목은 계속 진행
            }
        }

        log.info("[WearFactor] 마모율 계산 완료 [Vehicle: {}]", vehicleId);
    }

    private void calculateAndSaveForItem(Vehicle vehicle, MaintenanceItem item) {
        // 해당 소모품 조회 (없으면 생성)
        VehicleConsumable consumable = vehicleConsumableRepository
                .findByVehicleAndItem(vehicle, item)
                .orElseGet(() -> createDefaultConsumable(vehicle, item));

        // AI 요청 생성
        AiWearFactorRequest request = AiWearFactorRequest.builder()
                .targetItem(mapToAiItem(item))
                .lastReplaced(AiWearFactorRequest.LastReplaced.builder()
                        .date(consumable.getLastMaintenanceDate())
                        .mileage(consumable.getLastMaintenanceMileage() != null
                                ? consumable.getLastMaintenanceMileage().intValue()
                                : 0)
                        .build())
                .vehicleMetadata(AiWearFactorRequest.VehicleMetadata.builder()
                        .modelYear(vehicle.getModelYear() != null ? vehicle.getModelYear() : 2023)
                        .fuelType(vehicle.getFuelType() != null ? vehicle.getFuelType().name() : "GASOLINE")
                        .totalMileage(vehicle.getTotalMileage().intValue())
                        .build())
                .drivingHabits(AiWearFactorRequest.DrivingHabits.builder()
                        .avgRpm(2500.0) // TODO: 실제 TripSummary에서 가져오기
                        .hardAccelCount(0)
                        .hardBrakeCount(0)
                        .idleRatio(0.1)
                        .build())
                .build();

        // AI 서버 호출
        AiWearFactorResponse response = aiClient.getWearFactor(request);

        if (response != null && response.getPredictedWearFactor() != null) {
            consumable.updateWearFactor(response.getPredictedWearFactor());
            vehicleConsumableRepository.save(consumable);
            log.info("[WearFactor] {} 마모율 저장 완료: {}", item, response.getPredictedWearFactor());
        }
    }

    private VehicleConsumable createDefaultConsumable(Vehicle vehicle, MaintenanceItem item) {
        VehicleConsumable consumable = VehicleConsumable.builder()
                .vehicle(vehicle)
                .item(item)
                .lastMaintenanceMileage(0.0)
                .lastMaintenanceDate(java.time.LocalDate.now())
                .replacementIntervalMileage(10000.0)
                .replacementIntervalMonths(6)
                .build();
        return vehicleConsumableRepository.save(consumable);
    }

    private String mapToAiItem(MaintenanceItem item) {
        return switch (item) {
            case ENGINE_OIL -> "ENGINE_OIL";
            case TIRE -> "TIRES";
            case BRAKE_PAD -> "BRAKE_PADS";
            default -> throw new IllegalArgumentException("AI 미지원 소모품: " + item);
        };
    }
}
