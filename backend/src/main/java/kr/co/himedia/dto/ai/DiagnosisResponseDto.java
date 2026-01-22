package kr.co.himedia.dto.ai;

import java.time.LocalDateTime;
import java.util.UUID;
import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class DiagnosisResponseDto {
    private UUID sessionId;
    private String status; // PENDING, PROCESSING, DONE, ACTION_REQUIRED, FAILED
    private String progressMessage;

    private String responseMode; // REPORT | INTERACTIVE
    private String confidenceLevel; // HIGH | MEDIUM | LOW
    private String summary;

    // REPORT Mode Data
    private String finalReport;
    private Object suspectedCauses; // JSON List
    private String riskLevel;

    // INTERACTIVE Mode Data
    private Object interactiveData; // JSON Object

    private LocalDateTime createdAt;
}
