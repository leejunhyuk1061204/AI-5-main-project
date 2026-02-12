package kr.co.himedia.entity;

import jakarta.persistence.*;
import lombok.AccessLevel;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.CreationTimestamp;

import java.time.LocalDateTime;
import java.util.UUID;

@Entity
@Table(name = "vehicles")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class Vehicle {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "vehicles_id")
    private UUID vehicleId;

    @Column(name = "user_id", nullable = false)
    private UUID userId;

    @Column(name = "vin", unique = true)
    private String vin;

    @Column(name = "car_number", length = 20)
    private String carNumber;

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

    @Enumerated(EnumType.STRING)
    @Column(name = "fuel_type")
    private FuelType fuelType;

    @Column(name = "total_mileage")
    private Double totalMileage;

    @Column(name = "is_primary")
    private Boolean isPrimary;

    @Enumerated(EnumType.STRING)
    @Column(name = "registration_source")
    private RegistrationSource registrationSource;

    @Column(name = "cloud_linked")
    private Boolean cloudLinked;

    @Column(name = "nickname", length = 50)
    private String nickname;

    @Column(name = "memo", columnDefinition = "TEXT")
    private String memo;

    @CreationTimestamp
    @Column(name = "created_at", updatable = false)
    private LocalDateTime createdAt;

    @Column(name = "deleted_at")
    private LocalDateTime deletedAt;

    @Builder
    public Vehicle(UUID userId, String vin, String carNumber, String manufacturerKo, String manufacturerEn,
            String modelNameKo, String modelNameEn,
            Integer modelYear, FuelType fuelType, Double totalMileage, Boolean isPrimary,
            RegistrationSource registrationSource, String nickname, String memo) {
        this.userId = userId;
        this.vin = vin;
        this.carNumber = carNumber;
        this.manufacturerKo = manufacturerKo;
        this.manufacturerEn = manufacturerEn;
        this.modelNameKo = modelNameKo;
        this.modelNameEn = modelNameEn;
        this.modelYear = modelYear;
        this.fuelType = fuelType;
        this.totalMileage = (totalMileage != null) ? totalMileage : 0.0;
        this.isPrimary = (isPrimary != null) ? isPrimary : false;
        this.registrationSource = registrationSource;
        this.cloudLinked = false; // Default
        this.nickname = nickname;
        this.memo = memo;
    }

    public void updateInfo(String nickname, String memo) {
        this.nickname = nickname;
        this.memo = memo;
    }

    public void setPrimary(boolean isPrimary) {
        this.isPrimary = isPrimary;
    }

    public void delete() {
        this.deletedAt = LocalDateTime.now();
    }

    public void updateTotalMileage(Double totalMileage) {
        this.totalMileage = totalMileage;
    }

    public void updateCarNumber(String carNumber) {
        this.carNumber = carNumber;
    }

    /**
     * 차량 연동 상태 및 VIN 정보를 업데이트합니다.
     */
    public void updateCloudLinkStatus(boolean linked) {
        this.cloudLinked = linked;
        this.registrationSource = RegistrationSource.CLOUD;
    }

    /**
     * 복호화된 VIN을 받아 암호화하여 저장합니다.
     */
    public void updateVin(String encryptedVin) {
        this.vin = encryptedVin;
    }

    /**
     * 제조사/모델 영문명 보정 (수동 등록 시 미입력이면 car_model_master에서 채울 때 사용)
     */
    public void setManufacturerAndModelEn(String manufacturerEn, String modelNameEn) {
        if (manufacturerEn != null && !manufacturerEn.isBlank()) {
            this.manufacturerEn = manufacturerEn;
        }
        if (modelNameEn != null && !modelNameEn.isBlank()) {
            this.modelNameEn = modelNameEn;
        }
    }
}
