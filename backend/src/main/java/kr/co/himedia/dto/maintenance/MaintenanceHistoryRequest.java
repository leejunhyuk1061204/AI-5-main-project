package kr.co.himedia.dto.maintenance;

import kr.co.himedia.entity.MaintenanceItem;
import lombok.Getter;
import lombok.Setter;

import java.time.LocalDate;

@Getter
@Setter
public class MaintenanceHistoryRequest {
    private LocalDate maintenanceDate;
    private Double mileageAtMaintenance;
    private MaintenanceItem item;
    private Integer cost;
    private String memo;
}
