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
        }

        // 2. Process Trip Summary
        updateTripSummary(obdLogDtos);
    }

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

    @Transactional
    public void disconnectVehicle(UUID vehicleId) {
        Optional<TripSummary> activeTripOpt = tripSummaryRepository.findActiveTripByVehicleId(vehicleId);
        if (activeTripOpt.isPresent()) {
            TripSummary trip = activeTripOpt.get();
            // If endTime is null, it means it's still active.
            // We mark it as ended at the current time (or last received time if we want to
            // be precise)
            if (trip.getEndTime() == null) {
                trip.setEndTime(LocalDateTime.now());
                tripSummaryRepository.save(trip);
                log.info("Vehicle {} disconnected. Trip {} ended.", vehicleId, trip.getTripId());
            }
        }
    }

    private void updateTripSummary(List<ObdLogDto> dtos) {
        if (dtos.isEmpty())
            return;

        UUID vehicleId = dtos.get(0).getVehicleId();
        // Sort by timestamp just in case
        dtos.sort((a, b) -> a.getTimestamp().compareTo(b.getTimestamp()));

        Optional<TripSummary> activeTripOpt = tripSummaryRepository.findActiveTripByVehicleId(vehicleId);

        TripSummary trip;
        if (activeTripOpt.isPresent()) {
            trip = activeTripOpt.get();
            // Check for timeout (e.g., if more than 5 minutes passed since last log)
            if (trip.getEndTime() != null &&
                    dtos.get(0).getTimestamp().isAfter(trip.getEndTime().plusMinutes(5))) {
                // Finalize old trip and start new one
                trip.setEndTime(trip.getEndTime()); // Mark as truly ended (optional logic here)
                tripSummaryRepository.save(trip);
                trip = createNewTrip(dtos.get(0));
            }
        } else {
            trip = createNewTrip(dtos.get(0));
        }

        // Update metrics
        double currentDistance = trip.getDistance() != null ? trip.getDistance() : 0.0;
        double maxSpeed = trip.getTopSpeed() != null ? trip.getTopSpeed() : 0.0;
        double sumSpeed = 0.0;
        int count = dtos.size();

        for (ObdLogDto dto : dtos) {
            if (dto.getSpeed() != null) {
                if (dto.getSpeed() > maxSpeed) {
                    maxSpeed = dto.getSpeed();
                }
                sumSpeed += dto.getSpeed();
                // Simple distance calculation: speed(km/h) * 1s / 3600 = km
                currentDistance += (dto.getSpeed() / 3600.0);
            }
        }

        // Aggregate average speed
        // Note: This is an approximation. A more accurate way would be total distance /
        // total time.
        double prevAvg = trip.getAverageSpeed() != null ? trip.getAverageSpeed() : 0.0;
        // Simplified moving average (not perfect but okay for batch updates)
        // Ideally we should track total_data_points in the entity for a perfect
        // average.
        // For MVP, let's keep it simple.
        trip.setAverageSpeed((prevAvg + (sumSpeed / count)) / 2.0);
        trip.setTopSpeed(maxSpeed);
        trip.setDistance(currentDistance);
        trip.setEndTime(dtos.get(dtos.size() - 1).getTimestamp());

        tripSummaryRepository.save(trip);
    }

    private TripSummary createNewTrip(ObdLogDto firstDto) {
        return TripSummary.builder()
                .vehicleId(firstDto.getVehicleId())
                .startTime(firstDto.getTimestamp())
                .distance(0.0)
                .averageSpeed(0.0)
                .topSpeed(0.0)
                .fuelConsumed(0.0)
                .driveScore(100) // Start with perfect score
                .build();
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
