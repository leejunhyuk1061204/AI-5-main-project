package kr.co.himedia.dto.maintenance;

import lombok.*;

import java.time.LocalDate;

@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class OcrAnalysisResponse {
    private LocalDate maintenanceDate;
    private Double mileageAtMaintenance;
    private String shopName;
    private Integer cost;

    // Receipt Type
    private String receiptType; // "MAINTENANCE" or "FUELING"

    // Maintenance Specific
    private String consumableItemCode;
    private String consumableItemName;

    // Fueling Specific
    private String fuelType;
    private Integer unitPrice;
    private Double fuelAmount;

    private String ocrText;
    private String ocrData;
}
