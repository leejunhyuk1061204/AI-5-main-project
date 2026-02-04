package kr.co.himedia.dto.cloud;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.util.UUID;

/**
 * 차량의 VIN 정보를 업데이트하기 위한 요청 DTO
 */
@Getter
@Setter
@NoArgsConstructor
public class VinUpdateRequest {

    /**
     * 우리 시스템의 차량 ID
     */
    @NotNull(message = "차량 ID는 필수입니다.")
    private UUID vehicleId;

    /**
     * 업데이트할 VIN 번호
     */
    @NotBlank(message = "VIN은 필수입니다.")
    private String vin;
}
