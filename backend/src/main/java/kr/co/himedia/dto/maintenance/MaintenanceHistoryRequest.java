package kr.co.himedia.dto.maintenance;

import lombok.Getter;
import lombok.Setter;

import java.time.LocalDate;

@Getter
@Setter
public class MaintenanceHistoryRequest {
    private LocalDate maintenanceDate;
    private Double mileageAtMaintenance;
    private Long consumableItemId;
    private String consumableItemCode;
    private Boolean isStandardized;
    private String shopName;
    private Integer cost;
    private String ocrData;
    private String memo;
}
