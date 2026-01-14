package kr.co.himedia.controller;

import java.util.List;
import java.util.UUID;
import kr.co.himedia.dto.obd.ConnectionStatusDto;
import kr.co.himedia.dto.obd.ObdLogDto;
import kr.co.himedia.service.ObdService;
import kr.co.himedia.common.ApiResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/telemetry")
@RequiredArgsConstructor
public class ObdController {

    private final ObdService obdService;

    @PostMapping("/batch")
    public ResponseEntity<ApiResponse<Void>> uploadObdLogs(@RequestBody List<ObdLogDto> obdLogDtos) {
        obdService.saveObdLogs(obdLogDtos);
        return ResponseEntity.ok(ApiResponse.success(null));
    }

    @GetMapping("/status/{vehicleId}")
    public ResponseEntity<ApiResponse<ConnectionStatusDto>> getConnectionStatus(
            @PathVariable("vehicleId") UUID vehicleId) {
        return ResponseEntity.ok(ApiResponse.success(obdService.getConnectionStatus(vehicleId)));
    }

    @PostMapping("/status/{vehicleId}/disconnect")
    public ResponseEntity<ApiResponse<Void>> disconnectVehicle(@PathVariable("vehicleId") UUID vehicleId) {
        obdService.disconnectVehicle(vehicleId);
        return ResponseEntity.ok(ApiResponse.success(null));
    }
}
