package kr.co.himedia.service;

import kr.co.himedia.common.exception.BaseException;
import kr.co.himedia.common.exception.ErrorCode;
import kr.co.himedia.dto.maintenance.MaintenanceHistoryRequest;
import kr.co.himedia.dto.maintenance.MaintenanceHistoryResponse;
import kr.co.himedia.dto.maintenance.ConsumableStatusResponse;
import kr.co.himedia.dto.maintenance.OcrAnalysisResponse;

import kr.co.himedia.entity.MaintenanceHistory;
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
import org.springframework.web.multipart.MultipartFile;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;
import java.util.stream.Collectors;

import lombok.extern.slf4j.Slf4j;

@Slf4j
@Service
@RequiredArgsConstructor
public class MaintenanceService {

        private final MaintenanceHistoryRepository maintenanceHistoryRepository;
        private final VehicleConsumableRepository vehicleConsumableRepository;
        private final VehicleRepository vehicleRepository;
        private final ConsumableItemRepository consumableItemRepository;
        private final OcrService ocrService;
        private final ReceiptAnalyzerService receiptAnalyzerService;
        private final AiMediaService aiMediaService;

        /**
         * 정비 이력 다중 등록 (리스트 처리)
         */
        @Transactional
        public List<MaintenanceHistoryResponse> registerMaintenanceList(UUID vehicleId,
                        List<MaintenanceHistoryRequest> requests) {
                if (requests == null || requests.isEmpty()) {
                        return List.of();
                }

                // 영수증 단위 그룹화를 위한 ID 생성
                UUID receiptId = UUID.randomUUID();

                return requests.stream()
                                .map(req -> {
                                        req.setReceiptId(receiptId);
                                        return registerMaintenance(vehicleId, req);
                                })
                                .collect(Collectors.toList());
        }

        /**
         * 정비 이력 등록 (단건)
         */
        @Transactional
        public MaintenanceHistoryResponse registerMaintenance(UUID vehicleId, MaintenanceHistoryRequest request) {
                Vehicle vehicle = vehicleRepository.findById(vehicleId)
                                .orElseThrow(() -> new BaseException(ErrorCode.VEHICLE_NOT_FOUND));

                ConsumableItem searchItem = null;
                if (request.getConsumableItemId() != null) {
                        searchItem = consumableItemRepository.findById(request.getConsumableItemId()).orElse(null);
                }

                if (searchItem == null && request.getConsumableItemCode() != null) {
                        String code = request.getConsumableItemCode().trim().toUpperCase();
                        searchItem = consumableItemRepository.findByCode(code).orElse(null);
                }

                if (searchItem == null && request.getConsumableItemName() != null) {
                        String name = request.getConsumableItemName().trim();
                        // 1. 이름으로 정확히 찾기
                        searchItem = consumableItemRepository.findByName(name).orElse(null);

                        // 2. 공백 제거하고 다시 찾아보기 (DB의 '엔진 오일' vs 프런트의 '엔진오일' 등)
                        if (searchItem == null) {
                                final String normalizedSearchName = name.replace(" ", "");
                                searchItem = consumableItemRepository.findAll().stream()
                                                .filter(ci -> ci.getName().replace(" ", "")
                                                                .equals(normalizedSearchName))
                                                .findFirst()
                                                .orElse(null);
                        }
                }

                final ConsumableItem item = (searchItem != null) ? searchItem : getOrCreateOtherItem();

                // 미입력·0이면 vehicles.total_mileage로 대체 (registerHistory와 동일)
                Double requestedMileage = request.getMileageAtMaintenance();
                Double mileageAtMaintenance = (requestedMileage != null && requestedMileage > 0)
                                ? requestedMileage
                                : (vehicle.getTotalMileage() != null ? vehicle.getTotalMileage() : 0.0);

                MaintenanceHistory history = MaintenanceHistory.builder()
                                .vehicle(vehicle)
                                .maintenanceDate(request.getMaintenanceDate() != null ? request.getMaintenanceDate()
                                                : LocalDate.now())
                                .mileageAtMaintenance(mileageAtMaintenance)
                                .consumableItem(item)
                                .isStandardized(request.getIsStandardized())
                                .shopName(request.getShopName())
                                .cost(request.getCost())
                                .quantity(request.getQuantity() != null ? request.getQuantity() : 1)
                                .ocrData(request.getOcrData())
                                .receiptId(request.getReceiptId())
                                .memo(request.getMemo())
                                .build();

                MaintenanceHistory savedHistory = maintenanceHistoryRepository.save(history);

                // 2. 소모품 상태 갱신 (UPSERT)
                // request.getConsumableItemId()가 null일 수 있으므로, 위에서 조회한 item.getId()를 사용해야 함
                double remainingLife = computeRemainingLifePercent(vehicle, mileageAtMaintenance, item);
                vehicleConsumableRepository.findByVehicleAndConsumableItem_Id(vehicle, item.getId())
                                .ifPresentOrElse(vc -> {
                                        if (request.getMaintenanceDate() != null) {
                                                vc.setLastReplacedAt(request.getMaintenanceDate().atStartOfDay());
                                        }
                                        vc.setLastReplacedMileage(mileageAtMaintenance);
                                        vc.updateRemainingLife(remainingLife);
                                        vc.setIsInferred(false);
                                        vehicleConsumableRepository.save(vc);
                                }, () -> {
                                        VehicleConsumable newVc = new VehicleConsumable();
                                        newVc.setVehicle(vehicle);
                                        newVc.setConsumableItem(item);
                                        newVc.setWearFactor(1.0);
                                        if (request.getMaintenanceDate() != null) {
                                                newVc.setLastReplacedAt(request.getMaintenanceDate().atStartOfDay());
                                        }
                                        newVc.setLastReplacedMileage(mileageAtMaintenance);
                                        newVc.setRemainingLife(remainingLife);
                                        newVc.setIsInferred(false);
                                        vehicleConsumableRepository.save(newVc);
                                });

                return new MaintenanceHistoryResponse(savedHistory);
        }

