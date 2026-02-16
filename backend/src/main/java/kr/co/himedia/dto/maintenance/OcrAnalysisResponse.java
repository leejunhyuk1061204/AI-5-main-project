package kr.co.himedia.dto.maintenance;

import lombok.*;

import java.time.LocalDate;
import java.util.List;

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

    // Maintenance Specific (단일 품목, items 없을 때 사용)
    private String consumableItemCode;
    private String consumableItemName;
    /** 수량 (영수증에 "2개" 등 표기 시, 없으면 null → 1로 처리) */
    private Integer quantity;

    /** 정비 품목 목록 (LLM이 여러 품목 반환 시) */
    private List<MaintenanceLineItemDto> items;

    // Fueling Specific
    private String fuelType;
    private Integer unitPrice;
    private Double fuelAmount;

    private String ocrText;
    private String ocrData;
}
