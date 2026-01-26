package kr.co.himedia.common.exception;

import kr.co.himedia.common.ApiResponse;
import kr.co.himedia.common.exception.ErrorCode;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.HttpRequestMethodNotSupportedException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

/**
 * 전역 예외 처리기 클래스입니다.
 * 모든 컨트롤러에서 발생하는 예외를 가로채서 일관된 ApiResponse 형식으로 반환합니다.
 */
@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

        @ExceptionHandler(BaseException.class)
        protected ResponseEntity<ApiResponse<?>> handleBaseException(BaseException e) {
                log.error("BaseException: {}", e.getErrorCode().getMessage(), e);
                ErrorCode errorCode = e.getErrorCode();
                return ResponseEntity
                                .status((org.springframework.http.HttpStatusCode) errorCode.getStatus())
                                .body(ApiResponse.fail(errorCode.getCode(), e.getMessage()));
        }

        /**
         * @Valid 검증 실패 시 발생하는 예외 처리
         */
        @ExceptionHandler(MethodArgumentNotValidException.class)
        protected ResponseEntity<ApiResponse<?>> handleMethodArgumentNotValidException(
                        MethodArgumentNotValidException e) {
                log.error("MethodArgumentNotValidException", e);
                String message = e.getBindingResult().getAllErrors().get(0).getDefaultMessage();
                return ResponseEntity
                                .status((org.springframework.http.HttpStatusCode) ErrorCode.INVALID_INPUT_VALUE
                                                .getStatus())
                                .body(ApiResponse.fail(ErrorCode.INVALID_INPUT_VALUE.getCode(), message));
        }

        /**
         * 지원하지 않는 HTTP 메서드로 요청 시 발생하는 예외 처리
         */
        @ExceptionHandler(HttpRequestMethodNotSupportedException.class)
        protected ResponseEntity<ApiResponse<?>> handleHttpRequestMethodNotSupportedException(
                        HttpRequestMethodNotSupportedException e) {
                log.error("HttpRequestMethodNotSupportedException", e);
                return ResponseEntity
                                .status((org.springframework.http.HttpStatusCode) ErrorCode.METHOD_NOT_ALLOWED
                                                .getStatus())
                                .body(ApiResponse.fail(ErrorCode.METHOD_NOT_ALLOWED.getCode(),
                                                ErrorCode.METHOD_NOT_ALLOWED.getMessage()));
        }

        /**
         * 잘못된 리소스 경로 요청 시 발생하는 예외 처리 (404)
         */
        @ExceptionHandler(org.springframework.web.servlet.resource.NoResourceFoundException.class)
        protected ResponseEntity<ApiResponse<?>> handleNoResourceFoundException(
                        org.springframework.web.servlet.resource.NoResourceFoundException e) {
                log.error("NoResourceFoundException: {}", e.getMessage());
                return ResponseEntity
                                .status(org.springframework.http.HttpStatus.NOT_FOUND)
                                .body(ApiResponse.fail("COMMON_002", "Resource not found: " + e.getResourcePath()));
        }

        /**
         * 기타 모든 예외 처리
         */
        @ExceptionHandler(Exception.class)
        protected ResponseEntity<ApiResponse<?>> handleException(Exception e) {
                log.error("Unhandled Exception", e);
                return ResponseEntity
                                .status((org.springframework.http.HttpStatusCode) ErrorCode.INTERNAL_SERVER_ERROR
                                                .getStatus())
                                .body(ApiResponse.fail(ErrorCode.INTERNAL_SERVER_ERROR.getCode(),
                                                e.getMessage() != null ? e.getMessage()
                                                                : "Unknown Internal Server Error"));
        }
}
