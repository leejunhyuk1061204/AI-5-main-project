package kr.co.himedia.entity;

import jakarta.persistence.*;
import kr.co.himedia.common.BaseEntity;
import lombok.AccessLevel;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.time.LocalDate;

@Entity
@Table(name = "vehicle_consumables")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class VehicleConsumable extends BaseEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "vehicle_consumable_id")
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "vehicle_id", nullable = false)
    private Vehicle vehicle;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "consumable_id", nullable = false)
    private ConsumableItem consumableItem;

    // Last maintenance info is now derived from MaintenanceHistory, removed
    // redundant columns.
    // Custom replacement intervals (user overrides)
    @Column(name = "custom_interval_mileage")
    private Double customIntervalMileage;

    @Column(name = "custom_interval_months")
    private Integer customIntervalMonths;

    @Column(name = "wear_factor")
    private Double wearFactor;

    @Column(name = "wear_factor_updated_at")
    private java.time.LocalDateTime wearFactorUpdatedAt;

    @Builder
    public VehicleConsumable(Vehicle vehicle, ConsumableItem consumableItem,
            Double customIntervalMileage, Integer customIntervalMonths, Double wearFactor) {
        this.vehicle = vehicle;
        this.consumableItem = consumableItem;
        this.customIntervalMileage = customIntervalMileage;
        this.customIntervalMonths = customIntervalMonths;
        this.wearFactor = wearFactor != null ? wearFactor : 1.0;
        this.wearFactorUpdatedAt = java.time.LocalDateTime.now();
    }

    public void updateWearFactor(Double wearFactor) {
        this.wearFactor = wearFactor;
        this.wearFactorUpdatedAt = java.time.LocalDateTime.now();
    }
}
