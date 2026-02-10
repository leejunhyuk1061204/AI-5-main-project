package kr.co.himedia.dto.vehicle;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import kr.co.himedia.entity.FuelType;
import kr.co.himedia.entity.RegistrationSource;
import kr.co.himedia.entity.Vehicle;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.util.UUID;

public class VehicleDto {

    @Getter
    @Setter
    @NoArgsConstructor
    public static class UpdateRequest {
        private String nickname;
        private String memo;
        private String carNumber;
        private String vin;

        @Min(value = 0, message = "주행거리는 0 이상이어야 합니다.")
        private Double totalMileage;
    }

    @Getter
    @Setter
    @NoArgsConstructor
    public static class RegistrationRequest {
        @NotBlank(message = "제조사(한글)는 필수입니다.")
        private String manufacturerKo;

        private String manufacturerEn;

        @NotBlank(message = "모델명(한글)은 필수입니다.")
        private String modelNameKo;

        private String modelNameEn;

        @NotNull(message = "연식은 필수입니다.")
        private Integer modelYear;

        @NotNull(message = "유종은 필수입니다.")
        private FuelType fuelType;

        @Min(value = 0, message = "주행거리는 0 이상이어야 합니다.")
        private Double totalMileage;

        private String nickname;
        private String memo;
        private String carNumber;
        private String vin;

        // 추가: 소모품 등록 리스트
        private java.util.List<ConsumableRegistrationRequest> consumables;

        public Vehicle toEntity(UUID userId) {
            return Vehicle.builder()
                    .userId(userId)
                    .manufacturerKo(manufacturerKo)
                    .manufacturerEn(manufacturerEn)
                    .modelNameKo(modelNameKo)
                    .modelNameEn(modelNameEn)
                    .modelYear(modelYear)
                    .fuelType(fuelType)
                    .totalMileage(totalMileage)
                    .carNumber(carNumber)
                    .vin(vin)
                    .nickname(nickname)
                    .memo(memo)
                    .registrationSource(RegistrationSource.MANUAL)
                    .isPrimary(false)
                    .build();
        }
    }

    // 추가: 소모품 등록 요청 DTO
    @Getter
    @Setter
    @NoArgsConstructor
    public static class ConsumableRegistrationRequest {
        @NotBlank(message = "소모품 코드는 필수입니다.")
        private String code; // 예: ENGINE_OIL

        private java.time.LocalDate maintenanceDate; // 정비 날짜 (YYYY-MM-DD)
        private Double lastReplacedMileage; // 선택 입력

        // 하위 호환성 위해 유지 (필요 시)
        private java.time.LocalDateTime lastReplacedAt;
    }

    @Getter
    @Setter
    @NoArgsConstructor
    public static class ObdRegistrationRequest {
        @NotBlank(message = "VIN은 필수입니다.")
        private String vin;

        public Vehicle toEntity(UUID userId) {
            return Vehicle.builder()
                    .userId(userId)
                    .vin(vin)
                    .manufacturerKo("TBD") // API 승인 전까지 임시 값
                    .manufacturerEn("TBD")
                    .modelNameKo("TBD")
                    .modelNameEn("TBD")
                    .modelYear(0)
                    .registrationSource(RegistrationSource.OBD)
                    .isPrimary(false)
                    .build();
        }
    }

    @Getter
    @Setter
    public static class Response {
        private UUID vehicleId;
        private UUID userId;
        private String manufacturerKo;
        private String manufacturerEn;
        private String modelNameKo;
        private String modelNameEn;
        private Integer modelYear;
        private FuelType fuelType;
        private Double totalMileage;
        private String carNumber;
        private String nickname;
        private String memo;
        private String vin;
        private Boolean isPrimary;
        private String registrationSource;
        private Boolean cloudLinked; // 추가: 클라우드 연동 여부

        // 상세 제원 정보 (VehicleSpec 연동용)
        private Double length;
        private Double width;
        private Double height;
        private Integer displacement;
        private String engineType;
        private Double maxPower;
        private Double maxTorque;
        private String tireSizeFront;
        private String tireSizeRear;
        private Double officialFuelEconomy;

        public static Response from(Vehicle vehicle) {
            Response response = new Response();
            response.setVehicleId(vehicle.getVehicleId());
            response.setUserId(vehicle.getUserId());
            response.setManufacturerKo(vehicle.getManufacturerKo());
            response.setManufacturerEn(vehicle.getManufacturerEn());
            response.setModelNameKo(vehicle.getModelNameKo());
            response.setModelNameEn(vehicle.getModelNameEn());
            response.setModelYear(vehicle.getModelYear());
            response.setFuelType(vehicle.getFuelType());
            response.setTotalMileage(vehicle.getTotalMileage());
            response.setCarNumber(vehicle.getCarNumber());
            response.setNickname(vehicle.getNickname());
            response.setMemo(vehicle.getMemo());
            response.setVin(vehicle.getVin());
            response.setIsPrimary(vehicle.getIsPrimary());
            response.setRegistrationSource(
                    vehicle.getRegistrationSource() != null ? vehicle.getRegistrationSource().name() : null);
            response.setCloudLinked(vehicle.getCloudLinked()); // 클라우드 연동 여부 설정
            return response;
        }
    }
}
