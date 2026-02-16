package kr.co.himedia.service;

import kr.co.himedia.common.constants.ConsumableConstants;
import kr.co.himedia.common.exception.BaseException;
import kr.co.himedia.common.exception.ErrorCode;
import kr.co.himedia.entity.ObdLog;
import kr.co.himedia.entity.TripSummary;
import kr.co.himedia.repository.ObdLogRepository;
import kr.co.himedia.repository.TripSummaryRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.stream.Collectors;

import kr.co.himedia.dto.trip.TripObdLogDto;

@Slf4j
@Service
@RequiredArgsConstructor
public class TripService {
    private final TripSummaryRepository tripSummaryRepository;
    private final ObdLogRepository obdLogRepository;
    private final AiDiagnosisService aiDiagnosisService;
    private final WearFactorService wearFactorService;
    private final kr.co.himedia.repository.VehicleRepository vehicleRepository;
    private final kr.co.himedia.service.NotificationService notificationService;
    private final kr.co.himedia.repository.UserRepository userRepository;

    // 최소 유효 주행 거리 (100m = 0.1km) - 이 미만의 주행은 분석 대상에서 제외
    private static final double MIN_TRIP_DISTANCE_KM = 0.1;

    // 차량별 주행 기록 목록 조회 (100m 이상 유효 주행만 노출)
    @Transactional(readOnly = true)
    public List<TripSummary> getTripsByVehicle(UUID vehicleId) {
        return tripSummaryRepository.findValidTripsByVehicleId(vehicleId, MIN_TRIP_DISTANCE_KM);
    }

    // 주행 기록 상세 조회
    @Transactional(readOnly = true)
    public TripSummary getTripDetail(UUID tripId) {
        return tripSummaryRepository.findByTripId(tripId)
                .orElseThrow(() -> new BaseException(ErrorCode.TRIP_NOT_FOUND));
    }

    /**
     * 주행 구간 OBD 로그 조회 (CSV 내보내기용)
     */
    @Transactional(readOnly = true)
    public List<TripObdLogDto> getTripObdLogs(UUID tripId) {
        TripSummary trip = tripSummaryRepository.findByTripId(tripId)
                .orElseThrow(() -> new BaseException(ErrorCode.TRIP_NOT_FOUND));

        if (trip.getEndTime() == null) {
            return List.of();
        }

        var startOffset = trip.getStartTime().atZone(java.time.ZoneId.systemDefault()).toOffsetDateTime();
        var endOffset = trip.getEndTime().atZone(java.time.ZoneId.systemDefault()).toOffsetDateTime();

        List<ObdLog> logs = obdLogRepository.findByVehicleIdAndTimeBetweenOrderByTimeAsc(
                trip.getVehicleId(), startOffset, endOffset);

        return logs.stream()
                .map(log -> TripObdLogDto.builder()
                        .timestamp(log.getTime() != null ? log.getTime().toString() : "")
                        .rpm(log.getRpm())
                        .speed(log.getSpeed())
                        .voltage(log.getVoltage())
                        .coolantTemp(log.getCoolantTemp())
                        .engineLoad(log.getEngineLoad())
                        .fuelTrimShort(log.getFuelTrimShort())
                        .fuelTrimLong(log.getFuelTrimLong())
                        .throttlePos(log.getThrottlePos())
                        .map(log.getMap())
                        .maf(log.getMaf())
                        .intakeTemp(log.getIntakeTemp())
                        .engineRuntime(log.getEngineRuntime())
                        .build())
                .collect(Collectors.toList());
    }

    // 주행 시작 (Trip ID 발급 및 초기화)
    @Transactional
    public TripSummary startTrip(UUID vehicleId) {
        tripSummaryRepository.findActiveTripByVehicleId(vehicleId)
                .ifPresent(trip -> {
                    trip.setEndTime(LocalDateTime.now());
                    tripSummaryRepository.save(trip);
                });

        TripSummary newTrip = TripSummary.builder()
                .vehicleId(vehicleId)
                .startTime(LocalDateTime.now())
                .build();

        TripSummary saved = tripSummaryRepository.save(newTrip);

        vehicleRepository.findById(vehicleId).ifPresent(vehicle -> {
            userRepository.findById(vehicle.getUserId()).ifPresent(user -> {
                java.util.Map<String, String> data = new java.util.HashMap<>();
                data.put("type", "TRIP_START");
                data.put("tripId", saved.getTripId().toString());
                notificationService.sendNotification(user, "주행 시작", "차봄OBD 데이터 수집을 시작합니다.",
                        kr.co.himedia.entity.Notification.NotificationType.TRIP_START, data);
                log.info("[TripStart] FCM notification sent for trip: {}", saved.getTripId());
            });
        });

        return saved;
    }

