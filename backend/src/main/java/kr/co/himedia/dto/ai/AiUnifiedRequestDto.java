package kr.co.himedia.dto.ai;

import com.fasterxml.jackson.annotation.JsonInclude;
import lombok.*;
import java.util.List;
import java.util.Map;
import java.util.UUID;

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
    private UUID vehicleId;
    private Map<String, Object> audioAnalysis;
    private Map<String, Object> visualAnalysis;
    private Map<String, Object> anomalyAnalysis; // /anomaly 이상 탐지 결과
    private java.util.List<String> knowledgeData; // RAG 검색 결과
    private List<String> ragContext; // RAG 검색 결과 문서 리스트

    // 차량 제원 정보 (manufacturer, model, year, fuelType, totalMileage)
    private Map<String, Object> vehicleInfo;

    // 소모품 잔여 수명 정보 (item, remainingLifePct, wearFactor)
    private List<Map<String, Object>> consumablesStatus;
}
