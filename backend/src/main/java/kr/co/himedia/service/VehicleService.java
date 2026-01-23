package kr.co.himedia.service;

import kr.co.himedia.common.exception.BaseException;
import kr.co.himedia.common.exception.ErrorCode;
import kr.co.himedia.dto.vehicle.VehicleDto;
import kr.co.himedia.entity.Vehicle;
import kr.co.himedia.entity.ConsumableItem;
import kr.co.himedia.entity.VehicleConsumable;
import kr.co.himedia.repository.ConsumableItemRepository;
import kr.co.himedia.repository.VehicleConsumableRepository;
import kr.co.himedia.repository.VehicleRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.time.temporal.ChronoUnit;
import java.util.List;
import java.util.Map;
import java.util.Optional;
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
    private final kr.co.himedia.common.util.EncryptionUtils encryptionUtils;

    // VIN 암호화 업데이트
    @Transactional
    public void updateVehicleVin(UUID vehicleId, String plainVin) {
        Vehicle vehicle = vehicleRepository.findById(vehicleId)
                .orElseThrow(() -> new kr.co.himedia.common.exception.BaseException(
                        kr.co.himedia.common.exception.ErrorCode.VEHICLE_NOT_FOUND));

        String encryptedVin = encryptionUtils.encrypt(plainVin);
        vehicle.updateVin(encryptedVin);
        vehicleRepository.save(vehicle);
        log.info("[VehicleService] 차량 VIN 암호화 저장 완료 - vehicleId: {}", vehicleId);
    }

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

        // 9종 전체 소모품 초기화 (입력된 항목은 그대로, 미입력은 추론)
        registerConsumables(savedVehicle, request.getConsumables());

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

        if (request.getCarNumber() != null && !request.getCarNumber().isBlank()) {
            vehicle.updateCarNumber(request.getCarNumber());
        }

        if (request.getVin() != null && !request.getVin().isBlank() && !request.getVin().equals(vehicle.getVin())) {
            if (vehicleRepository.existsByVinAndDeletedAtIsNull(request.getVin())) {
                throw new BaseException(ErrorCode.DUPLICATE_VIN);
            }
            vehicle.updateVin(request.getVin());
        }

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

    /**
     * 소모품 다중 등록 및 추론 로직 (9종 전체 생성 보장)
     */
    @Transactional
    public void registerConsumables(Vehicle vehicle, List<VehicleDto.ConsumableRegistrationRequest> requests) {
        log.info("[VehicleService] 소모품 일괄 등록 시작 - Vehicle: {}", vehicle.getVehicleId());

        List<kr.co.himedia.entity.ConsumableItem> allMasterItems = consumableItemRepository.findAll();
        // [MOD] 코드 매칭을 대소문자 구분 없이 강건하게 처리
        Map<String, VehicleDto.ConsumableRegistrationRequest> requestMap = (requests == null) ? Map.of()
                : requests.stream()
                        .filter(r -> r.getCode() != null)
                        .collect(Collectors.toMap(
                                r -> r.getCode().trim().toUpperCase(),
                                r -> r,
                                (existing, replacement) -> existing // 중복 시 첫 번째 것 사용
                        ));

        log.info("[VehicleService] 수신된 소모품 요청 코드: {}", requestMap.keySet());

        double currentMileage = vehicle.getTotalMileage() != null ? vehicle.getTotalMileage() : 0.0;
        LocalDateTime now = LocalDateTime.now();
        double dailyMileage = 41.0; // 일평균 약 41km (연 15,000km 기준)

        for (ConsumableItem item : allMasterItems) {
            String itemCode = item.getCode().trim().toUpperCase();
            VehicleDto.ConsumableRegistrationRequest req = requestMap.get(itemCode);
            VehicleConsumable vc = new VehicleConsumable();
            vc.setVehicle(vehicle);
            vc.setConsumableItem(item);
            vc.setWearFactor(1.0); // 초기 가중치 1.0

            LocalDateTime lastAt;
            Double lastMileage;

            if (req != null) {
                // 사용자가 일부 정보를 입력한 경우
                lastAt = req.getLastReplacedAt();
                lastMileage = req.getLastReplacedMileage();

                if (lastAt == null && lastMileage != null) {
                    // 거리만 있고 날짜가 없는 경우 -> 주행거리 차이로 날짜 역산
                    long daysDiff = Math.abs(Math.round((currentMileage - lastMileage) / dailyMileage));
                    lastAt = now.minusDays(daysDiff);
                } else if (lastAt != null && lastMileage == null) {
                    // 날짜만 있고 거리가 없는 경우 -> 경과일로 거리 역산
                    long daysDiff = Math.abs(ChronoUnit.DAYS.between(lastAt, now));
                    lastMileage = Math.max(0, currentMileage - (daysDiff * dailyMileage));
                } else if (lastAt == null && lastMileage == null) {
                    // 항목만 추가하고 빈값인 경우 -> 수식 추론
                    lastMileage = currentMileage - (currentMileage % item.getDefaultIntervalMileage());
                    long daysDiff = Math.abs(Math.round((currentMileage - lastMileage) / dailyMileage));
                    lastAt = now.minusDays(daysDiff);
                }
            } else {
                // 사용자가 아예 입력하지 않은 항목 -> 수식 기반 초기화
                lastMileage = currentMileage - (currentMileage % item.getDefaultIntervalMileage());
                long daysDiff = Math.abs(Math.round((currentMileage - lastMileage) / dailyMileage));
                lastAt = now.minusDays(daysDiff);
            }

            vc.setLastReplacedAt(lastAt);
            vc.setLastReplacedMileage(lastMileage);
            vc.setIsInferred(req == null); // 사용자가 입력하지 않은 항목만 추론(inferred)으로 표시

            // 잔존 수명 최초 계산
            double distanceDriven = currentMileage - lastMileage;
            double lifePercentage = 100.0 - (distanceDriven / item.getDefaultIntervalMileage() * 100.0);
            vc.updateRemainingLife(lifePercentage);

            vehicleConsumableRepository.save(vc);
            log.info("[VehicleService] 소모품 생성 완료: {} (LastMileage: {}, Remaining: {}%)",
                    item.getCode(), lastMileage, String.format("%.1f", vc.getRemainingLife()));
        }
    }
}
