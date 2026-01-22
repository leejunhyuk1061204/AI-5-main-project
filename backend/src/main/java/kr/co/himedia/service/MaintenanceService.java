package kr.co.himedia.service;

import kr.co.himedia.common.exception.BaseException;
import kr.co.himedia.common.exception.ErrorCode;
import kr.co.himedia.dto.maintenance.MaintenanceHistoryRequest;
import kr.co.himedia.dto.maintenance.MaintenanceHistoryResponse;
import kr.co.himedia.dto.maintenance.ConsumableStatusResponse;

import kr.co.himedia.entity.MaintenanceHistory;
import kr.co.himedia.entity.MaintenanceItem; // Enum은 API 응답용으로 사용 or 삭제 고려
import kr.co.himedia.entity.Vehicle;
import kr.co.himedia.entity.VehicleConsumable;
import kr.co.himedia.entity.ConsumableItem;
import kr.co.himedia.repository.MaintenanceHistoryRepository;
import kr.co.himedia.repository.VehicleConsumableRepository;
import kr.co.himedia.repository.VehicleRepository;
import kr.co.himedia.repository.ConsumableItemRepository;

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
        private final ConsumableItemRepository consumableItemRepository;
        private final OcrService ocrService;

        /**
         * 정비 이력 다중 등록 (리스트 처리)
         */
        @Transactional
        public List<MaintenanceHistoryResponse> registerMaintenanceList(UUID vehicleId,
                        List<MaintenanceHistoryRequest> requests) {
                if (requests == null || requests.isEmpty()) {
                        return List.of();
                }
                return requests.stream()
                                .map(req -> registerMaintenance(vehicleId, req))
                                .collect(Collectors.toList());
        }

        /**
         * 정비 이력 등록 (단건)
         */
        @Transactional
        public MaintenanceHistoryResponse registerMaintenance(UUID vehicleId, MaintenanceHistoryRequest request) {
                Vehicle vehicle = vehicleRepository.findById(vehicleId)
                                .orElseThrow(() -> new BaseException(ErrorCode.VEHICLE_NOT_FOUND));

                // 1. 정비 이력 저장 (Stack)
                ConsumableItem item = consumableItemRepository.findById(request.getConsumableItemId())
                                .orElseThrow(() -> new BaseException(ErrorCode.INVALID_INPUT_VALUE));

                MaintenanceHistory history = MaintenanceHistory.builder()
                                .vehicle(vehicle)
                                .maintenanceDate(request.getMaintenanceDate())
                                .mileageAtMaintenance(request.getMileageAtMaintenance())
                                .consumableItem(item) // FK로 저장
                                .isStandardized(request.getIsStandardized())
                                .shopName(request.getShopName())
                                .cost(request.getCost())
                                .ocrData(request.getOcrData())
                                .memo(request.getMemo())
                                .build();

                MaintenanceHistory savedHistory = maintenanceHistoryRepository.save(history);

                // 2. 소모품 상태 갱신 (UPSERT)
                vehicleConsumableRepository.findByVehicleAndConsumableItem_Id(vehicle, request.getConsumableItemId())
                                .ifPresentOrElse(vc -> {
                                        // 기존 데이터가 있으면 업데이트 (Update)
                                        vc.setLastReplacedAt(request.getMaintenanceDate().atStartOfDay());
                                        vc.setLastReplacedMileage(request.getMileageAtMaintenance());
                                        vc.updateRemainingLife(100.0); // 교체 직후는 100%
                                        vc.setIsInferred(false); // 직접 정비했으므로 추론 데이터 아님
                                        vehicleConsumableRepository.save(vc);
                                }, () -> {
                                        // 기존 데이터가 없으면 신규 생성 (Insert)
                                        VehicleConsumable newVc = new VehicleConsumable();
                                        newVc.setVehicle(vehicle);
                                        newVc.setConsumableItem(item);
                                        newVc.setWearFactor(1.0);
                                        newVc.setLastReplacedAt(request.getMaintenanceDate().atStartOfDay());
                                        newVc.setLastReplacedMileage(request.getMileageAtMaintenance());
                                        newVc.setRemainingLife(100.0);
                                        newVc.setIsInferred(false); // 직접 정비했으므로 추론 데이터 아님
                                        vehicleConsumableRepository.save(newVc);
                                });

                return new MaintenanceHistoryResponse(savedHistory);
        }

        /**
         * 소모품 상태 조회
         */
        @Transactional(readOnly = true)
        public List<ConsumableStatusResponse> getConsumableStatus(UUID vehicleId) {
                Vehicle vehicle = vehicleRepository.findById(vehicleId)
                                .orElseThrow(() -> new IllegalArgumentException("해당 차량을 찾을 수 없습니다. ID: " + vehicleId));

                // 1. 모든 Master Data 조회
                List<ConsumableItem> allItems = consumableItemRepository.findAll();

                return allItems.stream()
                                .map(item -> {
                                        // 2. 매핑 테이블 조회 (없으면 가상 객체 생성하여 보여줌)
                                        VehicleConsumable vc = vehicleConsumableRepository
                                                        .findByVehicleAndConsumableItem_Code(vehicle, item.getCode())
                                                        .orElse(null);

                                        // 3. 최신 정비 이력 조회 (참고용)
                                        MaintenanceHistory lastHistory = maintenanceHistoryRepository
                                                        .findTopByVehicleAndConsumableItemOrderByMaintenanceDateDesc(
                                                                        vehicle,
                                                                        item)
                                                        .orElse(null);

                                        double remainingLife = (vc != null && vc.getRemainingLife() != null)
                                                        ? vc.getRemainingLife()
                                                        : 100.0; // 없으면 100%로 표시? or 미등록 상태 표시?
                                                                 // 여기서는 일단 단순하게 표시

                                        double intervalMileage = item.getDefaultIntervalMileage();
                                        int intervalMonths = (item.getDefaultIntervalMonths() != null)
                                                        ? item.getDefaultIntervalMonths()
                                                        : 12;

                                        // Enum 매핑 (DTO가 Enum을 요구한다면)
                                        // MaintenanceItem과 Code가 1:1 매핑된다고 가정하고 변환
                                        MaintenanceItem itemEnum;
                                        try {
                                                itemEnum = MaintenanceItem.valueOf(item.getCode());
                                        } catch (IllegalArgumentException e) {
                                                // 마스터 데이터 코드가 Enum에 없으면 'OTHER' 등으로 처리하거나 스킵
                                                // 여기서는 OTHER로 처리
                                                itemEnum = MaintenanceItem.OTHER;
                                        }

                                        return ConsumableStatusResponse.builder()
                                                        .item(itemEnum)
                                                        .itemDescription(item.getName())
                                                        .consumableItemId(item.getId())
                                                        .remainingLifePercent(Math.round(remainingLife * 10.0) / 10.0)
                                                        .lastMaintenanceDate(lastHistory != null
                                                                        ? lastHistory.getMaintenanceDate()
                                                                        : null)
                                                        .lastMaintenanceMileage(
                                                                        vc != null ? vc.getLastReplacedMileage() : 0.0)
                                                        .replacementIntervalMileage(intervalMileage)
                                                        .replacementIntervalMonths(intervalMonths)
                                                        .build();
                                })
                                .collect(Collectors.toList());
        }

        /**
         * 영수증 OCR 분석
         */
        public kr.co.himedia.dto.maintenance.MaintenanceReceiptResponse analyzeReceipt(
                        org.springframework.web.multipart.MultipartFile file) {
                String ocrText = ocrService.extractTextFromImage(file);
                return ocrService.parseReceiptData(ocrText);
        }
}
