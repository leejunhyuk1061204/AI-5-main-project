package kr.co.himedia.controller;

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

    @PostMapping("/ready")
    public ResponseEntity<ApiResponse<KakaoReadyResponse>> ready(
            @AuthenticationPrincipal CustomUserDetails userDetails,
            @RequestBody PaymentReadyRequest request) {

        KakaoReadyResponse response = kakaoPayService.ready(userDetails.getUserId().toString(), request);
        return ResponseEntity.ok(ApiResponse.success(response));
    }

    @PostMapping("/approve")
    public ResponseEntity<ApiResponse<KakaoApproveResponse>> approve(
            @AuthenticationPrincipal CustomUserDetails userDetails,
            @RequestBody PaymentApproveRequest request) {

        KakaoApproveResponse response = kakaoPayService.approve(userDetails.getUserId().toString(), request);
        return ResponseEntity.ok(ApiResponse.success(response));
    }

    @GetMapping("/ready/success")
    public void readySuccess(
            @RequestParam("pg_token") String pgToken,
            @RequestParam("order_id") String orderId,
            HttpServletResponse response) throws IOException {

        // 앱의 딥링크 주소로 리다이렉트 (pg_token은 넘기고 orderId는 AsyncStorage에 있으나 만일을 위해 파라미터로도 전달
        // 가능)
        String redirectUrl = "frontend://payment/success?pg_token=" + pgToken + "&order_id=" + orderId;
        response.sendRedirect(redirectUrl);
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
