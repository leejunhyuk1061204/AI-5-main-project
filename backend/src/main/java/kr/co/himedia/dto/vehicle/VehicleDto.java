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
    }

    @Getter
    @Setter
    @NoArgsConstructor
    public static class RegistrationRequest {
        @NotBlank(message = "제조사는 필수입니다.")
        private String manufacturer;

        @NotBlank(message = "모델명은 필수입니다.")
        private String modelName;

        @NotNull(message = "연식은 필수입니다.")
        private Integer modelYear;

        @NotNull(message = "유종은 필수입니다.")
        private FuelType fuelType;

        @Min(value = 0, message = "주행거리는 0 이상이어야 합니다.")
        private Double totalMileage;

        private String nickname;
        private String memo;
        private String carNumber;
        private String obdDeviceId;

        public Vehicle toEntity(UUID userId) {
            return Vehicle.builder()
                    .userId(userId)
                    .manufacturer(manufacturer)
                    .modelName(modelName)
                    .modelYear(modelYear)
                    .fuelType(fuelType)
                    .totalMileage(totalMileage)
                    .carNumber(carNumber)
                    .nickname(nickname)
                    .memo(memo)
                    .registrationSource(RegistrationSource.MANUAL)
                    .isPrimary(false)
                    .obdDeviceId(obdDeviceId)
                    .build();
        }
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
                    .manufacturer("Unknown") // API 승인 전까지 임시 값
                    .modelName("Unknown")
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
        private String manufacturer;
        private String modelName;
        private Integer modelYear;
        private FuelType fuelType;
        private Double totalMileage;
        private String carNumber;
        private String nickname;
        private String memo;
        private Boolean isPrimary;
        private String registrationSource;
        private String obdDeviceId;

        public static Response from(Vehicle vehicle) {
            Response response = new Response();
            response.setVehicleId(vehicle.getVehicleId());
            response.setUserId(vehicle.getUserId());
            response.setManufacturer(vehicle.getManufacturer());
            response.setModelName(vehicle.getModelName());
            response.setModelYear(vehicle.getModelYear());
            response.setFuelType(vehicle.getFuelType());
            response.setTotalMileage(vehicle.getTotalMileage());
            response.setCarNumber(vehicle.getCarNumber());
            response.setNickname(vehicle.getNickname());
            response.setMemo(vehicle.getMemo());
            response.setIsPrimary(vehicle.getIsPrimary());
            response.setRegistrationSource(vehicle.getRegistrationSource().name());
            response.setObdDeviceId(vehicle.getObdDeviceId());
            return response;
        }
    }
}
