package kr.co.himedia.dto.maintenance;

import lombok.*;

@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class MaintenanceLineItemDto {
    private String consumableItemCode;
    private String consumableItemName;
    private Integer quantity;
    private Integer amount;
    private String description;
}
