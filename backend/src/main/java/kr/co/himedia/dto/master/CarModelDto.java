package kr.co.himedia.dto.master;

import lombok.AllArgsConstructor;
import lombok.Getter;

@Getter
@AllArgsConstructor
public class CarModelDto {
    private String modelName; // Backward compatibility (maps to Ko)
    private String modelNameKo;
    private String modelNameEn;
    private String manufacturerKo;
    private String manufacturerEn;
    private Integer modelYear;
    private String fuelType;

    // Constructor for projection
    public CarModelDto(String modelNameKo, String modelNameEn, String manufacturerKo, String manufacturerEn,
            Integer modelYear, String fuelType) {
        this.modelName = modelNameKo;
        this.modelNameKo = modelNameKo;
        this.modelNameEn = modelNameEn;
        this.manufacturerKo = manufacturerKo;
        this.manufacturerEn = manufacturerEn;
        this.modelYear = modelYear;
        this.fuelType = fuelType;
    }
}
