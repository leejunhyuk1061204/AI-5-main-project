package kr.co.himedia.controller;

import jakarta.validation.Valid;
import kr.co.himedia.dto.common.VehicleIdRequest;
import kr.co.himedia.dto.vehicle.VehicleDto;
import kr.co.himedia.service.VehicleService;
import kr.co.himedia.common.ApiResponse;
import kr.co.himedia.security.CustomUserDetails;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/vehicles")
@RequiredArgsConstructor
public class VehicleController {

    private final VehicleService vehicleService;

    /**
     * [BE-VH-001] 차량 수동 등록
     * 사용자가 직접 차량 정보를 입력하여 등록합니다.
     */
    @PostMapping
    public ResponseEntity<ApiResponse<VehicleDto.Response>> registerVehicle(
            @AuthenticationPrincipal CustomUserDetails userDetails,
            @Valid @RequestBody VehicleDto.RegistrationRequest request) {
        VehicleDto.Response response = vehicleService.registerVehicle(userDetails.getUserId(), request);
        return ResponseEntity.status(HttpStatus.CREATED).body(ApiResponse.success(response));
    }

    /**
     * [BE-VH-002] OBD 기반 차량 자동 등록
     * OBD 장치에서 수집된 VIN을 통해 차량을 자동으로 등록합니다.
     */
    @PostMapping("/obd")
    public ResponseEntity<ApiResponse<VehicleDto.Response>> registerVehicleByObd(
            @AuthenticationPrincipal CustomUserDetails userDetails,
            @Valid @RequestBody VehicleDto.ObdRegistrationRequest request) {
        VehicleDto.Response response = vehicleService.registerVehicleByObd(userDetails.getUserId(), request);
        return ResponseEntity.status(HttpStatus.CREATED).body(ApiResponse.success(response));
    }

    /**
     * [BE-VH-004] 보유 차량 목록 조회
     * 사용자가 등록한 모든 차량의 요약 정보를 반환합니다.
     */
    @GetMapping
    public ResponseEntity<ApiResponse<List<VehicleDto.Response>>> getVehicleList(
            @AuthenticationPrincipal CustomUserDetails userDetails) {
        List<VehicleDto.Response> responseList = vehicleService.getVehicleList(userDetails.getUserId());
        return ResponseEntity.ok(ApiResponse.success(responseList));
    }

    /**
     * [BE-VH-004] 차량 상세 정보 조회
     * 특정 차량의 상세 정보를 반환합니다.
     */
    @GetMapping("/{vehicleId}")
    public ResponseEntity<ApiResponse<VehicleDto.Response>> getVehicleDetail(@PathVariable UUID vehicleId) {
        VehicleDto.Response response = vehicleService.getVehicleDetail(vehicleId);
        return ResponseEntity.ok(ApiResponse.success(response));
    }

    /**
     * [BE-VH-004] 차량 정보 수정
     * 차량의 닉네임이나 메모 등을 수정합니다.
     */
    @PutMapping("/{vehicleId}")
    public ResponseEntity<ApiResponse<VehicleDto.Response>> updateVehicle(
            @PathVariable UUID vehicleId,
            @Valid @RequestBody VehicleDto.UpdateRequest request) {
        VehicleDto.Response response = vehicleService.updateVehicle(vehicleId, request);
        return ResponseEntity.ok(ApiResponse.success(response));
    }

    /**
     * [BE-VH-006] 대표 차량 설정
     * 해당 차량을 사용자의 메인(Primary) 차량으로 설정합니다.
     */
    @PatchMapping("/primary")
    public ResponseEntity<ApiResponse<Void>> setPrimaryVehicle(
            @AuthenticationPrincipal CustomUserDetails userDetails,
            @Valid @RequestBody VehicleIdRequest req) {
        vehicleService.setPrimaryVehicle(userDetails.getUserId(), req.getVehicleId());
        return ResponseEntity.ok(ApiResponse.success(null));
    }

    /**
     * [BE-VH-007] 차량 삭제
     * 차량을 삭제 처리합니다 (Soft Delete).
     */
    @DeleteMapping("/{vehicleId}")
    public ResponseEntity<ApiResponse<Void>> deleteVehicle(@PathVariable UUID vehicleId) {
        vehicleService.deleteVehicle(vehicleId);
        return ResponseEntity.ok(ApiResponse.success(null));
    }
}
