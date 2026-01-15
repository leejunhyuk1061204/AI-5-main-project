package kr.co.himedia.entity;

import jakarta.persistence.*;
import kr.co.himedia.common.BaseEntity;
import lombok.AccessLevel;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.time.LocalDate;

@Entity
@Table(name = "maintenance_histories")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class MaintenanceHistory extends BaseEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "maintenance_id")
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "vehicle_id", nullable = false)
    private Vehicle vehicle;

    @Column(name = "maintenance_date", nullable = false)
    private LocalDate maintenanceDate;

    @Column(name = "mileage_at_maintenance", nullable = false)
    private Double mileageAtMaintenance;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private MaintenanceItem item;

    private Integer cost;

    @Column(columnDefinition = "TEXT")
    private String memo;

    @Builder
    public MaintenanceHistory(Vehicle vehicle, LocalDate maintenanceDate, Double mileageAtMaintenance,
            MaintenanceItem item, Integer cost, String memo) {
        this.vehicle = vehicle;
        this.maintenanceDate = maintenanceDate;
        this.mileageAtMaintenance = mileageAtMaintenance;
        this.item = item;
        this.cost = cost;
        this.memo = memo;
    }
}
