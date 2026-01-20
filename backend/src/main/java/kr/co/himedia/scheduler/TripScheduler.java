package kr.co.himedia.scheduler;

import kr.co.himedia.repository.ObdLogRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

@Component
@RequiredArgsConstructor
@Slf4j
public class TripScheduler {

    private final ObdLogRepository obdLogRepository;

    // BE-TD-006: 데이터 리텐션 (3일 경과 데이터 삭제)
    // 매일 새벽 3시에 실행
    @Scheduled(cron = "0 0 3 * * *")
    @Transactional
    public void cleanupOldLogs() {
        log.info("[Scheduler] Starting cleanup of old OBD logs...");
        // UTC 기준 3일 전 데이터 삭제
        java.time.OffsetDateTime retentionLimit = java.time.OffsetDateTime.now(java.time.ZoneOffset.UTC).minusDays(3);

        try {
            obdLogRepository.deleteByTimeBefore(retentionLimit);
            log.info("[Scheduler] Deleted logs older than: {}", retentionLimit);
        } catch (Exception e) {
            log.error("[Scheduler] Failed to cleanup logs", e);
        }
    }

}
