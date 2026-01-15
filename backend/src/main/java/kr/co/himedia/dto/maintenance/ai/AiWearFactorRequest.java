package kr.co.himedia.dto.maintenance.ai;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Builder;
import lombok.Getter;

import java.time.LocalDate;

@Getter
@Builder
public class AiWearFactorRequest {
    @JsonProperty("target_item")
    private String targetItem;

    @JsonProperty("last_replaced")
    private LastReplaced lastReplaced;

    @JsonProperty("vehicle_metadata")
    private VehicleMetadata vehicleMetadata;

    @JsonProperty("driving_habits")
    private DrivingHabits drivingHabits;

    @Getter
    @Builder
    public static class LastReplaced {
        @JsonProperty("date")
        private LocalDate date;
        @JsonProperty("mileage")
        private int mileage;
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
