package kr.co.himedia.dto.maintenance.ai;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Getter;
import lombok.Setter;
import lombok.NoArgsConstructor;
import java.util.Map;

/**
 * AI 서버 마모율 예측 응답 DTO (Phase 2 - 잔존 수명 포함)
 */
@Getter
@Setter
@NoArgsConstructor
public class AiWearFactorResponse {
    @JsonProperty("wear_factors")
    private Map<String, Double> wearFactors;

    @JsonProperty("remaining_lifes")
    private Map<String, Double> remainingLifes;

    @JsonProperty("model_version")
    private String modelVersion;
}
