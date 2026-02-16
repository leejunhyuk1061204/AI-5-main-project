package kr.co.himedia.dto.maintenance;

import jakarta.validation.constraints.NotNull;
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
    @NotNull(message = "총 결제금액은 필수입니다")
    private Integer totalCost;
    private String shopName;
    private String memo;
    private UUID receiptId;
}
