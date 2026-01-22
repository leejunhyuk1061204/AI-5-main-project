package kr.co.himedia.dto.cloud;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import kr.co.himedia.entity.CloudProvider;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

/**
 * 사용자가 선택한 클라우드 차량을 등록하기 위한 요청 DTO
 */
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
public class CloudVehicleRegisterRequest {

    /**
     * 클라우드 서비스 내부 차량 ID (하이모빌리티의 vehicle_id)
     */
    @NotBlank(message = "차량 ID는 필수입니다.")
    private String providerVehicleId;

    /**
     * 클라우드 제공자 (HIGH_MOBILITY, SMARTCAR 등)
     */
    @NotNull(message = "클라우드 제공자는 필수입니다.")
    private CloudProvider cloudProvider;
}
