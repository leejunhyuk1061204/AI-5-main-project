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

    // 주행 종료 처리
    @Transactional
    public TripSummary endTrip(UUID tripId) {
        TripSummary trip = tripSummaryRepository.findByTripId(tripId)
                .orElseThrow(() -> new IllegalArgumentException("Trip not found: " + tripId));

        if (trip.getEndTime() != null) {
            return trip; // Already ended
        }

        trip.setEndTime(LocalDateTime.now());
        TripSummary savedTrip = tripSummaryRepository.save(trip);

        // [Trigger 1] 운행 종료 시 자동 진단 비동기 호출
        try {
            // 해당 Trip 동안 수집된 OBD 데이터 조회
            List<ObdLog> tripLogs = obdLogRepository.findByVehicleIdAndTimeBetweenOrderByTimeAsc(
                    trip.getVehicleId(),
                    trip.getStartTime().atOffset(ZoneOffset.UTC),
                    savedTrip.getEndTime().atOffset(ZoneOffset.UTC));

            // LSTM 분석용 데이터 형식으로 변환 (간소화)
            Map<String, Object> lstmInput = Map.of(
                    "tripId", trip.getTripId().toString(),
                    "logCount", tripLogs.size(),
                    "logs", tripLogs.stream().map(log -> Map.of(
                            "time", log.getTime().toString(),
                            "rpm", log.getRpm(),
                            "speed", log.getSpeed(),
                            "coolantTemp", log.getCoolantTemp() != null ? log.getCoolantTemp() : 0.0,
                            "engineLoad", log.getEngineLoad() != null ? log.getEngineLoad() : 0.0))
                            .collect(Collectors.toList()));

            kr.co.himedia.dto.ai.UnifiedDiagnosisRequestDto requestDto = kr.co.himedia.dto.ai.UnifiedDiagnosisRequestDto
                    .builder()
                    .vehicleId(trip.getVehicleId())
                    .lstmAnalysis(lstmInput)
                    .build();

            aiDiagnosisService.requestUnifiedDiagnosisAsync(requestDto);
            log.info("Successfully triggered auto diagnosis for trip: {}", tripId);

            // [Trigger 2] 운행 종료 시 마모율 계산
            wearFactorService.calculateAndSaveWearFactors(trip.getVehicleId());
            log.info("Successfully calculated wear factors for vehicle: {}", trip.getVehicleId());
        } catch (Exception e) {
            log.error("Auto diagnosis trigger failed for trip: {}", tripId, e);
            throw new RuntimeException("자동 진단 트리거 실패: " + tripId, e);
        }

        return savedTrip;
    }

    // 수집된 로그 기반 주행 요약(거리, 점수 등) 갱신
    @Transactional
    public void updateTripFromLogs(UUID vehicleId, List<kr.co.himedia.dto.obd.ObdLogDto> logs) {
        if (logs.isEmpty())
            return;

        // Sort logs by timestamp
        logs.sort((a, b) -> a.getTimestamp().compareTo(b.getTimestamp()));

        TripSummary trip = tripSummaryRepository.findActiveTripByVehicleId(vehicleId)
                .orElseGet(() -> {
                    // Implicit start if no active trip
                    return startTrip(vehicleId);
                });

        // Update metrics
        double currentDistance = trip.getDistance() != null ? trip.getDistance() : 0.0;
        double maxSpeed = trip.getTopSpeed() != null ? trip.getTopSpeed() : 0.0;
        double sumSpeed = 0.0;
        int validCount = 0;
        int currentScore = trip.getDriveScore() != null ? trip.getDriveScore() : 100;

        for (kr.co.himedia.dto.obd.ObdLogDto dto : logs) {
            // BE-TD-003: Anomaly Filtering
            if (dto.getSpeed() != null && (dto.getSpeed() < 0 || dto.getSpeed() > 300))
                continue;
            if (dto.getRpm() != null && (dto.getRpm() < 0 || dto.getRpm() > 10000))
                continue;

            if (dto.getSpeed() != null) {
                if (dto.getSpeed() > maxSpeed) {
                    maxSpeed = dto.getSpeed();
                }
                sumSpeed += dto.getSpeed();
                // Distance: speed(km/h) * 1s / 3600
                currentDistance += (dto.getSpeed() / 3600.0);
                validCount++;

                // BE-TD-004: Score Calculation (Simple)
                if (dto.getSpeed() > 140) {
                    currentScore = Math.max(0, currentScore - 1);
                }
            }
            if (dto.getRpm() != null && dto.getRpm() > 5000) {
                currentScore = Math.max(0, currentScore - 1);
            }
        }

        if (validCount > 0) {
            // Weighted average for AvgSpeed? Or just simple moving average of valid points
            // For MVP, simplistic:
            double batchAvg = sumSpeed / validCount;
            double prevAvg = trip.getAverageSpeed() != null ? trip.getAverageSpeed() : 0.0;
            // Assuming equal weight for now (can be improved with count field)
            trip.setAverageSpeed(prevAvg == 0 ? batchAvg : (prevAvg + batchAvg) / 2.0);
        }

        trip.setTopSpeed(maxSpeed);
        trip.setDistance(currentDistance);
        trip.setDriveScore(currentScore);

        // endTime은 실제 주행 종료(disconnect) 시에만 설정
        // 여기서 설정하면 활성 Trip으로 인식되지 않아 자동 진단이 트리거되지 않음

        tripSummaryRepository.save(trip);
    }
}
