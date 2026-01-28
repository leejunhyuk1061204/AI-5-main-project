package kr.co.himedia.dto.ai;

import java.time.LocalDateTime;
import java.util.UUID;
import lombok.Builder;
import lombok.Getter;

/**
 * 진단 세션 목록 조회용 간략 DTO
 */
@Getter
@Builder
public class DiagnosisListItemDto {
    private UUID sessionId;
    private String status;
    private String progressMessage;
    private String triggerType;
    private String triggerTypeLabel; // 신규: 한글 라벨
    private String responseMode;
    private String riskLevel;
    private LocalDateTime createdAt;
}