        /**
         * 정비 이력 조회 (필터링 지원)
         */
        @Transactional(readOnly = true)
        public List<MaintenanceHistoryResponse> getMaintenanceHistory(UUID vehicleId, String itemCode,
                        LocalDate startDate, LocalDate endDate) {
                Vehicle vehicle = vehicleRepository.findById(vehicleId)
                                .orElseThrow(() -> new BaseException(ErrorCode.VEHICLE_NOT_FOUND));

                List<MaintenanceHistory> histories;

                if (itemCode != null && !itemCode.isEmpty()) {
                        if (startDate != null && endDate != null) {
                                histories = maintenanceHistoryRepository
                                                .findByVehicleAndConsumableItem_CodeAndMaintenanceDateBetweenOrderByMaintenanceDateDesc(
                                                                vehicle, itemCode, startDate, endDate);
                        } else {
                                histories = maintenanceHistoryRepository
                                                .findByVehicleAndConsumableItem_CodeOrderByMaintenanceDateDesc(vehicle,
                                                                itemCode);
                        }
                } else if (startDate != null && endDate != null) {
                        histories = maintenanceHistoryRepository
                                        .findByVehicleAndMaintenanceDateBetweenOrderByMaintenanceDateDesc(vehicle,
                                                        startDate, endDate);
                } else {
                        histories = maintenanceHistoryRepository.findByVehicleOrderByMaintenanceDateDesc(vehicle);
                }

                return histories.stream()
                                .map(MaintenanceHistoryResponse::new)
                                .collect(Collectors.toList());
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
                                        Integer intervalMonths = (item.getDefaultIntervalMonths() != null)
                                                        ? item.getDefaultIntervalMonths()
                                                        : 12;

                                        // 4. 예상 교체일 계산 (잔여 수명 기반 역산)
                                        // 잔여 수명 %가 남은 기간 %와 같다고 가정
                                        // 남은 기간 = 전체 주기 * (잔여 수명 / 100)
                                        LocalDate predictedDate = null;
                                        if (intervalMonths != null && intervalMonths > 0) {
                                                double remainingRatio = remainingLife / 100.0;
                                                long remainingMonths = Math.round(intervalMonths * remainingRatio);
                                                predictedDate = LocalDate.now().plusMonths(remainingMonths);
                                        }

                                        return ConsumableStatusResponse.builder()
                                                        .itemCode(item.getCode()) // DB 코드 직접 사용
                                                        .itemDescription(item.getName()) // DB 이름 직접 사용
                                                        .consumableItemId(item.getId())
                                                        .remainingLifePercent(Math.round(remainingLife * 10.0) / 10.0)
                                                        .lastMaintenanceDate(lastHistory != null
                                                                        ? lastHistory.getMaintenanceDate()
                                                                        : null)
                                                        .lastMaintenanceMileage(
                                                                        vc != null ? vc.getLastReplacedMileage() : 0.0)
                                                        .replacementIntervalMileage(intervalMileage)
                                                        .replacementIntervalMonths(intervalMonths)
                                                        .predictedReplacementDate(predictedDate)
                                                        .build();
                                })
                                // 정렬: 예상 교체일 오름차순 (null은 뒤로? 앞으로? -> 급한 건 아니므로 뒤로 배치하거나, interval 없는 건 제외)
                                // 여기서는 nullsLast로 처리
                                .sorted((c1, c2) -> {
                                        if (c1.getPredictedReplacementDate() == null
                                                        && c2.getPredictedReplacementDate() == null)
                                                return 0;
                                        if (c1.getPredictedReplacementDate() == null)
                                                return 1;
                                        if (c2.getPredictedReplacementDate() == null)
                                                return -1;
                                        return c1.getPredictedReplacementDate()
                                                        .compareTo(c2.getPredictedReplacementDate());
                                })
                                .collect(Collectors.toList());
        }

        /**
         * 정비 이력 및 소모품 상태 업데이트 (통합 등록용 내부 메소드)
         * maintenance_logs NOT NULL 컬럼 대응: date/mileage null 시 기본값 적용
         */
        @Transactional
        public void registerHistory(Vehicle vehicle, ConsumableItem item, LocalDate maintenanceDate, Double mileage) {
                LocalDate safeDate = maintenanceDate != null ? maintenanceDate : java.time.LocalDate.now();
                Double safeMileage = mileage != null ? mileage
                                : (vehicle.getTotalMileage() != null ? vehicle.getTotalMileage() : 0.0);
                MaintenanceHistory history = MaintenanceHistory.builder()
                                .vehicle(vehicle)
                                .maintenanceDate(safeDate)
                                .mileageAtMaintenance(safeMileage)
                                .consumableItem(item)
                                .isStandardized(true)
                                .build();
                maintenanceHistoryRepository.save(history);

                double remainingLife = computeRemainingLifePercent(vehicle, mileage != null ? mileage : safeMileage,
                                item);
                vehicleConsumableRepository.findByVehicleAndConsumableItem_Id(vehicle, item.getId())
                                .ifPresentOrElse(vc -> {
                                        if (maintenanceDate != null) {
                                                vc.setLastReplacedAt(maintenanceDate.atStartOfDay());
                                        }
                                        vc.setLastReplacedMileage(mileage);
                                        vc.updateRemainingLife(remainingLife);
                                        vc.setIsInferred(false);
                                        vehicleConsumableRepository.save(vc);
                                }, () -> {
                                        VehicleConsumable newVc = new VehicleConsumable();
                                        newVc.setVehicle(vehicle);
                                        newVc.setConsumableItem(item);
                                        newVc.setWearFactor(1.0);
                                        if (maintenanceDate != null) {
                                                newVc.setLastReplacedAt(maintenanceDate.atStartOfDay());
                                        }
                                        newVc.setLastReplacedMileage(mileage);
                                        newVc.setRemainingLife(remainingLife);
                                        newVc.setIsInferred(false);
                                        vehicleConsumableRepository.save(newVc);
                                });
        }

        /**
         * 영수증 OCR 분석
         */
        public kr.co.himedia.dto.maintenance.MaintenanceReceiptResponse analyzeReceipt(
                        org.springframework.web.multipart.MultipartFile file) {
                String ocrText = ocrService.extractTextFromImage(file);
                return ocrService.parseReceiptData(ocrText);
        }

        /**
         * [BE-OCR-002] OCR 분석 + 정비 이력 저장 + 소모품 상태 갱신 (원스톱)
         * 영수증 이미지를 분석하여 정비 이력을 저장하고, 소모품 상태를 자동으로 갱신합니다.
         * manualDataJson이 있으면 사용자가 수정한 값을 우선 적용합니다.
         */
        @Transactional
        public MaintenanceHistoryResponse analyzeAndSave(UUID vehicleId, MultipartFile file, String manualDataJson) {
                // 1. 차량 존재 확인
                Vehicle vehicle = vehicleRepository.findById(vehicleId)
                                .orElseThrow(() -> new BaseException(ErrorCode.VEHICLE_NOT_FOUND));

                // 2. OCR 분석 (Naver OCR + OpenAI 파싱)
                OcrAnalysisResponse ocrResult = receiptAnalyzerService.analyze(file);

                // 2.1 이미지 저장 (Receipt Gallery용)
                UUID receiptId = UUID.randomUUID();
                try {
                        String originalFilename = file.getOriginalFilename();
                        String ext = "jpg";
                        if (originalFilename != null && originalFilename.contains(".")) {
                                ext = originalFilename.substring(originalFilename.lastIndexOf(".") + 1);
                        }
                        String filename = receiptId.toString() + "." + ext;
                        aiMediaService.storeMedia(file, "receipts", filename);
                } catch (Exception e) {
                        log.error("Failed to save receipt image", e);
                        // 이미지가 저장되지 않아도 분석 및 저장은 계속 진행
                }

                // 3. 사용자 수동 수정 데이터 파싱 (있을 경우)
                if (manualDataJson != null && !manualDataJson.isEmpty()) {
                        try {
                                com.fasterxml.jackson.databind.ObjectMapper mapper = new com.fasterxml.jackson.databind.ObjectMapper()
                                                .registerModule(new com.fasterxml.jackson.datatype.jsr310.JavaTimeModule());
                                com.fasterxml.jackson.databind.JsonNode manualNode = mapper.readTree(manualDataJson);

                                if (manualNode.has("maintenanceDate") && !manualNode.get("maintenanceDate").isNull()) {
                                        ocrResult.setMaintenanceDate(
                                                        LocalDate.parse(manualNode.get("maintenanceDate").asText()));
                                }
                                if (manualNode.has("mileageAtMaintenance")
                                                && !manualNode.get("mileageAtMaintenance").isNull()) {
                                        ocrResult.setMileageAtMaintenance(
                                                        manualNode.get("mileageAtMaintenance").asDouble());
                                }
                                if (manualNode.has("shopName") && !manualNode.get("shopName").isNull()) {
                                        ocrResult.setShopName(manualNode.get("shopName").asText());
                                }
                                if (manualNode.has("cost") && !manualNode.get("cost").isNull()) {
                                        ocrResult.setCost(manualNode.get("cost").asInt());
                                }
                                if (manualNode.has("consumableItemCode")
                                                && !manualNode.get("consumableItemCode").isNull()) {
                                        ocrResult.setConsumableItemCode(manualNode.get("consumableItemCode").asText());
                                }
                                if (manualNode.has("memo") && !manualNode.get("memo").isNull()) {
                                        // OcrAnalysisResponse 에는 memo가 없지만 ocrData에 병합하거나
                                        // 아래 request 생성 시 직접 주입 가능
                                }
                        } catch (Exception e) {
                                log.error("Failed to parse manual data JSON", e);
                        }
                }

                // 4. OCR/수동 데이터 → MaintenanceHistoryRequest로 변환
                java.time.LocalDate commonDate = ocrResult.getMaintenanceDate() != null
                                ? ocrResult.getMaintenanceDate()
                                : LocalDate.now();
                Double commonMileage = ocrResult.getMileageAtMaintenance() != null
                                ? ocrResult.getMileageAtMaintenance()
                                : vehicle.getTotalMileage();
                String commonMemo = null;
                try {
                        if (manualDataJson != null) {
                                com.fasterxml.jackson.databind.JsonNode node = new com.fasterxml.jackson.databind.ObjectMapper()
                                                .readTree(manualDataJson);
                                if (node.has("memo") && !node.get("memo").isNull())
                                        commonMemo = node.get("memo").asText();
                        }
                } catch (Exception ignored) {
                }

                if (ocrResult.getItems() != null && !ocrResult.getItems().isEmpty()) {
                        java.util.List<MaintenanceHistoryRequest> requests = new java.util.ArrayList<>();
                        for (kr.co.himedia.dto.maintenance.MaintenanceLineItemDto item : ocrResult.getItems()) {
                                MaintenanceHistoryRequest req = new MaintenanceHistoryRequest();
                                req.setMaintenanceDate(commonDate);
                                req.setMileageAtMaintenance(commonMileage);
                                req.setShopName(ocrResult.getShopName());
                                req.setCost(item.getAmount());
                                req.setQuantity(item.getQuantity() != null ? item.getQuantity() : 1);
                                req.setConsumableItemCode(item.getConsumableItemCode());
                                req.setOcrData(ocrResult.getOcrData());
                                req.setIsStandardized(true);
                                req.setReceiptId(receiptId);
                                req.setMemo(commonMemo);
                                requests.add(req);
                        }
                        java.util.List<MaintenanceHistoryResponse> responses = registerMaintenanceList(vehicleId,
                                        requests);
                        return responses.isEmpty() ? null : responses.get(0);
                }

                MaintenanceHistoryRequest request = new MaintenanceHistoryRequest();
                request.setMaintenanceDate(commonDate);
                request.setMileageAtMaintenance(commonMileage);
                request.setShopName(ocrResult.getShopName());
                request.setCost(ocrResult.getCost());
                request.setQuantity(ocrResult.getQuantity() != null ? ocrResult.getQuantity() : 1);
                request.setConsumableItemCode(ocrResult.getConsumableItemCode());
                request.setOcrData(ocrResult.getOcrData());
                request.setIsStandardized(true);
                request.setReceiptId(receiptId);
                request.setMemo(commonMemo);

                // 5. 정비 이력 저장 (소모품 상태 갱신 포함)
                return registerMaintenance(vehicleId, request);
        }

        /**
         * 정비 이력 수정
         */
        @Transactional
        public MaintenanceHistoryResponse updateMaintenance(UUID historyId, MaintenanceHistoryRequest request) {
                MaintenanceHistory history = maintenanceHistoryRepository.findById(historyId)
                                .orElseThrow(() -> new BaseException(ErrorCode.ENTITY_NOT_FOUND));

                // 1. 기본 정보 업데이트
                history.setMaintenanceDate(request.getMaintenanceDate());
                history.setMileageAtMaintenance(request.getMileageAtMaintenance());
                history.setShopName(request.getShopName());
                history.setCost(request.getCost());
                history.setMemo(request.getMemo());
                if (request.getQuantity() != null)
                        history.setQuantity(request.getQuantity());

                // 소모품 항목이 변경된 경우
                if (request.getConsumableItemCode() != null
                                && !history.getConsumableItem().getCode().equals(request.getConsumableItemCode())) {
                        ConsumableItem newItem = consumableItemRepository.findByCode(request.getConsumableItemCode())
                                        .orElseGet(() -> consumableItemRepository.findByCode("OTHER")
                                                        .orElseThrow(() -> new BaseException(
                                                                        ErrorCode.INVALID_INPUT_VALUE)));
                        history.setConsumableItem(newItem);
                }

                MaintenanceHistory updated = maintenanceHistoryRepository.save(history);

                // 2. 소모품 상태 재계산 (최신 데이터 기준으로)
                updateVehicleConsumableStatus(history.getVehicle(), history.getConsumableItem());

                return new MaintenanceHistoryResponse(updated);
        }

        /**
         * 정비 이력 삭제
         */
        @Transactional
        public void deleteMaintenance(UUID historyId) {
                MaintenanceHistory history = maintenanceHistoryRepository.findById(historyId)
                                .orElseThrow(() -> new BaseException(ErrorCode.ENTITY_NOT_FOUND));

                Vehicle vehicle = history.getVehicle();
                ConsumableItem item = history.getConsumableItem();

                maintenanceHistoryRepository.delete(history);

                // 삭제 후 소모품 상태 재계산
                updateVehicleConsumableStatus(vehicle, item);
        }

        /**
         * 차량 현재 주행거리·교체 시점 주행거리·교체 주기로 잔존 수명(%) 계산.
         * 계산 불가 시(주행거리/주기 없음) 100% 반환.
         */
        private double computeRemainingLifePercent(Vehicle vehicle, Double lastReplacedMileage, ConsumableItem item) {
                Double currentMileage = vehicle.getTotalMileage();
                if (currentMileage == null || lastReplacedMileage == null) {
                        return 100.0;
                }
                Integer interval = item.getDefaultIntervalMileage();
                if (interval == null || interval <= 0) {
                        return 100.0;
                }
                double used = currentMileage - lastReplacedMileage;
                if (used < 0) {
                        used = 0;
                }
                double remaining = 100.0 * (1.0 - used / interval);
                return Math.max(0.0, Math.min(100.0, remaining));
        }

        /**
         * 특정 소모품의 상태(마지막 교환일, 주행거리)를 최신 이력 기반으로 재계산
         */
        private void updateVehicleConsumableStatus(Vehicle vehicle, ConsumableItem item) {
                maintenanceHistoryRepository.findTopByVehicleAndConsumableItemOrderByMaintenanceDateDesc(vehicle, item)
                                .ifPresentOrElse(last -> {
                                        vehicleConsumableRepository
                                                        .findByVehicleAndConsumableItem_Id(vehicle, item.getId())
                                                        .ifPresent(vc -> {
                                                                vc.setLastReplacedAt(last.getMaintenanceDate()
                                                                                .atStartOfDay());
                                                                vc.setLastReplacedMileage(
                                                                                last.getMileageAtMaintenance());
                                                                double remaining = computeRemainingLifePercent(vehicle,
                                                                                last.getMileageAtMaintenance(), item);
                                                                vc.updateRemainingLife(remaining);
                                                                vehicleConsumableRepository.save(vc);
                                                        });
                                }, () -> {
                                        // 이력이 하나도 없으면 차량 등록 시와 동일한 미입력 추론 로직 적용
                                        vehicleConsumableRepository
                                                        .findByVehicleAndConsumableItem_Id(vehicle, item.getId())
                                                        .ifPresent(vc -> {
                                                                applyInferredConsumableStatus(vehicle, item, vc);
                                                                vehicleConsumableRepository.save(vc);
                                                        });
                                });
        }

        /**
         * 차량 등록 시 소모품 미입력 시 사용하는 추론 로직과 동일.
         * 현재 주행거리·교체 주기로 "마지막 교체 시점"을 추정하고 잔존 수명(%)을 계산한다.
         */
        private void applyInferredConsumableStatus(Vehicle vehicle, ConsumableItem item, VehicleConsumable vc) {
                double currentMileage = vehicle.getTotalMileage() != null ? vehicle.getTotalMileage() : 0.0;
                Integer interval = item.getDefaultIntervalMileage();
                if (interval == null || interval <= 0) {
                        vc.setLastReplacedAt(null);
                        vc.setLastReplacedMileage(0.0);
                        vc.setRemainingLife(100.0);
                        vc.setIsInferred(true);
                        return;
                }
                double dailyMileage = 41.0;
                Double lastMileage = currentMileage - (currentMileage % interval);
                long daysDiff = Math.abs(Math.round((currentMileage - lastMileage) / dailyMileage));
                LocalDateTime lastAt = LocalDateTime.now().minusDays(daysDiff);
                vc.setLastReplacedAt(lastAt);
                vc.setLastReplacedMileage(lastMileage);
                vc.setIsInferred(true);
                double distanceDriven = currentMileage - lastMileage;
                double lifePercentage = 100.0 - (distanceDriven / interval * 100.0);
                vc.updateRemainingLife(Math.max(0.0, Math.min(100.0, lifePercentage)));
        }

        /**
         * 특정 항목이 없을 경우 '기타' 항목을 반환하거나, '기타'조차 없으면 자동 생성하여 반환합니다.
         */
        private ConsumableItem getOrCreateOtherItem() {
                return consumableItemRepository.findByCode("OTHER")
                                .orElseGet(() -> {
                                        ConsumableItem other = new ConsumableItem();
                                        other.setCode("OTHER");
                                        other.setName("기타 정비");
                                        other.setDefaultIntervalMileage(0);
                                        return consumableItemRepository.save(other);
                                });
        }
}
