package kr.co.himedia.entity;

import jakarta.persistence.*;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Entity
@Table(name = "consumable_items")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class ConsumableItem {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, unique = true)
    private String code; // e.g., "ENGINE_OIL"

    @Column(nullable = false)
    private String name; // e.g., "엔진오일"

    @Column(name = "default_interval_mileage")
    private Integer defaultIntervalMileage; // km

    @Column(name = "default_interval_months")
    private Integer defaultIntervalMonths; // months

    @Column(columnDefinition = "TEXT")
    private String description;

    public ConsumableItem(String code, String name, Integer defaultIntervalMileage, Integer defaultIntervalMonths,
            String description) {
        this.code = code;
        this.name = name;
        this.defaultIntervalMileage = defaultIntervalMileage;
        this.defaultIntervalMonths = defaultIntervalMonths;
        this.description = description;
    }
}
