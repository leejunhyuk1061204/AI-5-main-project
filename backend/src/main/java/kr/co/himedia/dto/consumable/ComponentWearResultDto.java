package kr.co.himedia.dto.consumable;

import kr.co.himedia.domain.consumable.RecommendationType;
import lombok.Builder;
import lombok.Data;

/**
 * 개별 소모품의 마모 진단 결과를 담는 DTO.
 * 규칙 기반 계산 결과를 클라이언트에 반환할 때 사용합니다.
 */
@Data
@Builder
public class ComponentWearResultDto {

    /** 마모 계수 (0.0 ~ 1.0) */
    private Double wearFactor;

    /** 예측 신뢰도 (0.0 ~ 1.0) */
    private Double confidence;

    /** 예측 잔여 주행거리 (km) */
    private Integer predictedRemainingKm;

    /** 권장 조치 (OK / MONITOR / REPLACE) */
    private RecommendationType recommendation;

    /** 상세 사유 코드 (예: "HIGH_WEAR", "NORMAL") */
    private String reasonCode;
}
