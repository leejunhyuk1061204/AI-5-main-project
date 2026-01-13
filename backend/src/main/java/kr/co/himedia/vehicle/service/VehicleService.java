package kr.co.himedia.vehicle.service;

import kr.co.himedia.vehicle.dto.VehicleDto;
import kr.co.himedia.vehicle.entity.Vehicle;
import kr.co.himedia.vehicle.repository.VehicleRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.UUID;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class VehicleService {

    private final VehicleRepository vehicleRepository;

    @Transactional
    public VehicleDto.Response registerVehicle(UUID userId, VehicleDto.RegistrationRequest request) {
        // 첫 차량 등록 시 자동으로 대표 차량으로 설정
        boolean hasVehicles = !vehicleRepository.findByUserIdAndDeletedAtIsNull(userId).isEmpty();

        Vehicle vehicle = request.toEntity(userId);
        if (!hasVehicles) {
            vehicle.setPrimary(true);
        }

        Vehicle savedVehicle = vehicleRepository.save(vehicle);
        return VehicleDto.Response.from(savedVehicle);
    }

    public List<VehicleDto.Response> getVehicleList(UUID userId) {
        return vehicleRepository.findByUserIdAndDeletedAtIsNull(userId).stream()
                .map(VehicleDto.Response::from)
                .collect(Collectors.toList());
    }

    public VehicleDto.Response getVehicleDetail(UUID vehicleId) {
        Vehicle vehicle = vehicleRepository.findByVehicleIdAndDeletedAtIsNull(vehicleId)
                .orElseThrow(() -> new IllegalArgumentException("해당 차량을 찾을 수 없습니다."));
        return VehicleDto.Response.from(vehicle);
    }

    @Transactional
    public VehicleDto.Response updateVehicle(UUID vehicleId, VehicleDto.UpdateRequest request) {
        Vehicle vehicle = vehicleRepository.findByVehicleIdAndDeletedAtIsNull(vehicleId)
                .orElseThrow(() -> new IllegalArgumentException("해당 차량을 찾을 수 없습니다."));

        vehicle.updateInfo(request.getNickname(), request.getMemo());
        return VehicleDto.Response.from(vehicle);
    }

    @Transactional
    public void setPrimaryVehicle(UUID userId, UUID vehicleId) {
        Vehicle newPrimary = vehicleRepository.findByVehicleIdAndDeletedAtIsNull(vehicleId)
                .orElseThrow(() -> new IllegalArgumentException("해당 차량을 찾을 수 없습니다."));

        if (!newPrimary.getUserId().equals(userId)) {
            throw new IllegalArgumentException("잘못된 접근입니다."); // User ownership check
        }

        // 기존 대표 차량 해제
        vehicleRepository.findByUserIdAndIsPrimaryTrueAndDeletedAtIsNull(userId)
                .ifPresent(v -> v.setPrimary(false));

        // 새로운 대표 차량 설정
        newPrimary.setPrimary(true);
    }

    @Transactional
    public void deleteVehicle(UUID vehicleId) {
        Vehicle vehicle = vehicleRepository.findByVehicleIdAndDeletedAtIsNull(vehicleId)
                .orElseThrow(() -> new IllegalArgumentException("해당 차량을 찾을 수 없습니다."));
        vehicle.delete();
    }
}
