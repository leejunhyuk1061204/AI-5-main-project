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
    /** 냉각수 wear_factor 상한 (극단 과열 시 무한 증가 방지) */
    public static final double COOLANT_MAX_FACTOR = 4.0;

    // ==================== 에어필터 (Air Filter) ====================
    /** 차량 모델별 기준 MAF (g/s) */
    public static final Map<String, Double> BASELINE_MAF = Map.of(
            // "Sonata 2.0", 18.0,
            // "Avante 1.6", 14.5,
            // "Grandeur 3.0", 22.0,
            // "Tucson 2.0", 19.0,
            "default", 18.0);
    public static final double AIR_FILTER_EFFICIENCY_BASE = 1.5;
    public static final double AIR_FILTER_EFFICIENCY_DIVISOR = 0.1;
    /** 에어필터 wear_factor 상한 (극단 효율 손실 시 무한 증가 방지) */
    public static final double AIR_FILTER_MAX_FACTOR = 3.0;

    // ==================== 브레이크패드 (Brake Pad) ====================
    public static final double BRAKE_ENERGY_DIVISOR = 10000.0;
    public static final double CITY_SPEED_THRESHOLD = 30.0; // km/h
    public static final double CITY_MULT = 1.3;
    /** 브레이크패드 wear_factor 상한 (급정동·고속 다수 시 무한 증가 방지) */
    public static final double BRAKE_PAD_MAX_FACTOR = 4.0;

    // ==================== 12V 배터리 (Battery) ====================
    public static final double BATTERY_LOW_VOLTAGE_THRESHOLD = 12.0; // V
    public static final double BATTERY_LOW_VOLTAGE_PENALTY = 1.4;
    public static final double BATTERY_SHORT_TRIP_THRESHOLD_KM = 5.0;
    public static final double BATTERY_SHORT_TRIP_PENALTY = 1.2;
    public static final double BATTERY_IDLE_PENALTY_COEF = 0.3;
    public static final double BATTERY_MAX_FACTOR = 2.0;

    // ==================== 미션 오일 (Transmission) ====================
    public static final double MISSION_OIL_TEMP_THRESHOLD = 90.0; // °C
    public static final double MISSION_OIL_LOAD_THRESHOLD = 80.0; // %
    public static final double MISSION_OIL_TEMP_PENALTY_COEF = 0.015; // per °C over threshold
    public static final double MISSION_OIL_LOAD_PENALTY_COEF = 0.008; // per % over threshold
    public static final double MISSION_OIL_MAX_FACTOR = 2.0;

    // ==================== 스파크 플러그 (Spark Plug) ====================
    public static final double SPARK_PLUG_RPM_PENALTY_COEF = 1.0;
    public static final double SPARK_PLUG_LOAD_PENALTY_COEF = 0.006;
    public static final double SPARK_PLUG_MAX_FACTOR = 2.2;

    // ==================== 임계값 (Thresholds) ====================
    public static final double HARD_ACCEL_THRESHOLD = 10.0; // km/h/s
    public static final double HARD_BRAKE_THRESHOLD = 10.0; // km/h/s

    // ==================== 유틸리티 메서드 ====================

    /**
     * 차량 모델에 맞는 기준 MAF 값을 반환합니다.
     *
     * @param vehicleModel 차량 모델명
     * @return 기준 MAF 값 (g/s). 모델을 찾을 수 없으면 기본값 18.0 반환
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
            case "TIRE_FL", "TIRE_FR", "TIRE_RL", "TIRE_RR" -> TIRE_CYCLE;
            case "BRAKE_PAD_FRONT", "BRAKE_PAD_REAR" -> BRAKE_PAD_CYCLE;
            default -> throw new IllegalArgumentException("알 수 없는 소모품 코드: " + itemCode);
        };
    }
}
