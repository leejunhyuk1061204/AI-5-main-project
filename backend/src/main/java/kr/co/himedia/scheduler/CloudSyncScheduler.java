package kr.co.himedia.scheduler;

import kr.co.himedia.entity.Vehicle;
import kr.co.himedia.repository.VehicleRepository;
import kr.co.himedia.service.CloudAuthService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.util.List;

/**
 * 하이모빌리티 클라우드 데이터 전수 동기화 스케줄러 (안전망)
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class CloudSyncScheduler {

    private final VehicleRepository vehicleRepository;
    private final CloudAuthService cloudAuthService;

    /**
     * 매일 새벽 3시에 모든 클라우드 연동 차량의 데이터를 정기 동기화합니다.
     */
    @Scheduled(cron = "0 0 3 * * *")
    public void syncAllCloudVehicles() {
        log.info("[Scheduler] 클라우드 차량 일일 정기 동기화 시작 (03:00)");

        List<Vehicle> linkedVehicles = vehicleRepository.findByCloudLinkedTrueAndDeletedAtIsNull();
        log.info("[Scheduler] 정기 동기화 대상 차량 수: {}대", linkedVehicles.size());

        for (Vehicle vehicle : linkedVehicles) {
            try {
                cloudAuthService.syncVehicleData(vehicle.getVehicleId(), true);
            } catch (Exception e) {
                log.error("[Scheduler] 정기 동기화 실패 - vehicleId: {}", vehicle.getVehicleId(), e);
            }
        }

        log.info("[Scheduler] 클라우드 차량 일일 정기 동기화 완료");
    }
}
