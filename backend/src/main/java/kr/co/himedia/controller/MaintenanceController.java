package kr.co.himedia.controller;

import kr.co.himedia.common.ApiResponse;
import kr.co.himedia.dto.maintenance.ConsumableStatusResponse;
import kr.co.himedia.dto.maintenance.MaintenanceHistoryRequest;
import kr.co.himedia.dto.maintenance.MaintenanceHistoryResponse;
import kr.co.himedia.service.MaintenanceService;
import java.util.List;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.UUID;

@RestController
@RequestMapping("/api/v1/vehicles")
@RequiredArgsConstructor
public class MaintenanceController {

    private final MaintenanceService maintenanceService;

    /**
     * 정비 이력 등록 (리스트로 다중 등록 지원)
     */
    @PostMapping("/{vehicleId}/maintenance")
    public ApiResponse<List<MaintenanceHistoryResponse>> registerMaintenance(
            @PathVariable("vehicleId") UUID vehicleId,
            @RequestBody List<MaintenanceHistoryRequest> requests) {

        List<MaintenanceHistoryResponse> responses = maintenanceService.registerMaintenanceList(vehicleId, requests);
        return ApiResponse.success(responses);
    }

    /**
     * 정비 이력 조회 (필터링 포함)
     */
    @GetMapping("/{vehicleId}/maintenance")
    public ApiResponse<List<MaintenanceHistoryResponse>> getMaintenanceHistory(
            @PathVariable("vehicleId") UUID vehicleId,
            @RequestParam(value = "itemCode", required = false) String itemCode,
            @RequestParam(value = "startDate", required = false) @org.springframework.format.annotation.DateTimeFormat(iso = org.springframework.format.annotation.DateTimeFormat.ISO.DATE) java.time.LocalDate startDate,
            @RequestParam(value = "endDate", required = false) @org.springframework.format.annotation.DateTimeFormat(iso = org.springframework.format.annotation.DateTimeFormat.ISO.DATE) java.time.LocalDate endDate) {

        List<MaintenanceHistoryResponse> responses = maintenanceService.getMaintenanceHistory(vehicleId, itemCode,
                startDate, endDate);
        return ApiResponse.success(responses);
    }

    @GetMapping("/{vehicleId}/consumables")
    public ApiResponse<List<ConsumableStatusResponse>> getConsumables(
            @PathVariable("vehicleId") UUID vehicleId) {

        List<ConsumableStatusResponse> response = maintenanceService.getConsumableStatus(vehicleId);
        return ApiResponse.success(response);
    }

    @PostMapping("/maintenance/ocr")
    public ApiResponse<kr.co.himedia.dto.maintenance.MaintenanceReceiptResponse> analyzeReceipt(
            @RequestParam("file") org.springframework.web.multipart.MultipartFile file) {
        return ApiResponse.success(maintenanceService.analyzeReceipt(file));
    }

    /**
     * 정비 이력 수정
     */
    @PutMapping("/maintenance/{historyId}")
    public ApiResponse<MaintenanceHistoryResponse> updateMaintenance(
            @PathVariable("historyId") UUID historyId,
            @RequestBody MaintenanceHistoryRequest request) {

        MaintenanceHistoryResponse response = maintenanceService.updateMaintenance(historyId, request);
        return ApiResponse.success(response);
    }

    /**
     * 정비 이력 삭제
     */
    @DeleteMapping("/maintenance/{historyId}")
    public ApiResponse<Void> deleteMaintenance(@PathVariable("historyId") UUID historyId) {
        maintenanceService.deleteMaintenance(historyId);
        return ApiResponse.success(null);
    }
}
