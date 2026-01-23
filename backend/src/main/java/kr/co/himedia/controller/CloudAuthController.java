package kr.co.himedia.controller;

import jakarta.validation.Valid;
import kr.co.himedia.common.ApiResponse;
import kr.co.himedia.dto.cloud.CloudVehicleRegisterRequest;
import kr.co.himedia.dto.cloud.CloudVehicleResponse;
import kr.co.himedia.entity.CloudProvider;
import kr.co.himedia.entity.Vehicle;
import kr.co.himedia.service.CloudAuthService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
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

        log.info("[CloudAuth] VIN 업데이트 요청 - vehicleId: {}", request.getVehicleId());
        cloudAuthService.updateVehicleVin(request.getVehicleId(), request.getVin());
        return ResponseEntity.ok(ApiResponse.success(null));
    }

    /**
     * 연동된 클라우드 계정의 차량 목록을 조회합니다.
     */
    @GetMapping("/vehicles")
    public ResponseEntity<ApiResponse<List<CloudVehicleResponse>>> getConnectedVehicles(
            @RequestParam UUID userId,
            @RequestParam CloudProvider provider) {

        log.info("[Phase 3] 차량 목록 조회 API 호출 - userId: {}, provider: {}", userId, provider);

        List<CloudVehicleResponse> vehicles = cloudAuthService.getConnectedVehicles(userId, provider);

        return ResponseEntity.ok(ApiResponse.success(vehicles));
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
}
