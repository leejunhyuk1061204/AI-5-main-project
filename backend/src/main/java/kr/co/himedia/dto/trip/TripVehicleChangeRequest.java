package kr.co.himedia.dto.trip;

import jakarta.validation.constraints.NotNull;
import lombok.Getter;
import lombok.Setter;

import java.util.UUID;

@Getter
@Setter
public class TripVehicleChangeRequest {
    @NotNull(message = "newVehicleId는 필수입니다.")
    private UUID newVehicleId;
}
