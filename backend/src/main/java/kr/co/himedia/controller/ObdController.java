package kr.co.himedia.controller;

import java.util.List;
import java.util.UUID;
import kr.co.himedia.dto.common.VehicleIdRequest;
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

    /**
     * [BE-TD-002] 벌크 로그 수집
     * OBD 장치로부터 수집된 3분 단위의 로그 데이터를 저장하고 주행 통계를 갱신합니다.
     */
    @PostMapping("/batch")
    public ResponseEntity<ApiResponse<Void>> uploadObdLogs(@RequestBody List<ObdLogDto> obdLogDtos) {
        obdService.saveObdLogs(obdLogDtos);
        return ResponseEntity.ok(ApiResponse.success(null));
    }

    /**
     * [BE-TD-006 (Partial)] 차량 연결 상태 조회
     * 차량의 실시간 연결 상태 및 주행/정차 여부를 조회합니다.
     */
    @GetMapping("/status/{vehicleId}")
    public ResponseEntity<ApiResponse<ConnectionStatusDto>> getConnectionStatus(
            @PathVariable("vehicleId") UUID vehicleId) {
        return ResponseEntity.ok(ApiResponse.success(obdService.getConnectionStatus(vehicleId)));
    }

    /**
     * 앱 수동 연결 해제
     * 사용자가 앱에서 수동으로 연결을 끊었을 때, 현재 세션을 즉시 종료 처리합니다.
     */
    @PostMapping("/status/disconnect")
    public ResponseEntity<ApiResponse<Void>> disconnectVehicle(@RequestBody VehicleIdRequest req) {
        obdService.disconnectVehicle(req.getVehicleId());
        return ResponseEntity.ok(ApiResponse.success(null));
    }
}
