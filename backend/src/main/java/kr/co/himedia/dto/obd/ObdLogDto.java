package kr.co.himedia.dto.obd;

import java.time.LocalDateTime;
import java.util.UUID;
import lombok.Getter;
import lombok.Setter;
import lombok.ToString;

@Getter
@Setter
@ToString
public class ObdLogDto {
    private LocalDateTime timestamp;
    private UUID vehicleId;
    private Double rpm;
    private Double speed;
    private Double voltage;
    private Double coolantTemp;
    private Double engineLoad;
    private Double fuelTrimShort;
    private Double fuelTrimLong;
}
