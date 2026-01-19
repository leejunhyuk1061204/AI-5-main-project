package kr.co.himedia.service;

import kr.co.himedia.common.exception.BaseException;
import kr.co.himedia.common.exception.ErrorCode;
import kr.co.himedia.dto.maintenance.MaintenanceHistoryRequest;
import kr.co.himedia.dto.maintenance.MaintenanceHistoryResponse;
import kr.co.himedia.dto.maintenance.ConsumableStatusResponse;

import kr.co.himedia.entity.MaintenanceHistory;

import kr.co.himedia.entity.MaintenanceItem;
import kr.co.himedia.entity.Vehicle;
import kr.co.himedia.entity.VehicleConsumable;
import kr.co.himedia.repository.MaintenanceHistoryRepository;
import kr.co.himedia.repository.VehicleConsumableRepository;
import kr.co.himedia.repository.VehicleRepository;

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
        private final kr.co.himedia.repository.ConsumableItemRepository consumableItemRepository; // New Repository

        @Transactional
        public MaintenanceHistoryResponse registerMaintenance(UUID vehicleId, MaintenanceHistoryRequest request) {
                Vehicle vehicle = vehicleRepository.findById(vehicleId)
                                .orElseThrow(() -> new BaseException(ErrorCode.VEHICLE_NOT_FOUND));

                // Enum String(request.getItem()) -> Entity Lookup
                kr.co.himedia.entity.ConsumableItem consumableItem = consumableItemRepository
                                .findByCode(request.getItem().name())
                                .orElseThrow(() -> new BaseException(ErrorCode.UNSUPPORTED_MAINTENANCE_ITEM));

                // 1. 정비 이력 저장
                MaintenanceHistory history = MaintenanceHistory.builder()
                                .vehicle(vehicle)
                                .maintenanceDate(request.getMaintenanceDate())
                                .mileageAtMaintenance(request.getMileageAtMaintenance())
                                .consumableItem(consumableItem)
                                .isStandardized(request.getIsStandardized())
                                .shopName(request.getShopName())
                                .cost(request.getCost())
                                .ocrData(request.getOcrData())
                                .memo(request.getMemo())
                                .build();

                MaintenanceHistory savedHistory = maintenanceHistoryRepository.save(history);

                // 2. VehicleConsumable (상태/AI설정) 확인 및 생성
                // 이력이 생겼으니, AI 마모도 관리를 위한 Entity가 없으면 만들어준다. (기존값 유지)
                vehicleConsumableRepository.findByVehicleAndConsumableItem(vehicle, consumableItem)
                                .orElseGet(() -> {
                                        VehicleConsumable newConsumable = VehicleConsumable.builder()
                                                        .vehicle(vehicle)
                                                        .consumableItem(consumableItem)
                                                        .wearFactor(1.0) // 기본값
                                                        .build();
                                        return vehicleConsumableRepository.save(newConsumable);
                                });

                return new MaintenanceHistoryResponse(savedHistory);
        }

        @Transactional(readOnly = true)
        public List<ConsumableStatusResponse> getConsumableStatus(UUID vehicleId) {
                Vehicle vehicle = vehicleRepository.findById(vehicleId)
                                .orElseThrow(() -> new IllegalArgumentException("해당 차량을 찾을 수 없습니다. ID: " + vehicleId));

                // 1. 모든 소모품 종류(Master Data) 조회
                List<kr.co.himedia.entity.ConsumableItem> allItems = consumableItemRepository.findAll();

                return allItems.stream()
                                .map(item -> {
                                        // 2. 각 소모품별 차량 상태(AI WearFactor, Custom Interval) 조회 - 없으면 기본값 사용
                                        VehicleConsumable status = vehicleConsumableRepository
                                                        .findByVehicleAndConsumableItem(vehicle, item)
                                                        .orElse(null);

                                        double wearFactor = (status != null && status.getWearFactor() != null)
                                                        ? status.getWearFactor()
                                                        : 1.0;

                                        // AI 갱신 로직 (필요시 비동기 호출하거나, 여기서 호출) -> 여기서는 생략하고 WearFactorService에 위임하거나 기존 유지
                                        // 성능상 리스트 조회시마다 AI 호출은 비추천. 별도 스케줄러/이벤트로 갱신됨을 가정하고 저장된 값만 사용.

                                        // 3. 가장 최신 정비 이력 조회 (Dynamic Calculation)
                                        MaintenanceHistory lastHistory = maintenanceHistoryRepository
                                                        .findTopByVehicleAndConsumableItemOrderByMaintenanceDateDesc(
                                                                        vehicle, item)
                                                        .orElse(null);

                                        double lastMileage = (lastHistory != null)
                                                        ? lastHistory.getMileageAtMaintenance()
                                                        : 0.0;
                                        java.time.LocalDate lastDate = (lastHistory != null)
                                                        ? lastHistory.getMaintenanceDate()
                                                        : java.time.LocalDate.now().minusYears(10); // 기록 없으면 아주 옛날

                                        // 4. 교체 주기 결정 (사용자 설정 > DB 기본값)
                                        double intervalMileage = (status != null
                                                        && status.getCustomIntervalMileage() != null)
                                                                        ? status.getCustomIntervalMileage()
                                                                        : (item.getDefaultIntervalMileage() != null
                                                                                        ? item.getDefaultIntervalMileage()
                                                                                        : 999999.0);

                                        int intervalMonths = (status != null
                                                        && status.getCustomIntervalMonths() != null)
                                                                        ? status.getCustomIntervalMonths()
                                                                        : (item.getDefaultIntervalMonths() != null
                                                                                        ? item.getDefaultIntervalMonths()
                                                                                        : 999);

                                        // 5. 남은 수명 계산 (주행거리 기준)
                                        double currentMileage = vehicle.getTotalMileage();
                                        double usedMileage = (currentMileage - lastMileage) * wearFactor;
                                        double mileagePct = Math.max(0,
                                                        (intervalMileage - usedMileage) / intervalMileage * 100);

                                        // 6. 남은 수명 계산 (기간 기준)
                                        long monthsPassed = java.time.temporal.ChronoUnit.MONTHS.between(lastDate,
                                                        java.time.LocalDate.now());
                                        double timePct = Math.max(0, (intervalMonths - monthsPassed)
                                                        / (double) intervalMonths * 100);

                                        // 둘 중 더 급한 것(작은 것) 선택
                                        double finalPct = Math.min(mileagePct, timePct);

                                        return ConsumableStatusResponse.builder()
                                                        .item(MaintenanceItem.valueOf(item.getCode())) // e.g.,
                                                                                                       // "ENGINE_OIL"
                                                        .itemDescription(item.getName()) // e.g., "엔진오일"
                                                        .remainingLifePercent(Math.round(finalPct * 10.0) / 10.0)
                                                        .lastMaintenanceDate(lastHistory != null
                                                                        ? lastHistory.getMaintenanceDate()
                                                                        : null)
                                                        .lastMaintenanceMileage(lastMileage)
                                                        .replacementIntervalMileage(intervalMileage)
                                                        .replacementIntervalMonths(intervalMonths)
                                                        .build();
                                })
                                .collect(Collectors.toList());
        }

        // isAiSupported, mapToAiItem methods removed or moved to WearFactorService
        // logic as needed.
        // Or keep them if you still want to call AI here. But for "Status View",
        // reading saved wear_factor is better.

}
