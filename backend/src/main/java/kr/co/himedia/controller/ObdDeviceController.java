package kr.co.himedia.controller;

import kr.co.himedia.common.ApiResponse;
import kr.co.himedia.dto.obd.*;
import kr.co.himedia.security.CustomUserDetails;
import kr.co.himedia.service.ObdDeviceService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import jakarta.validation.Valid;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/obd")
@RequiredArgsConstructor
public class ObdDeviceController {

    private final ObdDeviceService obdDeviceService;

    @GetMapping("/devices")
    public ResponseEntity<ApiResponse<List<ObdDeviceDto>>> getDevices(
            @AuthenticationPrincipal CustomUserDetails userDetails) {
        UUID userId = userDetails.getUserId();
        return ResponseEntity.ok(ApiResponse.success(obdDeviceService.getDevicesByUser(userId)));
    }

    @PostMapping("/devices")
    public ResponseEntity<ApiResponse<ObdDeviceDto>> registerDevice(
            @AuthenticationPrincipal CustomUserDetails userDetails,
            @Valid @RequestBody ObdDeviceRegisterRequest request) {
        UUID userId = userDetails.getUserId();
        return ResponseEntity.ok(ApiResponse.success(obdDeviceService.registerDevice(userId, request)));
    }

    @PutMapping("/devices/{deviceId}/connect")
    public ResponseEntity<ApiResponse<Void>> recordConnect(
            @AuthenticationPrincipal CustomUserDetails userDetails,
            @PathVariable String deviceId,
            @RequestBody ConnectHistoryRequest request) {
        UUID userId = userDetails.getUserId();
        obdDeviceService.recordConnect(userId, deviceId, request);
        return ResponseEntity.ok(ApiResponse.success(null));
    }

    @PostMapping("/resolve-vehicle")
    public ResponseEntity<ApiResponse<Map<String, UUID>>> resolveVehicle(
            @AuthenticationPrincipal CustomUserDetails userDetails,
            @RequestBody ResolveVehicleRequest request) {
        UUID userId = userDetails.getUserId();
        UUID vehicleId = obdDeviceService.resolveVehicle(userId, request);
        return ResponseEntity.ok(ApiResponse.success(Map.of("vehicleId", vehicleId)));
    }
}
