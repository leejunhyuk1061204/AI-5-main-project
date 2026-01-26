package kr.co.himedia.service;

import kr.co.himedia.config.RabbitConfig;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.stereotype.Service;

import java.util.UUID;

/**
 * 하이모빌리티 클라우드 데이터 동기화 메시지 발행 서비스
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class CloudSyncProducer {

    private final RabbitTemplate rabbitTemplate;

    /**
     * 동기화 요청 메시지를 큐에 발행합니다.
     */
    public void publishSyncRequest(UUID vehicleId) {
        log.info("[Producer] 클라우드 동기화 요청 발행 - vehicleId: {}", vehicleId);
        rabbitTemplate.convertAndSend(
                RabbitConfig.EXCHANGE_NAME,
                RabbitConfig.CLOUD_SYNC_ROUTING_KEY,
                vehicleId.toString());
    }

    /**
     * 상태가 PENDING일 때 재시도를 위해 지연 큐로 메시지를 보냅니다.
     */
    public void publishToDelayQueue(String vehicleId) {
        log.info("[Producer] 상태 미승인 - 지연 큐로 이동 (15초 대기) - vehicleId: {}", vehicleId);
        rabbitTemplate.convertAndSend(
                RabbitConfig.CLOUD_SYNC_DELAY_QUEUE, // 직접 큐로 전송하여 TTL 적용
                vehicleId);
    }
}
