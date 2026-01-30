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
    private String consumableItemCode;
    private String consumableItemName;
    private String ocrText;
    private String ocrData;
}
