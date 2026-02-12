package kr.co.himedia.domain.consumable;

/**
 * 관리 대상 소모품 타입을 정의하는 열거형.
 * 5가지 소모품: 엔진오일, 에어필터, 냉각수, 타이어, 브레이크패드
 */
public enum ConsumableType {

    ENGINE_OIL("엔진오일", 10000),
    AIR_FILTER("에어필터", 15000),
    COOLANT("냉각수", 40000),
    TIRE("타이어", 50000),
    BRAKE_PAD("브레이크패드", 60000);

    private final String displayName;
    private final int replacementCycleKm;

    ConsumableType(String displayName, int replacementCycleKm) {
        this.displayName = displayName;
        this.replacementCycleKm = replacementCycleKm;
    }

    public String getDisplayName() {
        return displayName;
    }

    public int getReplacementCycleKm() {
        return replacementCycleKm;
    }

    /**
     * 소모품 코드 문자열로부터 ConsumableType을 조회합니다.
     *
     * @param code 소모품 코드 (예: "ENGINE_OIL")
     * @return 매칭되는 ConsumableType
     * @throws IllegalArgumentException 알 수 없는 코드인 경우
     */
    public static ConsumableType fromCode(String code) {
        for (ConsumableType type : values()) {
            if (type.name().equals(code)) {
                return type;
            }
        }
        throw new IllegalArgumentException("알 수 없는 소모품 코드: " + code);
    }
}
