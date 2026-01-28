package kr.co.himedia.entity;

import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.CreationTimestamp;

import java.time.OffsetDateTime;
import java.util.UUID;

/**
 * 하이모빌리티(Cloud)로부터 수집된 텔레메트리 데이터를 저장하는 엔티티
 */
@Entity
@Table(name = "cloud_telemetry")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
@Builder
public class CloudTelemetry {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "telemetry_id")
    private UUID telemetryId;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "vehicles_id", nullable = false)
    private Vehicle vehicle;

    private Double odometer;

    @Column(name = "fuel_level")
    private Double fuelLevel;

    @Column(name = "battery_soc")
    private Double batterySoc;

    @Column(name = "engine_oil_life")
    private Double engineOilLife;

    @Column(name = "tire_pressure_fl")
    private Double tirePressureFl;

    @Column(name = "tire_pressure_fr")
    private Double tirePressureFr;

    @Column(name = "tire_pressure_rl")
    private Double tirePressureRl;

    @Column(name = "tire_pressure_rr")
    private Double tirePressureRr;

    private Double latitude;
    private Double longitude;

    @Column(name = "inside_temp")
    private Double insideTemp;

    @Column(name = "outside_temp")
    private Double outsideTemp;

    @Column(name = "door_lock_status", length = 20)
    private String doorLockStatus;

    @Column(name = "window_open_status", length = 20)
    private String windowOpenStatus;

    @Column(name = "trunk_open_status", length = 20)
    private String trunkOpenStatus;

    @Column(name = "hood_open_status", length = 20)
    private String hoodOpenStatus;

    @Column(name = "battery_capacity")
    private Double batteryCapacity;

    @Column(name = "charge_limit")
    private Double chargeLimit;

    @Enumerated(EnumType.STRING)
    @Column(name = "charging_status")
    private ChargingStatus chargingStatus;

    @CreationTimestamp
    @Column(name = "last_synced_at", updatable = false, columnDefinition = "TIMESTAMPTZ")
    private OffsetDateTime lastSyncedAt;
}
