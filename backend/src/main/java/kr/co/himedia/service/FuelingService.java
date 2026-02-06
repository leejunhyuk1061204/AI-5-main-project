package kr.co.himedia.service;

import kr.co.himedia.dto.maintenance.FuelingHistoryRequest;
import kr.co.himedia.dto.maintenance.FuelingHistoryResponse;
import kr.co.himedia.entity.FuelingHistory;
import kr.co.himedia.entity.Vehicle;
import kr.co.himedia.repository.FuelingHistoryRepository;
import kr.co.himedia.repository.VehicleRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.UUID;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class FuelingService {

    private final FuelingHistoryRepository fuelingHistoryRepository;
    private final VehicleRepository vehicleRepository;

    @Transactional
    public FuelingHistoryResponse registerFueling(UUID vehicleId, FuelingHistoryRequest request) {
        Vehicle vehicle = vehicleRepository.findById(vehicleId)
                .orElseThrow(() -> new IllegalArgumentException("Vehicle not found: " + vehicleId));

        FuelingHistory history = FuelingHistory.builder()
                .vehicle(vehicle)
                .fuelType(request.getFuelType())
                .fuelingDate(request.getFuelingDate())
                .amount(request.getAmount())
                .unitPrice(request.getUnitPrice())
                .totalCost(request.getTotalCost())
                .mileageAtFueling(request.getMileageAtFueling())
                .shopName(request.getShopName())
                .memo(request.getMemo())
                .receiptId(request.getReceiptId())
                .build();

        // 차량의 주행거리 업데이트 (더 최신일 경우)
        if (request.getMileageAtFueling() != null &&
                (vehicle.getTotalMileage() == null || request.getMileageAtFueling() > vehicle.getTotalMileage())) {
            vehicle.updateTotalMileage(request.getMileageAtFueling());
            vehicleRepository.save(vehicle);
        }

        FuelingHistory savedHistory = fuelingHistoryRepository.save(history);
        return new FuelingHistoryResponse(savedHistory);
    }

    @Transactional(readOnly = true)
    public List<FuelingHistoryResponse> getFuelingHistory(UUID vehicleId) {
        return fuelingHistoryRepository.findByVehicleVehicleIdOrderByFuelingDateDesc(vehicleId).stream()
                .map(FuelingHistoryResponse::new)
                .collect(Collectors.toList());
    }

    @Transactional
    public void deleteFueling(UUID fuelingId) {
        fuelingHistoryRepository.deleteById(fuelingId);
    }
}
