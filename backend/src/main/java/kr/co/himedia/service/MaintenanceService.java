package kr.co.himedia.service;

import kr.co.himedia.dto.maintenance.MaintenanceHistoryRequest;
import kr.co.himedia.dto.maintenance.MaintenanceHistoryResponse;
import kr.co.himedia.dto.maintenance.ConsumableStatusResponse;
import kr.co.himedia.dto.maintenance.ai.AiWearFactorRequest;
import kr.co.himedia.dto.maintenance.ai.AiWearFactorResponse;
import kr.co.himedia.entity.MaintenanceHistory;
import kr.co.himedia.entity.MaintenanceItem;
import kr.co.himedia.entity.Vehicle;
import kr.co.himedia.entity.VehicleConsumable;
import kr.co.himedia.repository.MaintenanceHistoryRepository;
import kr.co.himedia.repository.VehicleConsumableRepository;
import kr.co.himedia.repository.VehicleRepository;
import kr.co.himedia.service.ai.AiClient;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.UUID;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class MaintenanceService {

        private final MaintenanceHistoryRepository maintenanceHistoryRepository;
        private final VehicleConsumableRepository vehicleConsumableRepository;
        private final VehicleRepository vehicleRepository;
        private final AiClient aiClient;

        @Transactional
        public MaintenanceHistoryResponse registerMaintenance(UUID vehicleId, MaintenanceHistoryRequest request) {
                Vehicle vehicle = vehicleRepository.findById(vehicleId)
                                .orElseThrow(() -> new IllegalArgumentException("해당 차량을 찾을 수 없습니다. ID: " + vehicleId));

                // 1. 정비 이력 저장
                MaintenanceHistory history = MaintenanceHistory.builder()
                                .vehicle(vehicle)
                                .maintenanceDate(request.getMaintenanceDate())
                                .mileageAtMaintenance(request.getMileageAtMaintenance())
                                .item(request.getItem())
                                .cost(request.getCost())
                                .memo(request.getMemo())
                                .build();

                MaintenanceHistory savedHistory = maintenanceHistoryRepository.save(history);

                // 2. 소모품 수명(마지막 정비 상세) 업데이트 (수명 리셋)
                vehicleConsumableRepository.findByVehicleAndItem(vehicle, request.getItem())
                                .ifPresentOrElse(
                                                consumable -> consumable.updateMaintenanceInfo(
                                                                request.getMileageAtMaintenance(),
                                                                request.getMaintenanceDate()),
                                                () -> {
                                                        VehicleConsumable newConsumable = VehicleConsumable.builder()
                                                                        .vehicle(vehicle)
                                                                        .item(request.getItem())
                                                                        .lastMaintenanceMileage(request
                                                                                        .getMileageAtMaintenance())
                                                                        .lastMaintenanceDate(
                                                                                        request.getMaintenanceDate())
                                                                        .replacementIntervalMileage(10000.0) // 기본값
                                                                        .replacementIntervalMonths(6) // 기본값
                                                                        .build();
                                                        vehicleConsumableRepository.save(newConsumable);
                                                });

                return new MaintenanceHistoryResponse(savedHistory);
        }

        @Transactional(readOnly = true)
        public List<ConsumableStatusResponse> getConsumableStatus(UUID vehicleId) {
                Vehicle vehicle = vehicleRepository.findById(vehicleId)
                                .orElseThrow(() -> new IllegalArgumentException("해당 차량을 찾을 수 없습니다. ID: " + vehicleId));

                List<VehicleConsumable> consumables = vehicleConsumableRepository.findByVehicle(vehicle);

                return consumables.stream()
                                .map(consumable -> {
                                        double wearFactor = 1.0;

                                        if (isAiSupported(consumable.getItem())) {
                                                try {
                                                        AiWearFactorRequest aiRequest = AiWearFactorRequest.builder()
                                                                        .targetItem(mapToAiItem(consumable.getItem()))
                                                                        .lastReplaced(AiWearFactorRequest.LastReplaced
                                                                                        .builder()
                                                                                        .date(consumable.getLastMaintenanceDate())
                                                                                        .mileage(consumable
                                                                                                        .getLastMaintenanceMileage()
                                                                                                        .intValue())
                                                                                        .build())
                                                                        .vehicleMetadata(
                                                                                        AiWearFactorRequest.VehicleMetadata
                                                                                                        .builder()
                                                                                                        .modelYear(vehicle
                                                                                                                        .getModelYear() != null
                                                                                                                                        ? vehicle.getModelYear()
                                                                                                                                        : 2023)
                                                                                                        .fuelType(vehicle
                                                                                                                        .getFuelType() != null
                                                                                                                                        ? vehicle.getFuelType()
                                                                                                                                                        .name()
                                                                                                                                        : "GASOLINE")
                                                                                                        .totalMileage(vehicle
                                                                                                                        .getTotalMileage()
                                                                                                                        .intValue())
                                                                                                        .build())
                                                                        .drivingHabits(AiWearFactorRequest.DrivingHabits
                                                                                        .builder()
                                                                                        .avgRpm(2500.0) // Mock
                                                                                        .hardAccelCount(0)
                                                                                        .hardBrakeCount(0)
                                                                                        .idleRatio(0.1)
                                                                                        .build())
                                                                        .build();

                                                        AiWearFactorResponse aiResponse = aiClient
                                                                        .getWearFactor(aiRequest);
                                                        if (aiResponse != null) {
                                                                wearFactor = aiResponse.getPredictedWearFactor();
                                                        }
                                                } catch (Exception e) {
                                                        System.err.println("AI API call failed for item "
                                                                        + consumable.getItem() + ": " + e.getMessage());
                                                }
                                        }

                                        double currentMileage = vehicle.getTotalMileage();
                                        double lastMileage = consumable.getLastMaintenanceMileage();
                                        double intervalMileage = consumable.getReplacementIntervalMileage() != null
                                                        ? consumable.getReplacementIntervalMileage()
                                                        : 10000.0;

                                        double usedMileage = (currentMileage - lastMileage) * wearFactor;
                                        double remainingLifePercent = Math.max(0,
                                                        (intervalMileage - usedMileage) / intervalMileage * 100);

                                        return ConsumableStatusResponse.builder()
                                                        .item(consumable.getItem())
                                                        .itemDescription(consumable.getItem().getDescription())
                                                        .remainingLifePercent(
                                                                        Math.round(remainingLifePercent * 10.0) / 10.0)
                                                        .lastMaintenanceDate(consumable.getLastMaintenanceDate())
                                                        .lastMaintenanceMileage(consumable.getLastMaintenanceMileage())
                                                        .replacementIntervalMileage(
                                                                        consumable.getReplacementIntervalMileage())
                                                        .replacementIntervalMonths(
                                                                        consumable.getReplacementIntervalMonths())
                                                        .build();
                                })
                                .collect(Collectors.toList());
        }

        private boolean isAiSupported(MaintenanceItem item) {
                return item == MaintenanceItem.ENGINE_OIL || item == MaintenanceItem.TIRE
                                || item == MaintenanceItem.BRAKE_PAD;
        }

        private String mapToAiItem(MaintenanceItem item) {
                return switch (item) {
                        case ENGINE_OIL -> "ENGINE_OIL";
                        case TIRE -> "TIRES";
                        case BRAKE_PAD -> "BRAKE_PADS";
                        default -> throw new IllegalArgumentException("Unsupported AI item: " + item);
                };
        }
}
