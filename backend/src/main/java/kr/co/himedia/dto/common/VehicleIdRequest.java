package kr.co.himedia.dto.common;

import java.util.UUID;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import jakarta.validation.constraints.NotNull;

@Getter
@Setter
@NoArgsConstructor
public class VehicleIdRequest {
    @NotNull(message = "vehicleId는 필수입니다.")
    private UUID vehicleId;
}
