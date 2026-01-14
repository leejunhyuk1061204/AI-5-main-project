package kr.co.himedia.entity;

import jakarta.persistence.*;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Entity
@Table(name = "car_model_master")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class CarModelMaster {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "model_id")
    private Long modelId;

    @Column(name = "manufacturer", length = 50)
    private String manufacturer;

    @Column(name = "model_name", length = 100)
    private String modelName;

    @Column(name = "model_year")
    private Integer modelYear;

    @Column(name = "fuel_type", length = 20)
    private String fuelType;

    @Column(name = "displacement")
    private Integer displacement;

    @Column(name = "spec_json", columnDefinition = "jsonb")
    private String specJson;
}
