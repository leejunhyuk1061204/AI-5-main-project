package kr.co.himedia.entity;

import lombok.Getter;
import lombok.RequiredArgsConstructor;

@Getter
@RequiredArgsConstructor
public enum MaintenanceItem {
    ENGINE_OIL("엔진오일"),
    TIRE("타이어 (일반)"),
    TIRE_FRONT("앞 타이어"),
    TIRE_REAR("뒤 타이어"),
    BRAKE_PAD("브레이크 패드 (일반)"),
    BRAKE_PAD_FRONT("앞 브레이크 패드"),
    BRAKE_PAD_REAR("뒤 브레이크 패드"),
    BRAKE_FLUID("브레이크 오일"),
    COOLANT("냉각수"),
    AIR_CON_FILTER("에어컨 필터"),
    WIPER("와이퍼"),
    BATTERY("배터리 (일반)"),
    BATTERY_12V("12V 배터리"),
    MISSION_OIL("미션 오일"),
    OTHER("기타");

    private final String description;
}