    /**
     * 주행 종료 및 통계 계산
     * 10m 이상 주행 시에만 AI 진단 및 소모품 수명 계산을 수행합니다.
     */
    @Transactional
    public TripSummary endTrip(UUID tripId) {
        TripSummary trip = tripSummaryRepository.findByTripId(tripId)
                .orElseThrow(() -> new IllegalArgumentException("Trip not found: " + tripId));

        if (trip.getEndTime() != null) {
            return trip; // Already ended
        }

        LocalDateTime endTime = LocalDateTime.now();
        trip.setEndTime(endTime);

        var startOffset = trip.getStartTime().atZone(java.time.ZoneId.systemDefault()).toOffsetDateTime();
        var endOffset = endTime.atZone(java.time.ZoneId.systemDefault()).toOffsetDateTime();

        log.info("[TripEnd] Query logs between {} ~ {} (vehicleId={})", startOffset, endOffset, trip.getVehicleId());

        List<ObdLog> tripLogs = obdLogRepository.findByVehicleIdAndTimeBetweenOrderByTimeAsc(
                trip.getVehicleId(),
                startOffset,
                endOffset);

        log.info("[TripEnd] Found {} logs for trip {}", tripLogs.size(), tripId);

        // 2. 전체 로그 기반 통계 재계산 (수학적 결함 해결)
        if (!tripLogs.isEmpty()) {
            double sumSpeed = 0.0;
            double maxSpeed = 0.0;
            double distance = 0.0;
            int driveScore = 100;

            // 추가 통계 변수 초기화
            int highRpmCount = 0;
            int totalCount = 0;
            double sumRpm = 0.0;
            double sumEngineLoad = 0.0;
            double sumMaf = 0.0;
            double sumThrottlePos = 0.0;
            double sumFuelTrim = 0.0;

            double maxCoolantTemp = -100.0;
            double maxEngineLoad = 0.0;
            double minBatteryVoltage = 0.0; // 초기값 0, 루프에서 갱신

            int overheatDurationSec = 0;
            int idleTime = 0;
            int hardAccelCount = 0;
            int hardBrakeCount = 0;
            double prevSpeed = -1.0; // -1 for initial state

            for (ObdLog log : tripLogs) {
                totalCount++;

                if (log.getRpm() != null && log.getRpm() > ConsumableConstants.HIGH_RPM_THRESHOLD) {
                    highRpmCount++;
                }

                double speed = log.getSpeed() != null ? log.getSpeed() : 0.0;
                double rpm = log.getRpm() != null ? log.getRpm() : 0.0;
                double coolant = log.getCoolantTemp() != null ? log.getCoolantTemp() : 0.0;
                double voltage = log.getVoltage() != null ? log.getVoltage() : 0.0;
                double load = log.getEngineLoad() != null ? log.getEngineLoad() : 0.0;
                double maf = log.getMaf() != null ? log.getMaf() : 0.0;
                double throttle = log.getThrottlePos() != null ? log.getThrottlePos() : 0.0;
                double fuelTrim = log.getFuelTrimShort() != null ? log.getFuelTrimShort() : 0.0;

                // 최고 속도 갱신
                if (speed > maxSpeed)
                    maxSpeed = speed;

                // 속도 합계 (평균 속도 계산용)
                sumSpeed += speed;

                // 새로운 통계 데이터 집계
                sumRpm += rpm;
                sumEngineLoad += load;
                sumMaf += maf;
                sumThrottlePos += throttle;
                sumFuelTrim += fuelTrim;

                if (coolant > maxCoolantTemp)
                    maxCoolantTemp = coolant;
                if (load > maxEngineLoad)
                    maxEngineLoad = load;
                if (voltage > 0 && (minBatteryVoltage == 0 || voltage < minBatteryVoltage))
                    minBatteryVoltage = voltage; // 0이 아닌 최소값

                // 과열 지속 시간 (95도 이상)
                if (coolant >= ConsumableConstants.COOLANT_OVERHEAT_THRESHOLD)
                    overheatDurationSec++;

                // 공회전 시간 (속도 0, RPM > 0)
                if (speed < 1.0 && rpm > 0) {
                    idleTime++;
                    if (idleTime % 60 == 0) {
                        driveScore = Math.max(0, driveScore - 1); // 60초 누적 시 -1점
                    }
                }

                // 급가속/급감속 (이전 데이터와 비교)
                if (prevSpeed != -1.0) {
                    double speedDelta = speed - prevSpeed; // km/h per sec (assuming 1hz)
                    if (speedDelta >= ConsumableConstants.HARD_ACCEL_THRESHOLD) {
                        hardAccelCount++; // 초당 10km/h 증가
                        driveScore = Math.max(0, driveScore - 5); // 급가속 -5점
                    }
                    if (speedDelta <= -ConsumableConstants.HARD_BRAKE_THRESHOLD) {
                        hardBrakeCount++; // 초당 10km/h 감소
                        driveScore = Math.max(0, driveScore - 5); // 급감속 -5점
                    }
                }
                prevSpeed = speed;

                // 주행 거리 누적 (1초 주기 가정: speed km/h * 1s / 3600)
                distance += (speed / 3600.0);

                // 안전 점수 감점 로직 (초기 100점)
                // 과속 (140km/h 초과) 시 감점
                if (speed > 140)
                    driveScore = Math.max(0, driveScore - 1);
                // 고속 RPM (5000rpm 초과) 시 감점
                if (rpm > 5000)
                    driveScore = Math.max(0, driveScore - 1);
                // 풀 악셀 (Throttle > 90%) 시 감점
                if (throttle > 90)
                    driveScore = Math.max(0, driveScore - 1);
                // 엔진 과부하 (Engine Load > 90%) 시 감점
                if (load > 90)
                    driveScore = Math.max(0, driveScore - 1);
            }

            trip.setAverageSpeed(sumSpeed / tripLogs.size());
            trip.setTopSpeed(maxSpeed);
            trip.setDistance(distance);
            trip.setDriveScore(driveScore);

            // 추가 통계 설정
            int count = tripLogs.size();
            trip.setAvgRpm(sumRpm / count);
            trip.setAvgEngineLoad(sumEngineLoad / count);
            trip.setAvgMaf(sumMaf / count);
            trip.setAvgThrottlePos(sumThrottlePos / count);
            trip.setAvgFuelTrim(sumFuelTrim / count);

            // Calculate highRpmRatio
            Double highRpmRatio = null;
            if (totalCount > 0) {
                highRpmRatio = (double) highRpmCount / totalCount;
            }
            trip.setHighRpmRatio(highRpmRatio);

            trip.setMaxCoolantTemp(maxCoolantTemp);
            trip.setMaxEngineLoad(maxEngineLoad);
            trip.setMinBatteryVoltage(minBatteryVoltage);

            trip.setOverheatDurationSec(overheatDurationSec);
            trip.setIdleTime(idleTime);
            trip.setHardAccelCount(hardAccelCount);
            trip.setHardBrakeCount(hardBrakeCount);

            log.info(
                    "[TripEnd] Final statistics calculated for trip {}: AvgSpeed={}, MaxSpeed={}, Distance={}, Score={}",
                    tripId, trip.getAverageSpeed(), maxSpeed, distance, driveScore);

            // 최소 거리 이상인 경우에만 무거운 비즈니스 로직 실행
            if (distance >= MIN_TRIP_DISTANCE_KM) {
                vehicleRepository.findById(trip.getVehicleId()).ifPresent(vehicle -> {
                    double currentTotal = vehicle.getTotalMileage() != null ? vehicle.getTotalMileage() : 0.0;
                    double newTotal = currentTotal + trip.getDistance();
                    vehicle.updateTotalMileage(newTotal);
                    vehicleRepository.save(vehicle);
                    log.info("[TripEnd] Updated Vehicle Total Mileage: {} -> {}", currentTotal, newTotal);

                    try {
                        // [Migration] 규칙 기반 로컬 마모 계수 계산 (AI 서버 호출 제거)
                        wearFactorService.calculateWearFactorsLocal(trip);
                        log.info("Completed local wear factor calculation for vehicle: {}",
                                trip.getVehicleId());
                    } catch (Exception e) {
                        log.error("Wear factor trigger failed", e);
                    }
                });

                try {
                    Map<String, Object> lstmInput = Map.of(
                            "tripId", trip.getTripId().toString(),
                            "logCount", tripLogs.size(),
                            "logs", tripLogs.stream().limit(500).map(log -> Map.of(
                                    "time", log.getTime() != null ? log.getTime().toString() : "",
                                    "rpm", log.getRpm() != null ? log.getRpm() : 0.0,
                                    "speed", log.getSpeed() != null ? log.getSpeed() : 0.0,
                                    "coolant", log.getCoolantTemp() != null ? log.getCoolantTemp() : 0.0,
                                    "load", log.getEngineLoad() != null ? log.getEngineLoad() : 0.0,
                                    "voltage", log.getVoltage() != null ? log.getVoltage() : 0.0))
                                    .collect(Collectors.toList()));

                    kr.co.himedia.dto.ai.UnifiedDiagnosisRequestDto requestDto = kr.co.himedia.dto.ai.UnifiedDiagnosisRequestDto
                            .builder()
                            .vehicleId(trip.getVehicleId())
                            .tripId(trip.getTripId())
                            .lstmAnalysis(lstmInput)
                            .build();

                    aiDiagnosisService.requestUnifiedDiagnosis(requestDto, null, null,
                            kr.co.himedia.entity.DiagSession.DiagTriggerType.AUTO);
                    log.info("Successfully triggered auto diagnosis for trip: {}", tripId);
                } catch (Exception e) {
                    log.error("Auto diagnosis trigger failed for trip: {}", tripId, e);
                }
            } else {
                log.info("[TripEnd] Trip distance ({} km) is below threshold ({} km). Skipping heavy logic.",
                        distance, MIN_TRIP_DISTANCE_KM);
            }
        } else {
            // 로그가 아예 없는 경우 0.0으로 명시적 초기화
            trip.setDistance(0.0);
            trip.setAverageSpeed(0.0);
            trip.setTopSpeed(0.0);
            trip.setDriveScore(100); // 운전 점수는 기본 100점 (운행 안했으니 감점 없음)

            trip.setAvgRpm(0.0);
            trip.setAvgEngineLoad(0.0);
            trip.setAvgMaf(0.0);
            trip.setAvgThrottlePos(0.0);
            trip.setAvgFuelTrim(0.0);
            trip.setMaxCoolantTemp(0.0);
            trip.setMaxEngineLoad(0.0);
            trip.setMinBatteryVoltage(0.0);
            trip.setOverheatDurationSec(0);
            trip.setIdleTime(0);
            trip.setHardAccelCount(0);
            trip.setHardBrakeCount(0);
            log.info("[TripEnd] No logs found for trip {}. Setting stats to default (0).", tripId);
        }

        TripSummary saved = tripSummaryRepository.save(trip);

        vehicleRepository.findById(trip.getVehicleId()).ifPresent(vehicle -> {
            userRepository.findById(vehicle.getUserId()).ifPresent(user -> {
                java.util.Map<String, String> data = new java.util.HashMap<>();
                data.put("type", "TRIP_END");
                data.put("tripId", saved.getTripId().toString());
                data.put("distance", String.valueOf(saved.getDistance() != null ? saved.getDistance() : 0.0));
                notificationService.sendNotification(user, "주행 종료", "차봄OBD 데이터 수집이 완료되었습니다. AI 진단이 자동으로 진행됩니다.",
                        kr.co.himedia.entity.Notification.NotificationType.TRIP_END, data);
                log.info("[TripEnd] FCM notification sent for trip: {}", saved.getTripId());
            });
        });

        return saved;
    }

