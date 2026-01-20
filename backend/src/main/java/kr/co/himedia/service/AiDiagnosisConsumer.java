package kr.co.himedia.service;

import kr.co.himedia.config.RabbitConfig;
import kr.co.himedia.dto.ai.DiagnosisTaskMessage;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.stereotype.Component;

/**
 * RabbitMQ 메시지 컨슈머
 * ai.diagnosis.queue로부터 메시지를 수신하여 진단 프로세스(AiDiagnosisService) 지시
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class AiDiagnosisConsumer {

    private final AiDiagnosisService aiDiagnosisService;

    /**
     * 진단 큐 리스너
     * concurrency 설정은 application.yml의 spring.rabbitmq.listener.simple.concurrency를
     * 따름
     */
    @RabbitListener(queues = RabbitConfig.QUEUE_NAME)
    public void consumeDiagnosisTask(DiagnosisTaskMessage message) {
        log.info("[MQ Consumer] Received diagnosis task for Session: {}", message.getSessionId());

        try {
            // 실제 진단 파이프라인 실행
            aiDiagnosisService.processUnifiedFlow(message);
            log.info("[MQ Consumer] Successfully processed diagnosis task for Session: {}", message.getSessionId());
        } catch (Exception e) {
            log.error("[MQ Consumer] Fatal error in diagnosis processing [Session: {}]", message.getSessionId(), e);
            // 여기서 발생한 예외는 RabbitMQ의 Retry 메커니즘을 타거나 최종적으로 DLQ로 이동함
            throw e;
        }
    }
}
