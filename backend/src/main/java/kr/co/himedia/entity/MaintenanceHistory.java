package kr.co.himedia.entity;

import jakarta.persistence.*;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;
import kr.co.himedia.common.BaseEntity;
import lombok.AccessLevel;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.time.LocalDate;
import java.util.UUID;

/**
 * 차량의 정비 및 소모품 교체 이력을 관리하는 엔티티입니다.
 */
@Entity
@Table(name = "maintenance_logs")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class MaintenanceHistory extends BaseEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.AUTO)
    @Column(name = "maintenance_id")
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "vehicle_id", nullable = false)
    private Vehicle vehicle;

    @Column(name = "maintenance_date", nullable = false)
    private LocalDate maintenanceDate;

    @Column(name = "mileage_at_maintenance", nullable = false)
    private Double mileageAtMaintenance;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "consumable_item_id")
    private ConsumableItem consumableItem;

    @Column(name = "is_standardized")
    private Boolean isStandardized;

    @Column(name = "shop_name")
    private String shopName;

    @Column(name = "cost")
    private Integer cost;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "ocr_data", columnDefinition = "jsonb")
    private String ocrData;

    @Column(columnDefinition = "TEXT")
    private String memo;

    @Builder
    public MaintenanceHistory(Vehicle vehicle, LocalDate maintenanceDate, Double mileageAtMaintenance,
            ConsumableItem consumableItem, Boolean isStandardized, String shopName, Integer cost, String ocrData,
            String memo) {
        this.vehicle = vehicle;
        this.maintenanceDate = maintenanceDate;
        this.mileageAtMaintenance = mileageAtMaintenance;
        this.consumableItem = consumableItem;
        this.isStandardized = isStandardized;
        this.shopName = shopName;
        this.cost = cost;
        this.ocrData = ocrData;
        this.memo = memo;
    }
}
