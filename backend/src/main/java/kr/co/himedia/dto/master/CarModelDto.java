package kr.co.himedia.dto.master;

import lombok.AllArgsConstructor;
import lombok.Getter;

@Getter
@AllArgsConstructor
public class CarModelDto {
    private String modelName;
    private Integer modelYear;
    private String fuelType;
}
