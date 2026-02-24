package kr.co.himedia.dto.trip;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class TripObdLogDto {
    private String timestamp;
    private Double rpm;
    private Double speed;
    private Double voltage;
    private Double coolantTemp;
    private Double engineLoad;
    private Double fuelTrimShort;
    private Double fuelTrimLong;
    private Double throttlePos;
    private Double map;
    private Double maf;
    private Double intakeTemp;
    private Integer engineRuntime;
}
