package kr.co.himedia.service;

import kr.co.himedia.common.exception.BaseException;
import kr.co.himedia.common.exception.ErrorCode;
import kr.co.himedia.dto.obd.ObdDeviceDto;
import kr.co.himedia.dto.obd.ConnectHistoryRequest;
import kr.co.himedia.dto.obd.ObdDeviceRegisterRequest;
import kr.co.himedia.dto.obd.ResolveVehicleRequest;
import kr.co.himedia.entity.ObdDevice;
import kr.co.himedia.entity.ObdDeviceVehicleHistory;
import kr.co.himedia.entity.Vehicle;
import kr.co.himedia.repository.ObdDeviceRepository;
import kr.co.himedia.repository.ObdDeviceVehicleHistoryRepository;
import kr.co.himedia.repository.VehicleRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class ObdDeviceService {

    private final ObdDeviceRepository obdDeviceRepository;
    private final ObdDeviceVehicleHistoryRepository historyRepository;
    private final VehicleRepository vehicleRepository;

    @Transactional(readOnly = true)
    public List<ObdDeviceDto> getDevicesByUser(UUID userId) {
        return obdDeviceRepository.findByUserIdOrderByUpdatedAtDesc(userId).stream()
                .map(this::toDto)
                .collect(Collectors.toList());
    }

    @Transactional
    public ObdDeviceDto registerDevice(UUID userId, ObdDeviceRegisterRequest request) {
        if (obdDeviceRepository.existsByUserIdAndDeviceId(userId, request.getDeviceId())) {
            ObdDevice existing = obdDeviceRepository.findByUserIdAndDeviceId(userId, request.getDeviceId())
                    .orElseThrow();
            if (request.getName() != null && !request.getName().isBlank()) {
                existing.setName(request.getName());
                existing.setUpdatedAt(java.time.LocalDateTime.now());
                obdDeviceRepository.save(existing);
            }
            return toDto(existing);
        }
        ObdDevice device = ObdDevice.builder()
                .userId(userId)
                .deviceId(request.getDeviceId())
                .deviceType(request.getDeviceType())
                .name(request.getName() != null ? request.getName() : request.getDeviceId())
                .build();
        device = obdDeviceRepository.save(device);
        return toDto(device);
    }

    @Transactional
    public void recordConnect(UUID userId, String deviceId, ConnectHistoryRequest request) {
        ObdDevice device = obdDeviceRepository.findByUserIdAndDeviceId(userId, deviceId)
                .orElseThrow(() -> new BaseException(ErrorCode.ENTITY_NOT_FOUND));
        vehicleRepository.findByVehicleIdAndDeletedAtIsNull(request.getVehicleId())
                .orElseThrow(() -> new BaseException(ErrorCode.VEHICLE_NOT_FOUND));

        ObdDeviceVehicleHistory history = historyRepository.findByObdDeviceIdAndVehiclesId(device.getId(), request.getVehicleId())
                .orElse(ObdDeviceVehicleHistory.builder()
                        .obdDeviceId(device.getId())
                        .vehiclesId(request.getVehicleId())
                        .lastConnectedAt(OffsetDateTime.now())
                        .build());
        history.setLastConnectedAt(OffsetDateTime.now());
        if (request.getCalid() != null) history.setCalid(request.getCalid());
        if (request.getCvn() != null) history.setCvn(request.getCvn());
        historyRepository.save(history);
    }

    /**
     * 차량 특정: VIN → CALID/CVN 매칭 → 해당 장치 마지막 연결 차량 → 대표 차량
     */
    @Transactional(readOnly = true)
    public UUID resolveVehicle(UUID userId, ResolveVehicleRequest request) {
        if (request.getVin() != null && !request.getVin().isBlank()) {
            Vehicle byVin = vehicleRepository.findByVin(request.getVin().trim()).orElse(null);
            if (byVin != null && byVin.getUserId().equals(userId))
                return byVin.getVehicleId();
        }

        if (request.getDeviceId() != null && !request.getDeviceId().isBlank()) {
            ObdDevice device = obdDeviceRepository.findByUserIdAndDeviceId(userId, request.getDeviceId()).orElse(null);
            if (device != null) {
                if (request.getCalid() != null && !request.getCalid().isBlank()) {
                    var byCalid = historyRepository.findByObdDeviceIdAndCalid(device.getId(), request.getCalid().trim());
                    if (byCalid.isPresent())
                        return byCalid.get().getVehiclesId();
                }
                var last = historyRepository.findTopByObdDeviceIdOrderByLastConnectedAtDesc(device.getId());
                if (last.isPresent())
                    return last.get().getVehiclesId();
            }
        }

        return vehicleRepository.findByUserIdAndIsPrimaryTrueAndDeletedAtIsNull(userId)
                .map(Vehicle::getVehicleId)
                .orElseThrow(() -> new BaseException(ErrorCode.VEHICLE_NOT_FOUND));
    }

    private ObdDeviceDto toDto(ObdDevice d) {
        return ObdDeviceDto.builder()
                .id(d.getId())
                .deviceId(d.getDeviceId())
                .deviceType(d.getDeviceType())
                .name(d.getName())
                .build();
    }
}
