package kr.co.himedia.dto.maintenance;

import lombok.Builder;
import lombok.Getter;

import java.time.LocalDate;

@Getter
@Builder
public class ConsumableStatusResponse {
    private String itemCode; // DB 코드 (예: ENGINE_OIL)
    private String itemDescription; // DB 이름 (예: 엔진오일)
    private Long consumableItemId;
    private double remainingLifePercent;
    private LocalDate lastMaintenanceDate;
    private double lastMaintenanceMileage;
    private Double replacementIntervalMileage;
    private Integer replacementIntervalMonths;
    private LocalDate predictedReplacementDate;
}
