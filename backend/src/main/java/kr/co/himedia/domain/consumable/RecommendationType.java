package kr.co.himedia.domain.consumable;

/**
 * 소모품 마모 상태에 따른 권장 조치를 정의하는 열거형.
 * wearFactor 값에 따라 3단계로 분류합니다.
 */
public enum RecommendationType {

    OK("정상", "교체 필요 없음"),
    MONITOR("주의", "정기적 점검 필요"),
    REPLACE("교체 필요", "즉시 교체 권장");

    private final String displayName;
    private final String description;

    RecommendationType(String displayName, String description) {
        this.displayName = displayName;
        this.description = description;
    }

    public String getDisplayName() {
        return displayName;
    }

    public String getDescription() {
        return description;
    }

    /**
     * 마모 계수(wearFactor) 값에 따른 권장 조치를 반환합니다.
     * <ul>
     * <li>wearFactor < 0.5 → OK (정상)</li>
     * <li>wearFactor < 0.8 → MONITOR (주의)</li>
     * <li>wearFactor >= 0.8 → REPLACE (교체 필요)</li>
     * </ul>
     *
     * @param wearFactor 마모 계수 (0.0 ~ 1.0)
     * @return 권장 조치 타입
     */
    public static RecommendationType fromWearFactor(double wearFactor) {
        if (wearFactor < 0.5) {
            return OK;
        } else if (wearFactor < 0.8) {
            return MONITOR;
        } else {
            return REPLACE;
        }
    }
}
