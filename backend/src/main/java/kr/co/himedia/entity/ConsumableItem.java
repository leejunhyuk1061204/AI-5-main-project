package kr.co.himedia.entity;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

/**
 * 소모품 마스터 엔티티 (consumable_items)
 * 다양한 소모품의 표준 명칭과 교체 주기를 관리합니다.
 */
@Entity
@Table(name = "consumable_items")
@Getter
@Setter
@NoArgsConstructor
public class ConsumableItem {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(unique = true, nullable = false, length = 50)
    private String code; // 예: ENGINE_OIL

    @Column(nullable = false, length = 100)
    private String name; // 예: 엔진 오일

    @Column(name = "default_interval_mileage", nullable = false)
    private Integer defaultIntervalMileage; // 표준 교체 주기 (km)

    @Column(name = "default_interval_months")
    private Integer defaultIntervalMonths; // 표준 교체 주기 (개월)

    @Column(columnDefinition = "TEXT")
    private String description;
}
