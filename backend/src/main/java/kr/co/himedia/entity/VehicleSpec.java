package kr.co.himedia.entity;

import jakarta.persistence.*;
import lombok.AccessLevel;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.UpdateTimestamp;

import java.time.LocalDateTime;
import java.util.UUID;

@Entity
@Table(name = "vehicle_specs")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class VehicleSpec {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "spec_id")
    private UUID specId;

    @OneToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "vehicles_id")
    private Vehicle vehicle;

    private Double length;
    private Double width;
    private Double height;
    private Integer displacement;

    @Column(name = "engine_type", length = 50)
    private String engineType;

    @Column(name = "max_power")
    private Double maxPower;

    @Column(name = "max_torque")
    private Double maxTorque;

    @Column(name = "tire_size_front", length = 50)
    private String tireSizeFront;

    @Column(name = "tire_size_rear", length = 50)
    private String tireSizeRear;

    @Column(name = "official_fuel_economy")
    private Double officialFuelEconomy;

    @UpdateTimestamp
    @Column(name = "last_updated")
    private LocalDateTime lastUpdated;

    @Builder
    public VehicleSpec(Vehicle vehicle, Double length, Double width, Double height, Integer displacement,
            String engineType, Double maxPower, Double maxTorque, String tireSizeFront,
            String tireSizeRear, Double officialFuelEconomy) {
        this.vehicle = vehicle;
        this.length = length;
        this.width = width;
        this.height = height;
        this.displacement = displacement;
        this.engineType = engineType;
        this.maxPower = maxPower;
        this.maxTorque = maxTorque;
        this.tireSizeFront = tireSizeFront;
        this.tireSizeRear = tireSizeRear;
        this.officialFuelEconomy = officialFuelEconomy;
    }
}
