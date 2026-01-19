package kr.co.himedia.dto.maintenance;

import kr.co.himedia.entity.MaintenanceHistory;
import kr.co.himedia.entity.MaintenanceItem;
import lombok.Getter;

import java.time.LocalDate;
import java.util.UUID;

@Getter
public class MaintenanceHistoryResponse {
    private UUID id;
    private LocalDate maintenanceDate;
    private Double mileageAtMaintenance;
    private MaintenanceItem item;
    private String itemDescription;
    private Boolean isStandardized;
    private String shopName;
    private Integer cost;
    private String ocrData;
    private String memo;

    public MaintenanceHistoryResponse(MaintenanceHistory history) {
        this.id = history.getId();
        this.maintenanceDate = history.getMaintenanceDate();
        this.mileageAtMaintenance = history.getMileageAtMaintenance();
        this.item = MaintenanceItem.valueOf(history.getConsumableItem().getCode());
        this.itemDescription = history.getConsumableItem().getName();
        this.isStandardized = history.getIsStandardized();
        this.shopName = history.getShopName();
        this.cost = history.getCost();
        this.ocrData = history.getOcrData();
        this.memo = history.getMemo();
    }
}
