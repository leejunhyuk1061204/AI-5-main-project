package kr.co.himedia.dto.maintenance;

import kr.co.himedia.entity.MaintenanceItem;
import lombok.Builder;
import lombok.Getter;

import java.time.LocalDate;

@Getter
@Builder
public class ConsumableStatusResponse {
    private MaintenanceItem item;
    private String itemDescription;
    private double remainingLifePercent;
    private LocalDate lastMaintenanceDate;
    private double lastMaintenanceMileage;
    private Double replacementIntervalMileage;
    private Integer replacementIntervalMonths;
    private LocalDate predictedReplacementDate;
}
