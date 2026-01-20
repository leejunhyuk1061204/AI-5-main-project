package kr.co.himedia.dto.trip;

import java.util.UUID;
import lombok.Getter;
import lombok.Setter;
import jakarta.validation.constraints.NotNull;

@Getter
@Setter
public class TripStartRequest {
    @NotNull(message = "vehicleId는 필수입니다.")
    private UUID vehicleId;
}
