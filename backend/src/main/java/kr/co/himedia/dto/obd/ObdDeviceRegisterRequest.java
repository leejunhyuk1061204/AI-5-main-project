package kr.co.himedia.dto.obd;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
public class ObdDeviceRegisterRequest {
    @NotBlank
    private String deviceId;
    @NotBlank
    private String deviceType; // "ble" | "classic"
    private String name;
}
