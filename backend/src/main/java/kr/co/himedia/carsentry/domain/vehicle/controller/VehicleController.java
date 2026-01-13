package kr.co.himedia.carsentry.domain.vehicle.controller;

import kr.co.himedia.carsentry.domain.vehicle.dto.VehicleDto;
import kr.co.himedia.carsentry.domain.vehicle.service.VehicleService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/vehicles")
@RequiredArgsConstructor
public class VehicleController {

    private final VehicleService vehicleService;

    // TODO: userId should be extracted from SecurityContext/JWT in a real scenario.
    // For now, passing it as a header or parameter for testing, or assuming a fixed
    // user for MVP testing until Auth is fully integrated.
    // However, the plan implies Auth is separate. I will assume userId is passed
    // via @RequestHeader("X-User-Id") for now to facilitate independent testing
    // without Auth module,
    // or better, standard practice is to use a resolver.
    // Given the constraints and early stage, I'll allow it as a RequestHeader
    // "X-User-Id".

    @PostMapping
    public ResponseEntity<VehicleDto.Response> registerVehicle(
            @RequestHeader("X-User-Id") UUID userId,
            @RequestBody VehicleDto.RegistrationRequest request) {
        VehicleDto.Response response = vehicleService.registerVehicle(userId, request);
        return ResponseEntity.status(HttpStatus.CREATED).body(response);
    }

    @GetMapping
    public ResponseEntity<List<VehicleDto.Response>> getVehicleList(
            @RequestHeader("X-User-Id") UUID userId) {
        List<VehicleDto.Response> responseList = vehicleService.getVehicleList(userId);
        return ResponseEntity.ok(responseList);
    }

    @GetMapping("/{vehicleId}")
    public ResponseEntity<VehicleDto.Response> getVehicleDetail(@PathVariable UUID vehicleId) {
        VehicleDto.Response response = vehicleService.getVehicleDetail(vehicleId);
        return ResponseEntity.ok(response);
    }

    @PutMapping("/{vehicleId}")
    public ResponseEntity<VehicleDto.Response> updateVehicle(
            @PathVariable UUID vehicleId,
            @RequestBody VehicleDto.UpdateRequest request) {
        VehicleDto.Response response = vehicleService.updateVehicle(vehicleId, request);
        return ResponseEntity.ok(response);
    }

    @PatchMapping("/{vehicleId}/primary")
    public ResponseEntity<Void> setPrimaryVehicle(
            @RequestHeader("X-User-Id") UUID userId,
            @PathVariable UUID vehicleId) {
        vehicleService.setPrimaryVehicle(userId, vehicleId);
        return ResponseEntity.ok().build();
    }

    @DeleteMapping("/{vehicleId}")
    public ResponseEntity<Void> deleteVehicle(@PathVariable UUID vehicleId) {
        vehicleService.deleteVehicle(vehicleId);
        return ResponseEntity.noContent().build();
    }
}
