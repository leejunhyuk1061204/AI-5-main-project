package kr.co.himedia.dto.cloud;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

/**
 * 클라우드 서비스(하이모빌리티 등)에서 조회한 차량 정보를 담는 응답 DTO
 */
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class CloudVehicleResponse {

    /**
     * 클라우드 서비스 내부 차량 ID (하이모빌리티의 vehicle_id)
     */
    private String providerVehicleId;

    /**
     * 차량 고유 식별 번호 (Vehicle Identification Number)
     */
    private String vin;

    /**
     * 제조사 (예: BMW, Mercedes-Benz)
     */
    private String brand;

    /**
     * 모델명 (예: 530i, E-Class)
     */
    private String model;

    /**
     * 연식
     */
    private Integer year;

    /**
     * 현재 주행거리 (km)
     */
    private Double mileage;
}
