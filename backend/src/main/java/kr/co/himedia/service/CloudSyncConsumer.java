package kr.co.himedia.service;

import kr.co.himedia.config.RabbitConfig;
import kr.co.himedia.entity.Vehicle;
import kr.co.himedia.repository.VehicleRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.messaging.handler.annotation.Header;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * 하이모빌리티 클라우드 데이터 동기화 메시지 소비자
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class CloudSyncConsumer {

    private final HighMobilityService highMobilityService;
    private final CloudAuthService cloudAuthService;
    private final CloudSyncProducer cloudSyncProducer;
    private final VehicleRepository vehicleRepository;
    private final kr.co.himedia.common.util.EncryptionUtils encryptionUtils;

    private static final int MAX_RETRY_COUNT = 3;

    /**
     * 클라우드 동기화 큐를 구독하여 처리합니다.
     */
    @RabbitListener(queues = RabbitConfig.CLOUD_SYNC_QUEUE)
    public void consumeSyncRequest(String vehicleId,
            @Header(name = "x-death", required = false) List<Map<String, Object>> xDeath) {
        log.info("[Consumer] 동기화 메시지 수신 - vehicleId: {}", vehicleId);

        // 1. 재시도 횟수 확인 (무한 루프 방지)
        int retryCount = 0;
        if (xDeath != null && !xDeath.isEmpty()) {
            retryCount = ((Long) xDeath.get(0).get("count")).intValue();
        }

        if (retryCount >= MAX_RETRY_COUNT) {
            log.warn("[Consumer] 최대 재시도 횟수({}) 초과. 작업을 중단합니다. - vehicleId: {}", MAX_RETRY_COUNT, vehicleId);
            return;
        }

        try {
            Vehicle vehicle = vehicleRepository.findById(UUID.fromString(vehicleId))
                    .orElseThrow(() -> new RuntimeException("Vehicle not found"));

            if (vehicle.getVin() == null)
                return;
            String decryptedVin = encryptionUtils.decrypt(vehicle.getVin());

            // 2. 승인 상태 먼저 조회 (사용자 제안 반영)
            Map<String, Object> statusResult = highMobilityService.getClearanceStatus(decryptedVin);
            String status = (String) statusResult.get("status");
            log.info("[Consumer] 차량 상태 조회 결과: {} - vehicleId: {}", status, vehicleId);

            if ("APPROVED".equalsIgnoreCase(status)) {
                // 3. 승인된 경우 데이터 동기화 수행
                log.info("[Consumer] 승인 확인됨. 데이터 동기화를 시작합니다. - vehicleId: {}", vehicleId);
                cloudAuthService.syncVehicleData(UUID.fromString(vehicleId), true);
            } else {
                // 4. PENDING 등 승인 전인 경우 지연 큐로 재전송 (15초 대기)
                log.info("[Consumer] 아직 승인 전입니다. 15초 뒤에 다시 시도합니다. (현재 {}회 재시도)", retryCount + 1);
                cloudSyncProducer.publishToDelayQueue(vehicleId);
            }

        } catch (Exception e) {
            log.error("[Consumer] 동기화 처리 중 에러 발생 (15초 뒤 재시도 예정) - vehicleId: {}", vehicleId, e);
            cloudSyncProducer.publishToDelayQueue(vehicleId);
        }
    }
}
