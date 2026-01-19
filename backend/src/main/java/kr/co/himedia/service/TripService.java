package kr.co.himedia.service;

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
import java.time.ZoneOffset;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class TripService {
    private final TripSummaryRepository tripSummaryRepository;
    private final ObdLogRepository obdLogRepository;
    private final AiDiagnosisService aiDiagnosisService;
    private final WearFactorService wearFactorService;

    // 차량별 주행 기록 목록 조회
    @Transactional(readOnly = true)
    public List<TripSummary> getTripsByVehicle(UUID vehicleId) {
        return tripSummaryRepository.findByVehicleIdOrderByStartTimeDesc(vehicleId);
    }

    // 주행 기록 상세 조회
    @Transactional(readOnly = true)
    public TripSummary getTripDetail(UUID tripId) {
        return tripSummaryRepository.findByTripId(tripId)
                .orElseThrow(() -> new BaseException(ErrorCode.TRIP_NOT_FOUND));
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

        return tripSummaryRepository.save(newTrip);
    }

    @Transactional
    public TripSummary endTrip(UUID tripId) {
        TripSummary trip = tripSummaryRepository.findByTripId(tripId)
                .orElseThrow(() -> new IllegalArgumentException("Trip not found: " + tripId));

        if (trip.getEndTime() != null) {
            return trip; // Already ended
        }

        LocalDateTime endTime = LocalDateTime.now();
        trip.setEndTime(endTime);

        // 1. 해당 Trip 동안 수집된 전체 OBD 데이터 조회
        // 주의: LocalDateTime을 OffsetDateTime으로 변환 시 시스템 타임존 적용
        var startOffset = trip.getStartTime().atZone(java.time.ZoneId.systemDefault()).toOffsetDateTime();
        var endOffset = endTime.atZone(java.time.ZoneId.systemDefault()).toOffsetDateTime();

        log.info("[TripEnd] Query Range: {} ~ {} (vehicleId={})", startOffset, endOffset, trip.getVehicleId());

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

            for (ObdLog log : tripLogs) {
                double speed = log.getSpeed() != null ? log.getSpeed() : 0.0;
                double rpm = log.getRpm() != null ? log.getRpm() : 0.0;

                // 최고 속도
                if (speed > maxSpeed)
                    maxSpeed = speed;

                // 속도 합계 (평준화/평균용)
                sumSpeed += speed;

                // 주행 거리 (1초 주기 가정: speed km/h * 1s / 3600)
                distance += (speed / 3600.0);

                // 안전 점수 감점 로직 (정교화 가능)
                if (speed > 140)
                    driveScore = Math.max(0, driveScore - 1);
                if (rpm > 5000)
                    driveScore = Math.max(0, driveScore - 1);
            }

            trip.setAverageSpeed(sumSpeed / tripLogs.size());
            trip.setTopSpeed(maxSpeed);
            trip.setDistance(distance);
            trip.setDriveScore(driveScore);

            log.info(
                    "[TripEnd] Final statistics calculated for trip {}: AvgSpeed={}, MaxSpeed={}, Distance={}, Score={}",
                    tripId, trip.getAverageSpeed(), maxSpeed, distance, driveScore);
        }

        TripSummary savedTrip = tripSummaryRepository.save(trip);

        // [Trigger 1] 운행 종료 시 자동 진단 비동기 호출 (이미 조회한 tripLogs 재사용)
        try {
            // LSTM 분석용 데이터 형식으로 변환
            Map<String, Object> lstmInput = Map.of(
                    "tripId", trip.getTripId().toString(),
                    "logCount", tripLogs.size(),
                    "logs", tripLogs.stream().limit(500).map(log -> Map.of(
                            "time", log.getTime().toString(),
                            "rpm", log.getRpm(),
                            "speed", log.getSpeed(),
                            "coolantTemp", log.getCoolantTemp() != null ? log.getCoolantTemp() : 0.0,
                            "engineLoad", log.getEngineLoad() != null ? log.getEngineLoad() : 0.0))
                            .collect(Collectors.toList()));

            kr.co.himedia.dto.ai.UnifiedDiagnosisRequestDto requestDto = kr.co.himedia.dto.ai.UnifiedDiagnosisRequestDto
                    .builder()
                    .vehicleId(trip.getVehicleId())
                    .tripId(trip.getTripId())
                    .lstmAnalysis(lstmInput)
                    .build();

            aiDiagnosisService.requestUnifiedDiagnosisAsync(requestDto);
            log.info("Successfully triggered auto diagnosis for trip: {}", tripId);

            // [Trigger 2] 운행 종료 시 마모율 계산
            wearFactorService.calculateAndSaveWearFactors(trip.getVehicleId());
            log.info("Successfully calculated wear factors for vehicle: {}", trip.getVehicleId());
        } catch (Exception e) {
            log.error("Auto diagnosis trigger failed for trip: {}", tripId, e);
            // 진단 트리거 실패가 주행 종료 리턴을 막지 않도록 예외 전파 안함 (단, 로그는 남김)
        }

        return savedTrip;
    }

}
