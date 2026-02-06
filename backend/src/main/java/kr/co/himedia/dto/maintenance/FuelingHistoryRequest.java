package kr.co.himedia.dto.maintenance;

import kr.co.himedia.entity.FuelType;
import lombok.*;

import java.time.LocalDate;
import java.util.UUID;

@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class FuelingHistoryRequest {
    private LocalDate fuelingDate;
    private Double mileageAtFueling;
    private FuelType fuelType;
    private Double amount;
    private Integer unitPrice;
    private Integer totalCost;
    private String shopName;
    private String memo;
    private UUID receiptId;
}
