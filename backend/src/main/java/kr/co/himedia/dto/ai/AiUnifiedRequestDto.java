package kr.co.himedia.dto.ai;

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
public class AiUnifiedRequestDto {
    private String vehicleId;
    private Map<String, Object> audioAnalysis;
    private Map<String, Object> visualAnalysis;
    private Map<String, Object> lstmAnalysis;
    private java.util.List<String> knowledgeData; // RAG 검색 결과
    private List<String> ragContext; // RAG 검색 결과 문서 리스트
}
