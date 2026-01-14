package kr.co.himedia.controller;

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

    @PostMapping
    public ResponseEntity<ApiResponse<VehicleDto.Response>> registerVehicle(
            @AuthenticationPrincipal CustomUserDetails userDetails,
            @RequestBody VehicleDto.RegistrationRequest request) {
        VehicleDto.Response response = vehicleService.registerVehicle(userDetails.getUserId(), request);
        return ResponseEntity.status(HttpStatus.CREATED).body(ApiResponse.success(response));
    }

    @GetMapping
    public ResponseEntity<ApiResponse<List<VehicleDto.Response>>> getVehicleList(
            @AuthenticationPrincipal CustomUserDetails userDetails) {
        List<VehicleDto.Response> responseList = vehicleService.getVehicleList(userDetails.getUserId());
        return ResponseEntity.ok(ApiResponse.success(responseList));
    }

    @GetMapping("/{vehicleId}")
    public ResponseEntity<ApiResponse<VehicleDto.Response>> getVehicleDetail(@PathVariable UUID vehicleId) {
        VehicleDto.Response response = vehicleService.getVehicleDetail(vehicleId);
        return ResponseEntity.ok(ApiResponse.success(response));
    }

    @PutMapping("/{vehicleId}")
    public ResponseEntity<ApiResponse<VehicleDto.Response>> updateVehicle(
            @PathVariable UUID vehicleId,
            @RequestBody VehicleDto.UpdateRequest request) {
        VehicleDto.Response response = vehicleService.updateVehicle(vehicleId, request);
        return ResponseEntity.ok(ApiResponse.success(response));
    }

    @PatchMapping("/{vehicleId}/primary")
    public ResponseEntity<ApiResponse<Void>> setPrimaryVehicle(
            @AuthenticationPrincipal CustomUserDetails userDetails,
            @PathVariable UUID vehicleId) {
        vehicleService.setPrimaryVehicle(userDetails.getUserId(), vehicleId);
        return ResponseEntity.ok(ApiResponse.success(null));
    }

    @DeleteMapping("/{vehicleId}")
    public ResponseEntity<ApiResponse<Void>> deleteVehicle(@PathVariable UUID vehicleId) {
        vehicleService.deleteVehicle(vehicleId);
        return ResponseEntity.ok(ApiResponse.success(null));
    }
}
