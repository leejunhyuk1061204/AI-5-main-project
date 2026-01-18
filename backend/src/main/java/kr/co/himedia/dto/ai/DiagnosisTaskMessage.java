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
    private String imageFilename; // 서버 로컬에 저장된 이미지 파일명
    private String audioFilename; // 서버 로컬에 저장된 오디오 파일명
}
