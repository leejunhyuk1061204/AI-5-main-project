package kr.co.himedia.dto.master;

import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor
@AllArgsConstructor
public class ConsumableItemDto {
    private Long id;
    private String code;
    private String name;
    private String description;
    private Integer defaultIntervalMileage;
    private Integer defaultIntervalMonths;
}
