package kr.co.himedia.dto.maintenance.ai;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Builder;
import lombok.Getter;

import java.util.List;

/**
 * AI 서버 마모율 예측 요청 DTO (Phase 2 - 다중 소모품 컨텍스트 지원)
 */
@Getter
@Builder
public class AiWearFactorRequest {

    @JsonProperty("vehicle_metadata")
    private VehicleMetadata vehicleMetadata;

    @JsonProperty("driving_habits")
    private DrivingHabits drivingHabits;

    @JsonProperty("consumables")
    private List<ConsumableContext> consumables;

    /**
     * 소모품별 컨텍스트 (isInferred 플래그 포함)
     */
    @Getter
    @Builder
    public static class ConsumableContext {
        @JsonProperty("code")
        private String code;

        @JsonProperty("last_replaced_mileage")
        private double lastReplacedMileage;

        @JsonProperty("is_inferred")
        private boolean isInferred;
    }

    @Getter
    @Builder
    public static class VehicleMetadata {
        @JsonProperty("model_year")
        private int modelYear;
        @JsonProperty("fuel_type")
        private String fuelType;
        @JsonProperty("total_mileage")
        private int totalMileage;
    }

    @Getter
    @Builder
    public static class DrivingHabits {
        @JsonProperty("avg_rpm")
        private double avgRpm;
        @JsonProperty("hard_accel_count")
        private int hardAccelCount;
        @JsonProperty("hard_brake_count")
        private int hardBrakeCount;
        @JsonProperty("idle_ratio")
        private double idleRatio;
    }
}
