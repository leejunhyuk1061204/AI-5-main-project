package kr.co.himedia.dto.ai;

import lombok.*;
import java.util.UUID;

/**
 * RabbitMQ 큐로 전송되는 진단 작업 메시지
 */
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class DiagnosisTaskMessage {
    private UUID sessionId;
    private UnifiedDiagnosisRequestDto requestDto;
    private ReplyRequestDto replyRequest; // 채팅 답변 요청 시 포함
    private MessageType messageType; // INITIAL vs REPLY
    private String imageFilename;
    private String audioFilename;

    public enum MessageType {
        INITIAL, REPLY
    }
}
