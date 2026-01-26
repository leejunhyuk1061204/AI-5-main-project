package kr.co.himedia.entity;

/**
 * 전기차 충전 상태를 나타내는 Enum
 */
public enum ChargingStatus {
    DISCONNECTED, // 충전기 연결 안됨
    CHARGING, // 충전 중
    FULL, // 완충
    ERROR // 충전 오류
}
