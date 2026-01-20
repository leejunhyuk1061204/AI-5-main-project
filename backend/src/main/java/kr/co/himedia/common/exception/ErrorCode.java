package kr.co.himedia.common.exception;

import lombok.Getter;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;

/**
 * 에러 코드와 메시지를 관리하는 Enum 클래스입니다.
 */
@Getter
@RequiredArgsConstructor
public enum ErrorCode {

    // Common
    INVALID_INPUT_VALUE(HttpStatus.BAD_REQUEST, "COMMON_001", "잘못된 입력값입니다."),
    METHOD_NOT_ALLOWED(HttpStatus.METHOD_NOT_ALLOWED, "COMMON_002", "허용되지 않은 메서드 호출입니다."),
    INTERNAL_SERVER_ERROR(HttpStatus.INTERNAL_SERVER_ERROR, "COMMON_003", "서버 내부 오류가 발생했습니다."),
    ENTITY_NOT_FOUND(HttpStatus.NOT_FOUND, "COMMON_004", "해당 리소스를 찾을 수 없습니다."),

    // Auth & User
    UNAUTHORIZED(HttpStatus.UNAUTHORIZED, "AUTH_001", "인증되지 않은 사용자입니다."),
    ACCESS_DENIED(HttpStatus.FORBIDDEN, "AUTH_002", "접근 권한이 없습니다."),
    INVALID_CREDENTIALS(HttpStatus.UNAUTHORIZED, "AUTH_003", "이메일 또는 비밀번호가 올바르지 않습니다."),
    EMAIL_ALREADY_EXISTS(HttpStatus.CONFLICT, "AUTH_004", "이미 사용 중인 이메일입니다."),
    USER_NOT_FOUND(HttpStatus.NOT_FOUND, "AUTH_005", "사용자를 찾을 수 없습니다."),
    INVALID_REFRESH_TOKEN(HttpStatus.UNAUTHORIZED, "AUTH_006", "유효하지 않은 리프레시 토큰입니다."),
    REFRESH_TOKEN_EXPIRED(HttpStatus.UNAUTHORIZED, "AUTH_007", "리프레시 토큰이 만료되었습니다."),

    // Vehicle
    VEHICLE_NOT_FOUND(HttpStatus.NOT_FOUND, "VEH_001", "해당 차량을 찾을 수 없습니다."),
    DUPLICATE_VIN(HttpStatus.CONFLICT, "VEH_002", "이미 등록된 차대번호(VIN)입니다."),

    // Trip
    TRIP_NOT_FOUND(HttpStatus.NOT_FOUND, "TRP_001", "해당 주행 기록을 찾을 수 없습니다."),

    // Maintenance
    MAINTENANCE_NOT_FOUND(HttpStatus.NOT_FOUND, "MNT_001", "해당 정비 내역을 찾을 수 없습니다."),
    UNSUPPORTED_MAINTENANCE_ITEM(HttpStatus.BAD_REQUEST, "MNT_002", "지원하지 않는 정비 항목입니다."),

    // Diagnosis
    INSUFFICIENT_DATA(HttpStatus.BAD_REQUEST, "DIAG_001", "진단을 위한 데이터가 부족합니다.");

    private final HttpStatus status;
    private final String code;
    private final String message;
}
