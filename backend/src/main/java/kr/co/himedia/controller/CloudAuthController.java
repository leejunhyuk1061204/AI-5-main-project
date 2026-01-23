package kr.co.himedia.controller;

import jakarta.validation.Valid;
import kr.co.himedia.common.ApiResponse;
import kr.co.himedia.dto.cloud.CloudVehicleRegisterRequest;
import kr.co.himedia.entity.Vehicle;
import kr.co.himedia.service.CloudAuthService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.UUID;

@Slf4j
@RestController
@RequestMapping("/auth/cloud")
@RequiredArgsConstructor
public class CloudAuthController {

    private final CloudAuthService cloudAuthService;

    /**
     * 차량의 VIN 정보를 업데이트합니다 (프론트엔드에서 OBD로 획득한 VIN 전달).
     */
    @PatchMapping("/vin")
    public ResponseEntity<ApiResponse<Void>> updateVin(
            @Valid @RequestBody kr.co.himedia.dto.cloud.VinUpdateRequest request) {

        log.info("[CloudAuth] VIN 업데이트 요청 - vehicleId: {}, vin: {}", request.getVehicleId(), request.getVin());

        // 1. VIN 암호화 저장
        cloudAuthService.updateVehicleVin(request.getVehicleId(), request.getVin());

        return ResponseEntity.ok(ApiResponse.success(null));
    }

    /**
     * 사용자가 선택한 클라우드 차량을 시스템에 등록합니다.
     */
    @PostMapping("/register")
    public ResponseEntity<ApiResponse<Vehicle>> registerCloudVehicle(
            @RequestParam UUID userId,
            @Valid @RequestBody CloudVehicleRegisterRequest request) {

        log.info("[Phase 3] 차량 등록 API 호출 - userId: {}, vehicleId: {}", userId, request.getProviderVehicleId());

        Vehicle vehicle = cloudAuthService.registerCloudVehicle(userId, request);

        return ResponseEntity.status(HttpStatus.CREATED)
                .body(ApiResponse.success(vehicle));
    }

    /**
     * 하이모빌리티 클라우드 차량의 데이터를 강제로 동기화합니다.
     */
    @PostMapping("/sync")
    public ResponseEntity<ApiResponse<Void>> syncVehicleData(
            @RequestParam UUID vehicleId) {

        log.info("[CloudAuth] 차량 데이터 동기화 요청 - vehicleId: {}", vehicleId);
        cloudAuthService.syncVehicleData(vehicleId, true); // 수동 동기화 시에도 테이블 반영
        return ResponseEntity.ok(ApiResponse.success(null));
    }

    /**
     * 클라우드 차량 연동을 해제합니다.
     */
    @PostMapping("/revoke")
    public ResponseEntity<ApiResponse<Void>> revokeCloudVehicle(
            @RequestParam UUID userId,
            @RequestBody CloudVehicleRegisterRequest request) {

        log.info("[CloudAuth] 차량 연동 해제 요청 - userId: {}, vehicleId: {}", userId, request.getProviderVehicleId());
        cloudAuthService.revokeCloudVehicle(userId, request);

        return ResponseEntity.ok(ApiResponse.success(null));
    }
}
