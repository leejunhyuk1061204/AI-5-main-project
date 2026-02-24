package kr.co.himedia.service;

import kr.co.himedia.config.RabbitConfig;
import kr.co.himedia.dto.ai.DiagnosisTaskMessage;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.stereotype.Component;

/**
 * AI 진단 DLQ(Dead Letter Queue) 컨슈머.
 * 재시도 한계를 초과해 ai.diagnosis.dlq로 이동한 메시지만 처리하여
 * 최종 1회 실패 FCM을 발송한다.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class AiDiagnosisDlqConsumer {

    private final AiDiagnosisService aiDiagnosisService;

    /**
     * DLQ 리스너: 재시도 끝에 실패한 진단 작업에 대한 후속 처리만 수행한다.
     * 여기서는 진단 파이프라인을 다시 실행하지 않고, 세션 상태/알림만 정리한다.
     */
    @RabbitListener(queues = RabbitConfig.DLQ_NAME)
    public void consumeDeadDiagnosisTask(DiagnosisTaskMessage message) {
        log.error("[MQ DLQ Consumer] Received dead diagnosis task for Session: {}", message.getSessionId());
        aiDiagnosisService.handleDeadDiagnosisTask(message);
    }
}

