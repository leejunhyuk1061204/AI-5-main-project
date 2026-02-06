package kr.co.himedia.dto.maintenance;

import kr.co.himedia.entity.FuelType;
import kr.co.himedia.entity.FuelingHistory;
import lombok.Getter;

import java.time.LocalDate;
import java.util.UUID;

@Getter
public class FuelingHistoryResponse {
    private UUID id;
    private LocalDate fuelingDate;
    private Double mileageAtFueling;
    private FuelType fuelType;
    private Double amount;
    private Integer unitPrice;
    private Integer totalCost;
    private String shopName;
    private String stationName;
    private String memo;
    private UUID receiptId;

    public FuelingHistoryResponse(FuelingHistory history) {
        this.id = history.getId();
        this.fuelingDate = history.getFuelingDate();
        this.mileageAtFueling = history.getMileageAtFueling();
        this.fuelType = history.getFuelType();
        this.amount = history.getAmount();
        this.unitPrice = history.getUnitPrice();
        this.totalCost = history.getTotalCost();
        this.shopName = history.getShopName();
        this.stationName = history.getStationName();
        this.memo = history.getMemo();
        this.receiptId = history.getReceiptId();
    }
}
