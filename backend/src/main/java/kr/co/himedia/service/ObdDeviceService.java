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
import java.util.Optional;
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
        Vehicle vehicle = vehicleRepository.findByVehicleIdAndDeletedAtIsNull(request.getVehicleId())
                .orElseThrow(() -> new BaseException(ErrorCode.VEHICLE_NOT_FOUND));

        // 0902로 수신한 VIN이 있고, 해당 차량에 아직 VIN이 없을 때만 저장
        if (request.getVin() != null && !request.getVin().isBlank()
                && (vehicle.getVin() == null || vehicle.getVin().isBlank())) {
            vehicle.updateVin(request.getVin().trim());
            vehicleRepository.save(vehicle);
            log.info("[recordConnect] VIN 저장 완료 vehicleId={}", request.getVehicleId());
        }

        ObdDeviceVehicleHistory history = historyRepository
                .findByObdDeviceIdAndVehiclesId(device.getId(), request.getVehicleId())
                .orElse(ObdDeviceVehicleHistory.builder()
                        .obdDeviceId(device.getId())
                        .vehiclesId(request.getVehicleId())
                        .lastConnectedAt(OffsetDateTime.now())
                        .build());
        history.setLastConnectedAt(OffsetDateTime.now());
        if (request.getCalid() != null)
            history.setCalid(request.getCalid());
        if (request.getCvn() != null)
            history.setCvn(request.getCvn());
        historyRepository.save(history);
    }

    /**
     * 차량 특정: VIN → CALID → CVN → 해당 장치 마지막 연결 차량 → 대표 차량.
     * 각 단계에서 null/blank면 해당 단계 스킵. 후보가 정확히 1건일 때만 반환, 0건이면 다음 단계, 2건 이상이면 다음 단계로
     * 진행.
     */
    @Transactional(readOnly = true)
    public UUID resolveVehicle(UUID userId, ResolveVehicleRequest request) {
        log.info("[resolveVehicle] start userId={} deviceId={} vin={} calid={} cvn={}",
                userId, request.getDeviceId(),
                request.getVin() != null ? "***" : null,
                request.getCalid() != null ? "***" : null,
                request.getCvn() != null ? "***" : null);

        if (request.getVin() != null && !request.getVin().isBlank()) {
            Vehicle byVin = vehicleRepository.findByVin(request.getVin().trim()).orElse(null);
            if (byVin != null && byVin.getUserId().equals(userId)) {
                log.info("[resolveVehicle] step=VIN match vehicleId={}", byVin.getVehicleId());
                return byVin.getVehicleId();
            }
            log.debug("[resolveVehicle] step=VIN no match or not owner, continue");
        }

        ObdDevice device = null;
        if (request.getDeviceId() != null && !request.getDeviceId().isBlank()) {
            device = obdDeviceRepository.findByUserIdAndDeviceId(userId, request.getDeviceId()).orElse(null);
        }
        if (device == null) {
            log.debug("[resolveVehicle] no device for deviceId, skip CALID/CVN/last");
        } else {
            if (request.getCalid() != null && !request.getCalid().isBlank()) {
                List<ObdDeviceVehicleHistory> byCalid = historyRepository.findAllByObdDeviceIdAndCalid(device.getId(),
                        request.getCalid().trim());
                if (byCalid.size() == 1) {
                    UUID vehicleId = byCalid.get(0).getVehiclesId();
                    log.info("[resolveVehicle] step=CALID single match vehicleId={}", vehicleId);
                    return vehicleId;
                }
                if (byCalid.size() > 1) {
                    log.debug("[resolveVehicle] step=CALID multiple matches count={}, try CVN", byCalid.size());
                }
            }

            if (request.getCvn() != null && !request.getCvn().isBlank()) {
                String cvnTrim = request.getCvn().trim();
                if (request.getCalid() != null && !request.getCalid().isBlank()) {
                    Optional<ObdDeviceVehicleHistory> byCalidCvn = historyRepository
                            .findByObdDeviceIdAndCalidAndCvn(device.getId(), request.getCalid().trim(), cvnTrim);
                    if (byCalidCvn.isPresent()) {
                        UUID vehicleId = byCalidCvn.get().getVehiclesId();
                        log.info("[resolveVehicle] step=CALID+CVN match vehicleId={}", vehicleId);
                        return vehicleId;
                    }
                }
                List<ObdDeviceVehicleHistory> byCvn = historyRepository.findAllByObdDeviceIdAndCvn(device.getId(),
                        cvnTrim);
                if (byCvn.size() == 1) {
                    UUID vehicleId = byCvn.get(0).getVehiclesId();
                    log.info("[resolveVehicle] step=CVN single match vehicleId={}", vehicleId);
                    return vehicleId;
                }
                if (byCvn.size() > 1) {
                    UUID vehicleId = byCvn.get(0).getVehiclesId();
                    log.info("[resolveVehicle] step=CVN multiple matches, take most recent vehicleId={}", vehicleId);
                    return vehicleId;
                }
                log.debug("[resolveVehicle] step=CVN no match, continue");
            }

            Optional<ObdDeviceVehicleHistory> last = historyRepository
                    .findTopByObdDeviceIdOrderByLastConnectedAtDesc(device.getId());
            if (last.isPresent()) {
                UUID vehicleId = last.get().getVehiclesId();
                log.info("[resolveVehicle] step=LAST_CONNECTED vehicleId={}", vehicleId);
                return vehicleId;
            }
        }

        UUID primaryId = vehicleRepository.findByUserIdAndIsPrimaryTrueAndDeletedAtIsNull(userId)
                .map(Vehicle::getVehicleId)
                .orElseThrow(() -> new BaseException(ErrorCode.VEHICLE_NOT_FOUND));
        log.info("[resolveVehicle] step=PRIMARY vehicleId={}", primaryId);
        return primaryId;
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
