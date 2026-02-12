package kr.co.himedia.entity;

import jakarta.persistence.*;
import lombok.*;

import java.io.Serializable;
import java.time.LocalDateTime;
import java.util.UUID;

@Entity
@Table(name = "trip_summaries")
@Getter
@Setter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
@Builder
@IdClass(TripSummary.TripSummaryId.class)
public class TripSummary {

    @Id
    @Column(name = "start_time")
    private LocalDateTime startTime;

    @Id
    @Column(name = "vehicles_id")
    private UUID vehicleId;

    @Column(name = "trip_id", unique = true, nullable = false, updatable = false)
    private UUID tripId;

    @Column(name = "end_time")
    private LocalDateTime endTime;

    @Column(name = "distance")
    private Double distance;

    @Column(name = "drive_score")
    private Integer driveScore;

    @Column(name = "average_speed")
    private Double averageSpeed;

    @Column(name = "top_speed")
    private Double topSpeed;

    @Column(name = "fuel_consumed")
    private Double fuelConsumed;

    @Column(name = "min_battery_voltage")
    private Double minBatteryVoltage;

    @Column(name = "max_coolant_temp")
    private Double maxCoolantTemp;

    @Column(name = "avg_fuel_trim")
    private Double avgFuelTrim;

    @Column(name = "max_engine_load")
    private Double maxEngineLoad;

    @Column(name = "idle_time")
    private Integer idleTime;

    @Column(name = "hard_accel_count")
    private Integer hardAccelCount;

    @Column(name = "hard_brake_count")
    private Integer hardBrakeCount;

    @Column(name = "high_rpm_ratio")
    private Double highRpmRatio; // Nullable for backward compatibility

    @Column(name = "avg_rpm")
    private Double avgRpm;

    @Column(name = "avg_engine_load")
    private Double avgEngineLoad;

    @Column(name = "avg_maf")
    private Double avgMaf;

    @Column(name = "avg_throttle_pos")
    private Double avgThrottlePos;

    @Column(name = "overheat_duration_sec")
    private Integer overheatDurationSec;

    @Embeddable
    @Getter
    @Setter
    @NoArgsConstructor
    @AllArgsConstructor
    @EqualsAndHashCode
    public static class TripSummaryId implements Serializable {
        private LocalDateTime startTime;
        private UUID vehicleId;
    }

    @PrePersist
    public void prePersist() {
        if (this.tripId == null) {
            this.tripId = UUID.randomUUID();
        }
    }
}
