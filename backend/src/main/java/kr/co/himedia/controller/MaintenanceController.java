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
@RequestMapping("/api/vehicles")
@RequiredArgsConstructor
public class MaintenanceController {

    private final MaintenanceService maintenanceService;

    @PostMapping("/{vehicleId}/maintenance")
    public ApiResponse<MaintenanceHistoryResponse> registerMaintenance(
            @PathVariable UUID vehicleId,
            @jakarta.validation.Valid @RequestBody MaintenanceHistoryRequest request) {

        MaintenanceHistoryResponse response = maintenanceService.registerMaintenance(vehicleId, request);
        return ApiResponse.success(response);
    }

    @GetMapping("/{vehicleId}/consumables")
    public ApiResponse<List<ConsumableStatusResponse>> getConsumables(
            @PathVariable UUID vehicleId) {

        List<ConsumableStatusResponse> response = maintenanceService.getConsumableStatus(vehicleId);
        return ApiResponse.success(response);
    }
}
