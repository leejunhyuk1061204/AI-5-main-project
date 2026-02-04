package kr.co.himedia.controller;

import jakarta.servlet.http.HttpServletRequest;

import kr.co.himedia.common.ApiResponse;
import kr.co.himedia.dto.payment.KakaoApproveResponse;
import kr.co.himedia.dto.payment.KakaoReadyResponse;
import kr.co.himedia.dto.payment.PaymentApproveRequest;
import kr.co.himedia.dto.payment.PaymentReadyRequest;
import kr.co.himedia.security.CustomUserDetails;
import kr.co.himedia.service.KakaoPayService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;

@RestController
@RequestMapping("/payment")
@RequiredArgsConstructor
public class PaymentController {

    private final KakaoPayService kakaoPayService;

    /**
     * 결제 준비 API 엔드포인트입니다.
     */
    @PostMapping("/ready")
    public ResponseEntity<ApiResponse<KakaoReadyResponse>> ready(
            @AuthenticationPrincipal CustomUserDetails userDetails,
            @RequestBody PaymentReadyRequest request,
            HttpServletRequest servletRequest) {

        // 현재 요청된 서버의 Base URL 동적 추출 (http://IP:PORT 형태)
        String baseUrl = servletRequest.getScheme() + "://" + servletRequest.getServerName() + ":"
                + servletRequest.getServerPort();

        KakaoReadyResponse response = kakaoPayService.ready(userDetails.getUserId().toString(), request, baseUrl);
        return ResponseEntity.ok(ApiResponse.success(response));
    }

    /**
     * 결제 승인 API 엔드포인트입니다.
     */
    /**
     * 결제 승인 API 엔드포인트입니다.
     */
    @PostMapping("/approve")
    public ResponseEntity<ApiResponse<KakaoApproveResponse>> approve(
            @AuthenticationPrincipal CustomUserDetails userDetails,
            @RequestBody PaymentApproveRequest request) {

        KakaoApproveResponse response = kakaoPayService.approve(userDetails.getUserId().toString(), request);
        return ResponseEntity.ok(ApiResponse.success(response));
    }

    /**
     * 멤버십을 FREE로 초기화(다운그레이드)하는 API 엔드포인트입니다.
     */
    @PostMapping("/reset")
    public ResponseEntity<ApiResponse<Void>> reset(@AuthenticationPrincipal CustomUserDetails userDetails) {
        kakaoPayService.resetMembership(userDetails.getUserId().toString());
        return ResponseEntity.ok(ApiResponse.success(null));
    }

    /**
     * 결제 성공 시 앱으로 리다이렉트하는 콜백 핸들러입니다.
     */
    /**
     * 결제 성공 시 앱의 딥링크로 리다이렉트합니다.
     */
    @GetMapping("/ready/success")
    public void readySuccess(
            @RequestParam("pg_token") String pgToken,
            @RequestParam("order_id") String orderId,
            HttpServletResponse response) throws IOException {

        try {
            // 백엔드에서 즉시 승인 처리 수행 (Front가 아닌 서버에서 직접 승인)
            kakaoPayService.approveByOrderId(orderId, pgToken);

            // 승인이 완료된 후 앱으로 리다이렉트
            String redirectUrl = "frontend://payment/success?order_id=" + orderId + "&status=success";
            response.sendRedirect(redirectUrl);
        } catch (Exception e) {
            response.sendRedirect("frontend://payment/fail?order_id=" + orderId + "&message=" + e.getMessage());
        }
    }

    @GetMapping("/ready/cancel")
    public void readyCancel(HttpServletResponse response) throws IOException {
        response.sendRedirect("frontend://payment/cancel");
    }

    @GetMapping("/ready/fail")
    public void readyFail(HttpServletResponse response) throws IOException {
        response.sendRedirect("frontend://payment/fail");
    }
}
