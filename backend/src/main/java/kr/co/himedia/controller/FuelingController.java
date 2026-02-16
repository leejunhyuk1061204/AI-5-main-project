package kr.co.himedia.controller;

import kr.co.himedia.common.ApiResponse;
import kr.co.himedia.dto.maintenance.FuelingHistoryRequest;
import kr.co.himedia.service.FuelingService;
import kr.co.himedia.dto.maintenance.FuelingHistoryResponse;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/fueling")
@RequiredArgsConstructor
public class FuelingController {

    private final FuelingService fuelingService;

    @PostMapping("/{vehicleId}")
    public ApiResponse<FuelingHistoryResponse> registerFueling(
            @PathVariable("vehicleId") UUID vehicleId,
            @RequestBody @Valid FuelingHistoryRequest request) {
        return ApiResponse.success(fuelingService.registerFueling(vehicleId, request));
    }

    @GetMapping("/{vehicleId}")
    public ApiResponse<List<FuelingHistoryResponse>> getFuelingHistory(@PathVariable("vehicleId") UUID vehicleId) {
        return ApiResponse.success(fuelingService.getFuelingHistory(vehicleId));
    }

    @DeleteMapping("/{fuelingId}")
    public ApiResponse<Void> deleteFueling(@PathVariable("fuelingId") UUID fuelingId) {
        fuelingService.deleteFueling(fuelingId);
        return ApiResponse.success(null);
    }
}
