package kr.co.himedia.dto.ai;

import com.fasterxml.jackson.annotation.JsonInclude;
import lombok.*;
import java.util.List;
import java.util.Map;

/**
 * AI 서버로 통합 진단을 요청하기 위한 내부 DTO
 */
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
@JsonInclude(JsonInclude.Include.NON_NULL)
public class AiUnifiedRequestDto {
    @com.fasterxml.jackson.annotation.JsonProperty("visual_analysis")
    private Map<String, Object> visualAnalysis;

    @com.fasterxml.jackson.annotation.JsonProperty("audio_analysis")
    private Map<String, Object> audioAnalysis;

    @com.fasterxml.jackson.annotation.JsonProperty("anomaly_analysis")
    private Map<String, Object> anomalyAnalysis;

    @com.fasterxml.jackson.annotation.JsonProperty("knowledge_data")
    private List<String> knowledgeData;

    @com.fasterxml.jackson.annotation.JsonProperty("conversation_history")
    private List<Map<String, Object>> conversationHistory;

    @com.fasterxml.jackson.annotation.JsonProperty("vehicle_info")
    private Map<String, Object> vehicleInfo;

    @com.fasterxml.jackson.annotation.JsonProperty("consumables_status")
    private List<Map<String, Object>> consumablesStatus;
}
