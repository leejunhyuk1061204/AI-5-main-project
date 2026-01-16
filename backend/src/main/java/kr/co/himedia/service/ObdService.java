package kr.co.himedia.service;

import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import java.util.stream.Collectors;
import kr.co.himedia.dto.obd.ConnectionStatusDto;
import kr.co.himedia.dto.obd.ObdLogDto;
import kr.co.himedia.entity.ObdLog;
import kr.co.himedia.entity.TripSummary;
import kr.co.himedia.repository.ObdLogRepository;
import kr.co.himedia.repository.TripSummaryRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
@Slf4j
public class ObdService {

    private final ObdLogRepository obdLogRepository;
    private final TripSummaryRepository tripSummaryRepository;
    private final TripService tripService;

    // OBD 로그 대량 저장 및 주행 요약 갱신
    @Transactional
    public void saveObdLogs(List<ObdLogDto> obdLogDtos) {
        if (obdLogDtos == null || obdLogDtos.isEmpty()) {
            return;
        }

        // 1. Save raw logs
        List<ObdLog> obdLogs = obdLogDtos.stream()
                .map(this::toEntity)
                .collect(Collectors.toList());

        if (!obdLogs.isEmpty()) {
            obdLogRepository.saveAll(obdLogs);
            // 실시간 주행 요약 갱신은 부하 감소 및 정확도를 위해 종료 시 단회 처리로 변경됨
        }
    }

    // 차량 연결 상태 및 주행 여부 조회
    @Transactional(readOnly = true)
    public ConnectionStatusDto getConnectionStatus(UUID vehicleId) {
        Optional<TripSummary> lastTrip = tripSummaryRepository.findLatestTripByVehicleId(vehicleId);

        if (lastTrip.isEmpty()) {
            return ConnectionStatusDto.builder()
                    .connected(false)
                    .statusMessage("NEVER_CONNECTED")
                    .build();
        }

        TripSummary trip = lastTrip.get();
        LocalDateTime lastTime = trip.getEndTime() != null ? trip.getEndTime() : trip.getStartTime();

        // If last data was within 5 minutes, consider it "DRIVING"
        boolean isDriving = lastTime.isAfter(LocalDateTime.now().minusMinutes(5));

        return ConnectionStatusDto.builder()
                .connected(isDriving)
                .lastDataTime(lastTime)
                .statusMessage(isDriving ? "DRIVING" : "PARKED")
                .build();
    }

    // 차량 연결 해제 및 주행 종료 처리
    @Transactional
    public void disconnectVehicle(UUID vehicleId) {
        tripSummaryRepository.findActiveTripByVehicleId(vehicleId)
                .ifPresent(trip -> tripService.endTrip(trip.getTripId()));
    }

    private ObdLog toEntity(ObdLogDto dto) {
        return ObdLog.builder()
                .time(dto.getTimestamp().atOffset(ZoneOffset.UTC)) // Assuming UTC for now
                .vehicleId(dto.getVehicleId())
                .rpm(dto.getRpm())
                .speed(dto.getSpeed())
                .voltage(dto.getVoltage())
                .coolantTemp(dto.getCoolantTemp())
                .engineLoad(dto.getEngineLoad())
                .fuelTrimShort(dto.getFuelTrimShort())
                .fuelTrimLong(dto.getFuelTrimLong())
                .build();
    }
}
