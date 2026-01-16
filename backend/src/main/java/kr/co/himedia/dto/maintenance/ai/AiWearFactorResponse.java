package kr.co.himedia.dto.maintenance.ai;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@NoArgsConstructor
public class AiWearFactorResponse {
    @JsonProperty("predicted_wear_factor")
    private Double predictedWearFactor;

    @JsonProperty("model_version")
    private String modelVersion;
}
