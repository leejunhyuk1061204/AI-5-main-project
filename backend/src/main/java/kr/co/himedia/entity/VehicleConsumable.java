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
    @Column(name = "consumable_id")
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "vehicle_id", nullable = false)
    private Vehicle vehicle;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private MaintenanceItem item;

    @Column(name = "last_maintenance_mileage")
    private Double lastMaintenanceMileage;

    @Column(name = "last_maintenance_date")
    private LocalDate lastMaintenanceDate;

    @Column(name = "replacement_interval_mileage")
    private Double replacementIntervalMileage;

    @Column(name = "replacement_interval_months")
    private Integer replacementIntervalMonths;

    @Column(name = "wear_factor")
    private Double wearFactor;

    @Column(name = "wear_factor_updated_at")
    private java.time.LocalDateTime wearFactorUpdatedAt;

    @Builder
    public VehicleConsumable(Vehicle vehicle, MaintenanceItem item, Double lastMaintenanceMileage,
            LocalDate lastMaintenanceDate, Double replacementIntervalMileage, Integer replacementIntervalMonths) {
        this.vehicle = vehicle;
        this.item = item;
        this.lastMaintenanceMileage = lastMaintenanceMileage != null ? lastMaintenanceMileage : 0.0;
        this.lastMaintenanceDate = lastMaintenanceDate != null ? lastMaintenanceDate : LocalDate.now();
        this.replacementIntervalMileage = replacementIntervalMileage;
        this.replacementIntervalMonths = replacementIntervalMonths;
    }

    public void updateMaintenanceInfo(Double mileage, LocalDate date) {
        this.lastMaintenanceMileage = mileage;
        this.lastMaintenanceDate = date;
    }

    public void updateWearFactor(Double wearFactor) {
        this.wearFactor = wearFactor;
        this.wearFactorUpdatedAt = java.time.LocalDateTime.now();
    }
}
