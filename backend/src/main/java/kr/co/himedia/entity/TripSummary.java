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
