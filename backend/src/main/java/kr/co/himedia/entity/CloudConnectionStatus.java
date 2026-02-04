package kr.co.himedia.entity;

/**
 * 클라우드 계정 연동 상태를 나타내는 열거형
 */
public enum CloudConnectionStatus {
    /**
     * 정상 연동 상태
     */
    CONNECTED,

    /**
     * 토큰 만료로 재연동 필요
     */
    EXPIRED,

    /**
     * 사용자가 수동으로 연동 해제 (기본값)
     */
    DISCONNECTED
}
