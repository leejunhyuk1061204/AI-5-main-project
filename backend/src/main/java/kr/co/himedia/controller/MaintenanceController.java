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
@RequestMapping("/vehicles")
@RequiredArgsConstructor
public class MaintenanceController {

    private final MaintenanceService maintenanceService;

    /**
     * 정비 이력 등록 (리스트로 다중 등록 지원)
     */
    @PostMapping("/{vehicleId}/maintenance")
    public ApiResponse<List<MaintenanceHistoryResponse>> registerMaintenance(
            @PathVariable UUID vehicleId,
            @jakarta.validation.Valid @RequestBody List<MaintenanceHistoryRequest> requests) {

        List<MaintenanceHistoryResponse> responses = maintenanceService.registerMaintenanceList(vehicleId, requests);
        return ApiResponse.success(responses);
    }

    @GetMapping("/{vehicleId}/consumables")
    public ApiResponse<List<ConsumableStatusResponse>> getConsumables(
            @PathVariable UUID vehicleId) {

        List<ConsumableStatusResponse> response = maintenanceService.getConsumableStatus(vehicleId);
        return ApiResponse.success(response);
    }

    @PostMapping("/maintenance/ocr")
    public ApiResponse<kr.co.himedia.dto.maintenance.MaintenanceReceiptResponse> analyzeReceipt(
            @RequestParam("file") org.springframework.web.multipart.MultipartFile file) {
        return ApiResponse.success(maintenanceService.analyzeReceipt(file));
    }
}
