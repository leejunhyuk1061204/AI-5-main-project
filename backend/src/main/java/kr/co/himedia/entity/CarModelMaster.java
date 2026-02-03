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

    /**
     * 제조사 (한글)
     */
    @Column(name = "manufacturer_ko", length = 50)
    private String manufacturerKo;

    /**
     * 제조사 (영어)
     */
    @Column(name = "manufacturer_en", length = 50)
    private String manufacturerEn;

    /**
     * 모델명 (한글)
     */
    @Column(name = "model_name_ko", length = 100)
    private String modelNameKo;

    /**
     * 모델명 (영어)
     */
    @Column(name = "model_name_en", length = 100)
    private String modelNameEn;

    @Column(name = "model_year")
    private Integer modelYear;

    @Column(name = "fuel_type", length = 20)
    private String fuelType;

    @Column(name = "displacement")
    private Integer displacement;

    @Column(name = "spec_json", columnDefinition = "jsonb")
    private String specJson;
}
