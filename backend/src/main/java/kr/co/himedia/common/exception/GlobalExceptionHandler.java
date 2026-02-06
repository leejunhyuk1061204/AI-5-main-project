package kr.co.himedia.common.exception;

import kr.co.himedia.common.ApiResponse;
import kr.co.himedia.common.exception.ErrorCode;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
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
                java.util.List<org.springframework.validation.FieldError> fieldErrors = e.getBindingResult()
                                .getFieldErrors();
                String message = fieldErrors.stream()
                                .map(error -> String.format("%s: %s", error.getField(), error.getDefaultMessage()))
                                .collect(java.util.stream.Collectors.joining(", "));

                if (message.isEmpty()) {
                        message = e.getBindingResult().getAllErrors().get(0).getDefaultMessage();
                }

                return ResponseEntity
                                .status(HttpStatus.BAD_REQUEST)
                                .body(ApiResponse.fail("COMMON_001", "입력 오류 - " + message));
        }

        @ExceptionHandler(org.springframework.validation.BindException.class)
        protected ResponseEntity<ApiResponse<?>> handleBindException(org.springframework.validation.BindException e) {
                log.error("BindException", e);
                String details = e.getBindingResult().getFieldErrors().stream()
                                .map(error -> error.getField() + ": " + error.getDefaultMessage())
                                .collect(java.util.stream.Collectors.joining(", "));
                return ResponseEntity
                                .status(HttpStatus.BAD_REQUEST)
                                .body(ApiResponse.fail("COMMON_001", "바인딩 오류 - " + details));
        }

        @ExceptionHandler(org.springframework.http.converter.HttpMessageNotReadableException.class)
        protected ResponseEntity<ApiResponse<?>> handleHttpMessageNotReadableException(
                        org.springframework.http.converter.HttpMessageNotReadableException e) {
                log.error("HttpMessageNotReadableException", e);
                return ResponseEntity
                                .status(HttpStatus.BAD_REQUEST)
                                .body(ApiResponse.fail("COMMON_001", "JSON 파싱 오류: " + e.getMessage()));
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
