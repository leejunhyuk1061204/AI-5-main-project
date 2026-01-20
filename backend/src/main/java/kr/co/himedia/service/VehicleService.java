package kr.co.himedia.service;

import kr.co.himedia.common.exception.BaseException;
import kr.co.himedia.common.exception.ErrorCode;
import kr.co.himedia.dto.vehicle.VehicleDto;
import kr.co.himedia.entity.Vehicle;
import kr.co.himedia.repository.VehicleRepository;
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

    // 차량 수동 등록 (첫 차량일 경우 대표 차량 설정)
    @Transactional
    public VehicleDto.Response registerVehicle(UUID userId, VehicleDto.RegistrationRequest request) {
        // VIN 중복 체크 (VIN이 입력된 경우에만)
        if (request.getVin() != null && !request.getVin().isBlank() &&
                vehicleRepository.existsByVinAndDeletedAtIsNull(request.getVin())) {
            throw new BaseException(ErrorCode.DUPLICATE_VIN);
        }

        // 첫 차량 등록 시 자동으로 대표 차량으로 설정
        boolean hasVehicles = !vehicleRepository.findByUserIdAndDeletedAtIsNull(userId).isEmpty();

        Vehicle vehicle = request.toEntity(userId);
        if (!hasVehicles) {
            vehicle.setPrimary(true);
        }

        Vehicle savedVehicle = vehicleRepository.save(vehicle);
        return VehicleDto.Response.from(savedVehicle);
    }

    // OBD 기반 차량 자동 등록
    @Transactional
    public VehicleDto.Response registerVehicleByObd(UUID userId, VehicleDto.ObdRegistrationRequest request) {
        // VIN 중복 체크
        if (vehicleRepository.existsByVinAndDeletedAtIsNull(request.getVin())) {
            throw new BaseException(ErrorCode.DUPLICATE_VIN);
        }

        // 첫 차량 등록 시 자동으로 대표 차량으로 설정
        boolean hasVehicles = !vehicleRepository.findByUserIdAndDeletedAtIsNull(userId).isEmpty();

        Vehicle vehicle = request.toEntity(userId);
        if (!hasVehicles) {
            vehicle.setPrimary(true);
        }

        Vehicle savedVehicle = vehicleRepository.save(vehicle);
        return VehicleDto.Response.from(savedVehicle);
    }

    // 사용자 소유 차량 목록 조회
    public List<VehicleDto.Response> getVehicleList(UUID userId) {
        return vehicleRepository.findByUserIdAndDeletedAtIsNull(userId).stream()
                .map(VehicleDto.Response::from)
                .collect(Collectors.toList());
    }

    // 차량 상세 정보 조회
    public VehicleDto.Response getVehicleDetail(UUID vehicleId) {
        Vehicle vehicle = vehicleRepository.findByVehicleIdAndDeletedAtIsNull(vehicleId)
                .orElseThrow(() -> new BaseException(ErrorCode.VEHICLE_NOT_FOUND));
        return VehicleDto.Response.from(vehicle);
    }

    // 차량 정보(별명, 메모) 수정
    @Transactional
    public VehicleDto.Response updateVehicle(UUID vehicleId, VehicleDto.UpdateRequest request) {
        Vehicle vehicle = vehicleRepository.findByVehicleIdAndDeletedAtIsNull(vehicleId)
                .orElseThrow(() -> new BaseException(ErrorCode.VEHICLE_NOT_FOUND));

        vehicle.updateInfo(request.getNickname(), request.getMemo());
        return VehicleDto.Response.from(vehicle);
    }

    // 대표 차량 설정 (기존 대표 차량 해제 후 설정)
    @Transactional
    public void setPrimaryVehicle(UUID userId, UUID vehicleId) {
        Vehicle newPrimary = vehicleRepository.findByVehicleIdAndDeletedAtIsNull(vehicleId)
                .orElseThrow(() -> new IllegalArgumentException("해당 차량을 찾을 수 없습니다."));

        if (!newPrimary.getUserId().equals(userId)) {
            throw new BaseException(ErrorCode.ACCESS_DENIED);
        }

        // 기존 대표 차량 해제
        vehicleRepository.findByUserIdAndIsPrimaryTrueAndDeletedAtIsNull(userId)
                .ifPresent(v -> v.setPrimary(false));

        // 새로운 대표 차량 설정
        newPrimary.setPrimary(true);
    }

    // 차량 삭제 (Soft Delete)
    @Transactional
    public void deleteVehicle(UUID vehicleId) {
        Vehicle vehicle = vehicleRepository.findByVehicleIdAndDeletedAtIsNull(vehicleId)
                .orElseThrow(() -> new BaseException(ErrorCode.VEHICLE_NOT_FOUND));
        vehicle.delete();
    }
}
