package kr.co.himedia.service;

import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import java.util.stream.Collectors;
import kr.co.himedia.dto.obd.ObdBatchRequestDto;
import kr.co.himedia.dto.obd.ConnectionStatusDto;
import kr.co.himedia.dto.obd.ObdLogDto;
import kr.co.himedia.entity.ObdLog;
import kr.co.himedia.entity.TripSummary;
import kr.co.himedia.repository.ObdLogRepository;
import kr.co.himedia.repository.TripSummaryRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.concurrent.TimeUnit;

@Service
@RequiredArgsConstructor
@Slf4j
public class ObdService {

    private final ObdLogRepository obdLogRepository;
    private final TripSummaryRepository tripSummaryRepository;
    private final TripService tripService;
    private final StringRedisTemplate redisTemplate;

    // 8.5단계: Idempotency (중복 방지) 고도화
    @Transactional
    public void saveObdLogs(ObdBatchRequestDto batchRequest) {
        if (batchRequest == null || batchRequest.getLogs() == null || batchRequest.getLogs().isEmpty()) {
            return;
        }

        UUID vehicleId = batchRequest.getVehicleId();
        String batchId = batchRequest.getBatchId();
        // Point 1: 키 설계 개선 (차량별 네임스페이스 분리)
        String redisKey = String.format("obd:batch:%s:%s", vehicleId, batchId);

        // Point 2 & 6: 중복 확인 및 처리 정책 (Option A: Processing Lock)
        String status = redisTemplate.opsForValue().get(redisKey);
        if ("DONE".equals(status)) {
            log.info("[ObdService] Batch already processed (DONE): {}", batchId);
            return; // 200 OK (정상 처리로 간주)
        }

        if ("PROCESSING".equals(status)) {
            log.info("[ObdService] Batch is currently being processed: {}", batchId);
            return; // 중복 요청 차단
        }

        // 락 시도 (10분간 유효한 처리중 락)
        Boolean lockAcquired = redisTemplate.opsForValue().setIfAbsent(redisKey, "PROCESSING", 10, TimeUnit.MINUTES);
        if (Boolean.FALSE.equals(lockAcquired)) {
            log.warn("[ObdService] Failed to acquire lock for batch: {}", batchId);
            return;
        }

        try {
            // Point 3: 트랜잭션 내 일괄 저장 (원자성 보장)
            List<ObdLog> obdLogs = batchRequest.getLogs().stream()
                    .map(this::toEntity)
                    .collect(Collectors.toList());

            if (!obdLogs.isEmpty()) {
                obdLogRepository.saveAll(obdLogs);

                // Point 4: TTL 72시간으로 연장 (오프라인 큐 대응)
                redisTemplate.opsForValue().set(redisKey, "DONE", 72, TimeUnit.HOURS);
                log.info("[ObdService] Batch processed successfully: {} ({} logs)", batchId, obdLogs.size());
            }
        } catch (Exception e) {
            // 실패 시 락 해제 (다음 재시도 허용)
            redisTemplate.delete(redisKey);
            log.error("[ObdService] Error processing batch {}: {}", batchId, e.getMessage());
            throw e; // 트랜잭션 롤백 유도
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

        // 주행 종료 시간(endTime)이 없어야 '주행 중(DRIVING)'으로 판단
        boolean isDriving = (trip.getEndTime() == null);

        // 연결 상태는 주행 중이면서 마지막 데이터가 5분 이내인 경우로 판단 (임시 로직)
        boolean isConnected = isDriving && lastTime.isAfter(LocalDateTime.now().minusMinutes(5));

        return ConnectionStatusDto.builder()
                .connected(isConnected)
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
                // 클라이언트가 보낸 LocalDateTime을 시스템 타임존 기준으로 OffsetDateTime 변환
                .time(dto.getTimestamp().atZone(java.time.ZoneId.systemDefault()).toOffsetDateTime())
                .vehicleId(dto.getVehicleId())
                .rpm(dto.getRpm())
                .speed(dto.getSpeed())
                .voltage(dto.getVoltage())
                .coolantTemp(dto.getCoolantTemp())
                .engineLoad(dto.getEngineLoad())
                .fuelTrimShort(dto.getFuelTrimShort())
                .fuelTrimLong(dto.getFuelTrimLong())
                .intakeTemp(dto.getIntakeTemp())
                .map(dto.getMap())
                .maf(dto.getMaf())
                .throttlePos(dto.getThrottlePos())
                .engineRuntime(dto.getEngineRuntime())
                .build();
    }
}
