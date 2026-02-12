package kr.co.himedia.common.constants;

import java.util.Map;

/**
 * 소모품 마모 진단에 필요한 모든 상수를 정의하는 클래스.
 * AI 서버의 Python 규칙 기반 공식과 동일한 상수를 사용합니다.
 */
public final class ConsumableConstants {

    private ConsumableConstants() {
        // 인스턴스 생성 방지
    }

    // ==================== 교체 주기 (km) ====================
    public static final int ENGINE_OIL_CYCLE = 10000;
    public static final int AIR_FILTER_CYCLE = 15000;
    public static final int COOLANT_CYCLE = 40000;
    public static final int TIRE_CYCLE = 50000;
    public static final int BRAKE_PAD_CYCLE = 60000;

    // ==================== 타이어 (Tire) ====================
    public static final double TIRE_ACCEL_BRAKE_COEF = 0.03;
    public static final double TIRE_MAX_FACTOR = 3.0;

    // ==================== 엔진오일 (Engine Oil) ====================
    public static final double COLD_START_THRESHOLD_KM = 5.0;
    public static final double COLD_START_PENALTY = 1.5;
    public static final double RPM_PENALTY_COEF = 0.8;
    public static final double IDLE_PENALTY_COEF = 0.5;
    public static final double ENGINE_OIL_MAX_FACTOR = 2.5;
    public static final int HIGH_RPM_THRESHOLD = 3000;

    // ==================== 냉각수 (Coolant) ====================
    public static final double COOLANT_NORMAL_TEMP = 90.0; // °C
    public static final double COOLANT_OVERHEAT_THRESHOLD = 95.0; // °C - 과열 판단 기준
    public static final double COOLANT_ARRHENIUS_BASE = 2.0;
    public static final double COOLANT_TEMP_DIVISOR = 10.0;

    // ==================== 에어필터 (Air Filter) ====================
    /** 차량 모델별 기준 MAF (g/s) */
    public static final Map<String, Double> BASELINE_MAF = Map.of(
            "Sonata 2.0", 18.0,
            "Avante 1.6", 14.5,
            "Grandeur 3.0", 22.0,
            "Tucson 2.0", 19.0,
            "default", 16.0);
    public static final double AIR_FILTER_EFFICIENCY_BASE = 1.5;
    public static final double AIR_FILTER_EFFICIENCY_DIVISOR = 0.1;

    // ==================== 브레이크패드 (Brake Pad) ====================
    public static final double BRAKE_ENERGY_DIVISOR = 10000.0;
    public static final double CITY_SPEED_THRESHOLD = 30.0; // km/h
    public static final double CITY_MULT = 1.3;

    // ==================== 임계값 (Thresholds) ====================
    public static final double HARD_ACCEL_THRESHOLD = 10.0; // km/h/s
    public static final double HARD_BRAKE_THRESHOLD = 10.0; // km/h/s

    // ==================== 신뢰도 맵 (Confidence) ====================
    public static final Map<String, Double> CONFIDENCE_MAP = Map.of(
            "AIR_FILTER", 0.89,
            "COOLANT", 0.95,
            "TIRE", 0.82,
            "BRAKE_PAD", 0.78,
            "ENGINE_OIL", 0.71);

    // ==================== 유틸리티 메서드 ====================

    /**
     * 차량 모델에 맞는 기준 MAF 값을 반환합니다.
     *
     * @param vehicleModel 차량 모델명
     * @return 기준 MAF 값 (g/s). 모델을 찾을 수 없으면 기본값 16.0 반환
     */
    public static Double getBaselineMaf(String vehicleModel) {
        if (vehicleModel == null) {
            return BASELINE_MAF.get("default");
        }
        return BASELINE_MAF.getOrDefault(vehicleModel, BASELINE_MAF.get("default"));
    }

    /**
     * 소모품 코드에 해당하는 교체 주기(km)를 반환합니다.
     *
     * @param itemCode 소모품 코드 (예: "ENGINE_OIL", "TIRE")
     * @return 교체 주기 (km)
     * @throws IllegalArgumentException 알 수 없는 소모품 코드인 경우
     */
    public static int getReplacementCycle(String itemCode) {
        return switch (itemCode) {
            case "ENGINE_OIL" -> ENGINE_OIL_CYCLE;
            case "AIR_FILTER" -> AIR_FILTER_CYCLE;
            case "COOLANT" -> COOLANT_CYCLE;
            case "TIRE" -> TIRE_CYCLE;
            case "BRAKE_PAD" -> BRAKE_PAD_CYCLE;
            default -> throw new IllegalArgumentException("알 수 없는 소모품 코드: " + itemCode);
        };
    }

    /**
     * 소모품 코드에 해당하는 신뢰도 값을 반환합니다.
     *
     * @param itemCode 소모품 코드 (예: "ENGINE_OIL", "TIRE")
     * @return 신뢰도 값 (0.0 ~ 1.0). 코드를 찾을 수 없으면 0.5 반환
     */
    public static double getConfidence(String itemCode) {
        return CONFIDENCE_MAP.getOrDefault(itemCode, 0.5);
    }
}
