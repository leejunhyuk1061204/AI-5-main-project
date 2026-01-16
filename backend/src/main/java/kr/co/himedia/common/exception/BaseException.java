package kr.co.himedia.common.exception;

import lombok.Getter;

/**
 * 프로젝트 내 모든 커스텀 예외의 부모 클래스입니다.
 */
@Getter
public class BaseException extends RuntimeException {

    private final ErrorCode errorCode;

    public BaseException(ErrorCode errorCode) {
        super(errorCode.getMessage());
        this.errorCode = errorCode;
    }

    public BaseException(ErrorCode errorCode, String message) {
        super(message);
        this.errorCode = errorCode;
    }
}
