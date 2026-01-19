package kr.co.himedia.dto.maintenance.ai;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Getter;
import lombok.Setter;
import lombok.NoArgsConstructor;
import java.util.Map;

@Getter
@Setter
@NoArgsConstructor
public class AiWearFactorResponse {
    @JsonProperty("wear_factors")
    private Map<String, Double> wearFactors;

    @JsonProperty("model_version")
    private String modelVersion;
}
