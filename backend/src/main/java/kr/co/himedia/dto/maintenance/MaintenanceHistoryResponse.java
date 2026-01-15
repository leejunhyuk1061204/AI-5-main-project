package kr.co.himedia.dto.maintenance;

import kr.co.himedia.entity.MaintenanceHistory;
import kr.co.himedia.entity.MaintenanceItem;
import lombok.Getter;

import java.time.LocalDate;

@Getter
public class MaintenanceHistoryResponse {
    private Long id;
    private LocalDate maintenanceDate;
    private Double mileageAtMaintenance;
    private MaintenanceItem item;
    private String itemDescription;
    private Integer cost;
    private String memo;

    public MaintenanceHistoryResponse(MaintenanceHistory history) {
        this.id = history.getId();
        this.maintenanceDate = history.getMaintenanceDate();
        this.mileageAtMaintenance = history.getMileageAtMaintenance();
        this.item = history.getItem();
        this.itemDescription = history.getItem().getDescription();
        this.cost = history.getCost();
        this.memo = history.getMemo();
    }
}
