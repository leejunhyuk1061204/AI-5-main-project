package kr.co.himedia.entity;

import jakarta.persistence.*;
import kr.co.himedia.common.BaseEntity;
import lombok.*;

import java.time.LocalDate;
import java.util.UUID;

@Entity
@Table(name = "fueling_logs")
@Getter
@Setter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
@Builder
public class FuelingHistory extends BaseEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.AUTO)
    @Column(name = "fueling_id")
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "vehicle_id", nullable = false)
    private Vehicle vehicle;

    @Enumerated(EnumType.STRING)
    @Column(name = "fuel_type", nullable = false)
    private FuelType fuelType;

    @Column(name = "fueling_date", nullable = false)
    private LocalDate fuelingDate;

    @Column(name = "amount")
    private Double amount; // L or kWh (nullable; 총액·단가로 역산 가능)

    @Column(name = "unit_price")
    private Integer unitPrice;

    @Column(name = "total_cost", nullable = false)
    private Integer totalCost;

    @Column(name = "mileage_at_fueling")
    private Double mileageAtFueling;

    @Column(name = "shop_name")
    private String shopName;

    @Column(name = "station_name") // shopName과 혼용될 수 있으나 주유소명을 별도로 관리
    private String stationName;

    @Column(columnDefinition = "TEXT")
    private String memo;

    @Column(name = "receipt_id")
    private UUID receiptId;
}
