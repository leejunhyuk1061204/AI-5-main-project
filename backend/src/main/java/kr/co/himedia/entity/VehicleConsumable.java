package kr.co.himedia.entity;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.UpdateTimestamp;

import java.time.LocalDateTime;
import java.util.UUID;

/**
 * 차량별 소모품 상태 엔티티 (vehicle_consumables)
 * 차량과 소모품 마스터 간의 매핑 및 상태 정보를 관리합니다.
 */
@Entity
@Table(name = "vehicle_consumables", uniqueConstraints = {
        @UniqueConstraint(columnNames = { "vehicles_id", "consumable_item_id" })
})
@Getter
@Setter
@NoArgsConstructor
public class VehicleConsumable {

    @Id
    @GeneratedValue(strategy = GenerationType.AUTO)
    @Column(name = "vehicle_consumable_id")
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "vehicles_id", nullable = false)
    private Vehicle vehicle;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "consumable_item_id", nullable = false)
    private ConsumableItem consumableItem;

    @Column(name = "wear_factor", nullable = false)
    private Double wearFactor = 1.0; // AI 마모 가중치

    @Column(name = "is_inferred", nullable = false)
    private Boolean isInferred = false; // 시스템 추론 데이터 여부

    @Column(name = "remaining_life")
    private Double remainingLife; // 잔존 수명 (%) (캐싱용)

    @Column(name = "last_replaced_at")
    private LocalDateTime lastReplacedAt;

    @Column(name = "last_replaced_mileage")
    private Double lastReplacedMileage; // 마지막 교체 시점 주행거리

    @CreationTimestamp
    @Column(name = "created_at", updatable = false)
    private LocalDateTime createdAt;

    @UpdateTimestamp
    @Column(name = "updated_at")
    private LocalDateTime updatedAt;

    // Helper method to set remaining life safely
    public void updateRemainingLife(Double newLife) {
        this.remainingLife = newLife;
        this.updatedAt = LocalDateTime.now();
    }
}