    /**
     * 주행 차량 재할당: trip_summaries 및 해당 구간 obd_logs의 vehicles_id 변경 후 통계 재집계.
     * 소모품 반영은 하지 않음. 진단(RAG+GPT) 재실행은 별도 트리거.
     */
    @Transactional
    public TripSummary changeTripVehicle(UUID userId, UUID tripId, UUID newVehicleId) {
        TripSummary trip = tripSummaryRepository.findByTripId(tripId)
                .orElseThrow(() -> new BaseException(ErrorCode.TRIP_NOT_FOUND));

        kr.co.himedia.entity.Vehicle oldVehicle = vehicleRepository
                .findByVehicleIdAndDeletedAtIsNull(trip.getVehicleId())
                .orElseThrow(() -> new BaseException(ErrorCode.VEHICLE_NOT_FOUND));
        if (!oldVehicle.getUserId().equals(userId))
            throw new BaseException(ErrorCode.VEHICLE_NOT_FOUND);

        kr.co.himedia.entity.Vehicle newVehicle = vehicleRepository.findByVehicleIdAndDeletedAtIsNull(newVehicleId)
                .orElseThrow(() -> new BaseException(ErrorCode.VEHICLE_NOT_FOUND));
        if (!newVehicle.getUserId().equals(userId))
            throw new BaseException(ErrorCode.VEHICLE_NOT_FOUND);

        UUID oldVehicleId = trip.getVehicleId();
        if (oldVehicleId.equals(newVehicleId)) {
            return trip;
        }

        java.time.OffsetDateTime startOffset = trip.getStartTime().atZone(java.time.ZoneId.systemDefault())
                .toOffsetDateTime();
        java.time.OffsetDateTime endOffset = (trip.getEndTime() != null)
                ? trip.getEndTime().atZone(java.time.ZoneId.systemDefault()).toOffsetDateTime()
                : java.time.OffsetDateTime.now();

        List<ObdLog> oldLogs = obdLogRepository.findByVehicleIdAndTimeBetweenOrderByTimeAsc(oldVehicleId, startOffset,
                endOffset);
        List<ObdLog> newLogs = oldLogs.stream()
                .map(log -> ObdLog.builder()
                        .time(log.getTime())
                        .vehicleId(newVehicleId)
                        .rpm(log.getRpm())
                        .speed(log.getSpeed())
                        .voltage(log.getVoltage())
                        .coolantTemp(log.getCoolantTemp())
                        .engineLoad(log.getEngineLoad())
                        .fuelTrimShort(log.getFuelTrimShort())
                        .fuelTrimLong(log.getFuelTrimLong())
                        .intakeTemp(log.getIntakeTemp())
                        .map(log.getMap())
                        .maf(log.getMaf())
                        .throttlePos(log.getThrottlePos())
                        .engineRuntime(log.getEngineRuntime())
                        .jsonExtra(log.getJsonExtra())
                        .build())
                .collect(Collectors.toList());

        if (!newLogs.isEmpty()) {
            obdLogRepository.saveAll(newLogs);
        }
        obdLogRepository.deleteByVehicleIdAndTimeBetween(oldVehicleId, startOffset, endOffset);

        TripSummary newTrip = TripSummary.builder()
                .startTime(trip.getStartTime())
                .vehicleId(newVehicleId)
                .tripId(trip.getTripId())
                .endTime(trip.getEndTime())
                .fuelConsumed(trip.getFuelConsumed() != null ? trip.getFuelConsumed() : 0.0)
                .build();

        if (!newLogs.isEmpty()) {
            double sumSpeed = 0.0, maxSpeed = 0.0, distance = 0.0;
            int driveScore = 100;
            double sumRpm = 0.0, sumEngineLoad = 0.0, sumMaf = 0.0, sumThrottlePos = 0.0, sumFuelTrim = 0.0;
            double maxCoolantTemp = -100.0, maxEngineLoad = 0.0, minBatteryVoltage = 0.0;
            int overheatDurationSec = 0, idleTime = 0, hardAccelCount = 0, hardBrakeCount = 0;
            double prevSpeed = -1.0;

            for (ObdLog log : newLogs) {
                double speed = log.getSpeed() != null ? log.getSpeed() : 0.0;
                double rpm = log.getRpm() != null ? log.getRpm() : 0.0;
                double coolant = log.getCoolantTemp() != null ? log.getCoolantTemp() : 0.0;
                double voltage = log.getVoltage() != null ? log.getVoltage() : 0.0;
                double load = log.getEngineLoad() != null ? log.getEngineLoad() : 0.0;
                double maf = log.getMaf() != null ? log.getMaf() : 0.0;
                double throttle = log.getThrottlePos() != null ? log.getThrottlePos() : 0.0;
                double fuelTrim = log.getFuelTrimShort() != null ? log.getFuelTrimShort() : 0.0;

                if (speed > maxSpeed)
                    maxSpeed = speed;
                sumSpeed += speed;
                sumRpm += rpm;
                sumEngineLoad += load;
                sumMaf += maf;
                sumThrottlePos += throttle;
                sumFuelTrim += fuelTrim;
                if (coolant > maxCoolantTemp)
                    maxCoolantTemp = coolant;
                if (load > maxEngineLoad)
                    maxEngineLoad = load;
                if (voltage > 0 && (minBatteryVoltage == 0 || voltage < minBatteryVoltage))
                    minBatteryVoltage = voltage;
                if (coolant >= ConsumableConstants.COOLANT_OVERHEAT_THRESHOLD)
                    overheatDurationSec++;
                if (speed < 1.0 && rpm > 0) {
                    idleTime++;
                    if (idleTime % 60 == 0)
                        driveScore = Math.max(0, driveScore - 1);
                }
                if (prevSpeed != -1.0) {
                    double speedDelta = speed - prevSpeed;
                    if (speedDelta >= ConsumableConstants.HARD_ACCEL_THRESHOLD) {
                        hardAccelCount++;
                        driveScore = Math.max(0, driveScore - 5);
                    }
                    if (speedDelta <= -ConsumableConstants.HARD_BRAKE_THRESHOLD) {
                        hardBrakeCount++;
                        driveScore = Math.max(0, driveScore - 5);
                    }
                }
                prevSpeed = speed;
                distance += (speed / 3600.0);
                if (speed > 140)
                    driveScore = Math.max(0, driveScore - 1);
                if (rpm > 5000)
                    driveScore = Math.max(0, driveScore - 1);
                if (throttle > 90)
                    driveScore = Math.max(0, driveScore - 1);
                if (load > 90)
                    driveScore = Math.max(0, driveScore - 1);
            }

            int count = newLogs.size();
            newTrip.setAverageSpeed(sumSpeed / count);
            newTrip.setTopSpeed(maxSpeed);
            newTrip.setDistance(distance);
            newTrip.setDriveScore(driveScore);
            newTrip.setAvgRpm(sumRpm / count);
            newTrip.setAvgEngineLoad(sumEngineLoad / count);
            newTrip.setAvgMaf(sumMaf / count);
            newTrip.setAvgThrottlePos(sumThrottlePos / count);
            newTrip.setAvgFuelTrim(sumFuelTrim / count);
            newTrip.setMaxCoolantTemp(maxCoolantTemp);
            newTrip.setMaxEngineLoad(maxEngineLoad);
            newTrip.setMinBatteryVoltage(minBatteryVoltage);
            newTrip.setOverheatDurationSec(overheatDurationSec);
            newTrip.setIdleTime(idleTime);
            newTrip.setHardAccelCount(hardAccelCount);
            newTrip.setHardBrakeCount(hardBrakeCount);
        } else {
            newTrip.setDistance(0.0);
            newTrip.setAverageSpeed(0.0);
            newTrip.setTopSpeed(0.0);
            newTrip.setDriveScore(100);
            newTrip.setAvgRpm(0.0);
            newTrip.setAvgEngineLoad(0.0);
            newTrip.setAvgMaf(0.0);
            newTrip.setAvgThrottlePos(0.0);
            newTrip.setAvgFuelTrim(0.0);
            newTrip.setMaxCoolantTemp(0.0);
            newTrip.setMaxEngineLoad(0.0);
            newTrip.setMinBatteryVoltage(0.0);
            newTrip.setOverheatDurationSec(0);
            newTrip.setIdleTime(0);
            newTrip.setHardAccelCount(0);
            newTrip.setHardBrakeCount(0);
        }

        tripSummaryRepository.delete(trip);
        return tripSummaryRepository.save(newTrip);
    }

}
