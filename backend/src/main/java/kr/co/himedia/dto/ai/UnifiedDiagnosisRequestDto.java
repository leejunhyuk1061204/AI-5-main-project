package kr.co.himedia.dto.ai;

import lombok.*;
import java.util.Map;
import java.util.UUID;

/**
 * 프론트엔드로부터 통합 진단 결과를 받기 위한 DTO
 */
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class UnifiedDiagnosisRequestDto {
    private UUID vehicleId;
    private Map<String, Object> audioAnalysis; // 소리 분석 결과 (Optional)
    private Map<String, Object> visualAnalysis; // 사진 분석 결과 (Optional)
    private Map<String, Object> lstmAnalysis; // LSTM 분석 결과 (Optional)
    private java.util.List<String> knowledgeData; // RAG 검색 결과 (Optional)
}
