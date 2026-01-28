package kr.co.himedia.service;

import kr.co.himedia.common.exception.BaseException;
import kr.co.himedia.common.exception.ErrorCode;
import kr.co.himedia.dto.vehicle.VehicleDto;
import kr.co.himedia.entity.Vehicle;
import kr.co.himedia.entity.ConsumableItem;
import kr.co.himedia.entity.VehicleConsumable;
import kr.co.himedia.entity.VehicleSpec;
import kr.co.himedia.repository.ConsumableItemRepository;
import kr.co.himedia.repository.VehicleConsumableRepository;
import kr.co.himedia.repository.VehicleRepository;
import kr.co.himedia.repository.VehicleSpecRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.time.temporal.ChronoUnit;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class VehicleService {

    private final VehicleRepository vehicleRepository;
    private final ConsumableItemRepository consumableItemRepository;
    private final VehicleConsumableRepository vehicleConsumableRepository;
    private final VehicleSpecRepository vehicleSpecRepository;
    private final kr.co.himedia.common.util.EncryptionUtils encryptionUtils;

    // VIN 암호화 업데이트
    @Transactional
    public void updateVehicleVin(UUID vehicleId, String plainVin) {
        Vehicle vehicle = vehicleRepository.findById(vehicleId)
                .orElseThrow(() -> new BaseException(ErrorCode.VEHICLE_NOT_FOUND));

        String encryptedVin = encryptionUtils.encrypt(plainVin);
        vehicle.updateVin(encryptedVin);
        vehicleRepository.save(vehicle);
        log.info("[VehicleService] 차량 VIN 암호화 업데이트 완료 - vehicleId: {}", vehicleId);
    }

    // 차량 수동 등록 (첫 차량일 경우 대표 차량 설정)
    @Transactional
    public VehicleDto.Response registerVehicle(UUID userId, VehicleDto.RegistrationRequest request) {
        // VIN 중복 체크 (VIN이 입력된 경우에만)
        if (request.getVin() != null && !request.getVin().isBlank()) {
            String encryptedVin = encryptionUtils.encrypt(request.getVin());
            if (vehicleRepository.existsByVinAndDeletedAtIsNull(encryptedVin)) {
                throw new BaseException(ErrorCode.DUPLICATE_VIN);
            }
        }

        // 첫 차량 등록 시 자동적으로 대표 차량으로 설정
        boolean hasVehicles = !vehicleRepository.findByUserIdAndDeletedAtIsNullOrderByCreatedAtAsc(userId).isEmpty();

        Vehicle vehicle = request.toEntity(userId);
        if (request.getVin() != null && !request.getVin().isBlank()) {
            vehicle.updateVin(encryptionUtils.encrypt(request.getVin()));
        }

        if (!hasVehicles) {
            vehicle.setPrimary(true);
        }

        Vehicle savedVehicle = vehicleRepository.save(vehicle);

        // 9종 전체 소모품 초기화 (입력값 있으면 그것 사용, 미입력시 추론)
        registerConsumables(savedVehicle, request.getConsumables());

        return convertToDtoWithDecryptedVin(savedVehicle);
    }

    // OBD 기반 차량 자동 등록
    @Transactional
    public VehicleDto.Response registerVehicleByObd(UUID userId, VehicleDto.ObdRegistrationRequest request) {
        // VIN 중복 체크
        String encryptedVin = encryptionUtils.encrypt(request.getVin());
        if (vehicleRepository.existsByVinAndDeletedAtIsNull(encryptedVin)) {
            throw new BaseException(ErrorCode.DUPLICATE_VIN);
        }

        // 첫 차량 등록 시 자동적으로 대표 차량으로 설정
        boolean hasVehicles = !vehicleRepository.findByUserIdAndDeletedAtIsNullOrderByCreatedAtAsc(userId).isEmpty();

        Vehicle vehicle = request.toEntity(userId);
        vehicle.updateVin(encryptedVin);

        if (!hasVehicles) {
            vehicle.setPrimary(true);
        }

        Vehicle savedVehicle = vehicleRepository.save(vehicle);
        return convertToDtoWithDecryptedVin(savedVehicle);
    }

    // 사용자의 보유 차량 목록 조회
    public List<VehicleDto.Response> getVehicleList(UUID userId) {
        return vehicleRepository.findByUserIdAndDeletedAtIsNullOrderByCreatedAtAsc(userId).stream()
                .map(this::convertToDtoWithDecryptedVin)
                .collect(Collectors.toList());
    }

    // 차량 상세 정보 조회
    public VehicleDto.Response getVehicleDetail(UUID vehicleId) {
        Vehicle vehicle = vehicleRepository.findByVehicleIdAndDeletedAtIsNull(vehicleId)
                .orElseThrow(() -> new BaseException(ErrorCode.VEHICLE_NOT_FOUND));

        VehicleDto.Response response = convertToDtoWithDecryptedVin(vehicle);

        // 상세 제원 정보 (VehicleSpec) 추가 조회 및 매핑
        vehicleSpecRepository.findByVehicle(vehicle).ifPresent(spec -> {
            response.setLength(spec.getLength());
            response.setWidth(spec.getWidth());
            response.setHeight(spec.getHeight());
            response.setDisplacement(spec.getDisplacement());
            response.setEngineType(spec.getEngineType());
            response.setMaxPower(spec.getMaxPower());
            response.setMaxTorque(spec.getMaxTorque());
            response.setTireSizeFront(spec.getTireSizeFront());
            response.setTireSizeRear(spec.getTireSizeRear());
            response.setOfficialFuelEconomy(spec.getOfficialFuelEconomy());
        });

        return response;
    }

    // 차량 정보(별명, 메모) 수정
    @Transactional
    public VehicleDto.Response updateVehicle(UUID vehicleId, VehicleDto.UpdateRequest request) {
        Vehicle vehicle = vehicleRepository.findByVehicleIdAndDeletedAtIsNull(vehicleId)
                .orElseThrow(() -> new BaseException(ErrorCode.VEHICLE_NOT_FOUND));

        vehicle.updateInfo(request.getNickname(), request.getMemo());
        if (request.getCarNumber() != null && !request.getCarNumber().isBlank()) {
            vehicle.updateCarNumber(request.getCarNumber());
        }

        if (request.getTotalMileage() != null) {
            vehicle.updateTotalMileage(request.getTotalMileage());
        }

        if (request.getVin() != null && !request.getVin().isBlank() && !request.getVin().equals(vehicle.getVin())) {
            String encryptedVin = encryptionUtils.encrypt(request.getVin());
            if (vehicleRepository.existsByVinAndDeletedAtIsNull(encryptedVin)) {
                throw new BaseException(ErrorCode.DUPLICATE_VIN);
            }
            vehicle.updateVin(encryptedVin);
        }

        return convertToDtoWithDecryptedVin(vehicle);
    }

    // 대표 차량 설정
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

    /**
     * 소모품 일괄 등록 및 추론 로직
     */
    @Transactional
    public void registerConsumables(Vehicle vehicle, List<VehicleDto.ConsumableRegistrationRequest> requests) {
        log.info("[VehicleService] 소모품 일괄 등록 시작 - Vehicle: {}", vehicle.getVehicleId());

        List<ConsumableItem> allMasterItems = consumableItemRepository.findAll();
        Map<String, VehicleDto.ConsumableRegistrationRequest> requestMap = (requests == null) ? Map.of()
                : requests.stream()
                        .filter(r -> r.getCode() != null)
                        .collect(Collectors.toMap(
                                r -> r.getCode().trim().toUpperCase(),
                                r -> r,
                                (existing, replacement) -> existing));

        double currentMileage = vehicle.getTotalMileage() != null ? vehicle.getTotalMileage() : 0.0;
        LocalDateTime now = LocalDateTime.now();
        double dailyMileage = 41.0;

        for (ConsumableItem item : allMasterItems) {
            String itemCode = item.getCode().trim().toUpperCase();
            VehicleDto.ConsumableRegistrationRequest req = requestMap.get(itemCode);
            VehicleConsumable vc = new VehicleConsumable();
            vc.setVehicle(vehicle);
            vc.setConsumableItem(item);
            vc.setWearFactor(1.0);

            LocalDateTime lastAt;
            Double lastMileage;

            if (req != null) {
                lastAt = req.getLastReplacedAt();
                lastMileage = req.getLastReplacedMileage();

                if (lastAt == null && lastMileage != null) {
                    long daysDiff = Math.abs(Math.round((currentMileage - lastMileage) / dailyMileage));
                    lastAt = now.minusDays(daysDiff);
                } else if (lastAt != null && lastMileage == null) {
                    long daysDiff = Math.abs(ChronoUnit.DAYS.between(lastAt, now));
                    lastMileage = Math.max(0, currentMileage - (daysDiff * dailyMileage));
                } else if (lastAt == null && lastMileage == null) {
                    lastMileage = currentMileage - (currentMileage % item.getDefaultIntervalMileage());
                    long daysDiff = Math.abs(Math.round((currentMileage - lastMileage) / dailyMileage));
                    lastAt = now.minusDays(daysDiff);
                }
            } else {
                lastMileage = currentMileage - (currentMileage % item.getDefaultIntervalMileage());
                long daysDiff = Math.abs(Math.round((currentMileage - lastMileage) / dailyMileage));
                lastAt = now.minusDays(daysDiff);
            }

            vc.setLastReplacedAt(lastAt);
            vc.setLastReplacedMileage(lastMileage);
            vc.setIsInferred(req == null);

            double distanceDriven = currentMileage - lastMileage;
            double lifePercentage = 100.0 - (distanceDriven / item.getDefaultIntervalMileage() * 100.0);
            vc.updateRemainingLife(lifePercentage);

            vehicleConsumableRepository.save(vc);
        }
    }

    // [Helper] Entity -> DTO 변환 및 VIN 복호화 처리
    private VehicleDto.Response convertToDtoWithDecryptedVin(Vehicle vehicle) {
        VehicleDto.Response response = VehicleDto.Response.from(vehicle);
        if (vehicle.getVin() != null) {
            try {
                String decryptedVin = encryptionUtils.decrypt(vehicle.getVin());
                response.setVin(decryptedVin);
            } catch (Exception e) {
                log.warn("VIN 복호화 실패 - vehicleId: {}", vehicle.getVehicleId());
            }
        }
        return response;
    }
}
