package kr.co.himedia.service;

import kr.co.himedia.dto.payment.KakaoApproveResponse;
import kr.co.himedia.dto.payment.KakaoReadyResponse;
import kr.co.himedia.dto.payment.PaymentApproveRequest;
import kr.co.himedia.dto.payment.PaymentReadyRequest;
import kr.co.himedia.entity.Payment;
import kr.co.himedia.entity.User;
import kr.co.himedia.entity.UserLevel;
import kr.co.himedia.repository.PaymentRepository;
import kr.co.himedia.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.client.RestTemplate;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

@Service
@RequiredArgsConstructor
@Slf4j
public class KakaoPayService {

    private final PaymentRepository paymentRepository;
    private final UserRepository userRepository;
    private final RestTemplate restTemplate = new RestTemplate();

    @Value("${kakao.pay.secret-key}")
    private String kakaoSecretKey;

    @Value("${app.backend-url}")
    private String backendUrl;

    private static final String KAKAO_PAY_HOST = "https://open-api.kakaopay.com/online/v1/payment";
    private static final String CID = "TC0ONETIME"; // 테스트용 CID

    @Transactional
    public KakaoReadyResponse ready(String userId, PaymentReadyRequest request) {
        User user = userRepository.findById(UUID.fromString(userId))
                .orElseThrow(() -> new IllegalArgumentException("User not found"));

        // 주문 번호 생성
        String orderId = UUID.randomUUID().toString();

        // 카카오페이 요청 본문
        Map<String, String> parameters = new HashMap<>();
        parameters.put("cid", CID);
        parameters.put("partner_order_id", orderId);
        parameters.put("partner_user_id", userId);
        parameters.put("item_name", request.getItemName());
        parameters.put("quantity", "1");
        parameters.put("total_amount", String.valueOf(request.getTotalAmount()));
        parameters.put("tax_free_amount", "0");

        // 앱 스킴 직접 호출 대신 백엔드를 거쳐서 리다이렉트 (도메인 등록 이슈 해결)
        parameters.put("approval_url", backendUrl + "/api/v1/payment/ready/success?order_id=" + orderId);
        parameters.put("cancel_url", backendUrl + "/api/v1/payment/ready/cancel");
        parameters.put("fail_url", backendUrl + "/api/v1/payment/ready/fail");

        // 헤더 설정
        HttpHeaders headers = getHeaders();
        HttpEntity<Map<String, String>> requestEntity = new HttpEntity<>(parameters, headers);

        // API 호출
        ResponseEntity<KakaoReadyResponse> response = restTemplate.postForEntity(
                KAKAO_PAY_HOST + "/ready",
                requestEntity,
                KakaoReadyResponse.class);

        KakaoReadyResponse readyResponse = response.getBody();

        // DB 저장 (PENDING)
        Payment payment = Payment.builder()
                .user(user)
                .tid(readyResponse.getTid())
                .orderId(orderId)
                .itemName(request.getItemName())
                .amount(request.getTotalAmount())
                .status(Payment.PaymentStatus.PENDING)
                .build();

        paymentRepository.save(payment);

        // 프론트엔드에 orderId 전달 (승인 요청 시 필요)
        readyResponse.setOrderId(orderId);

        return readyResponse;
    }

    @Transactional
    public KakaoApproveResponse approve(String userId, PaymentApproveRequest request) {
        Payment payment = paymentRepository.findByOrderId(request.getOrderId())
                .orElseThrow(() -> new IllegalArgumentException("Payment info not found"));

        // 본인 확인 (선택 사항)
        if (!payment.getUser().getUserId().toString().equals(userId)) {
            throw new IllegalArgumentException("User mismatch");
        }

        // 카카오페이 승인 요청
        Map<String, String> parameters = new HashMap<>();
        parameters.put("cid", CID);
        parameters.put("tid", payment.getTid());
        parameters.put("partner_order_id", request.getOrderId());
        parameters.put("partner_user_id", userId);
        parameters.put("pg_token", request.getPgToken());

        HttpEntity<Map<String, String>> requestEntity = new HttpEntity<>(parameters, getHeaders());

        ResponseEntity<KakaoApproveResponse> response = restTemplate.postForEntity(
                KAKAO_PAY_HOST + "/approve",
                requestEntity,
                KakaoApproveResponse.class);

        KakaoApproveResponse approveResponse = response.getBody();

        // 결제 완료 처리
        payment.setStatus(Payment.PaymentStatus.PAID);
        payment.setApprovedAt(LocalDateTime.now());
        paymentRepository.save(payment);

        // 멤버십 등급 업데이트
        User user = payment.getUser();
        if ("Business".equalsIgnoreCase(payment.getItemName())) {
            user.setUserLevel(UserLevel.BUSINESS);
        } else {
            user.setUserLevel(UserLevel.PREMIUM);
        }
        // 만료일 설정 (예: 30일) - 로직에 따라 다름, 여기서는 한 달 자동 부여
        user.setMembershipExpiry(LocalDateTime.now().plusDays(30));
        userRepository.save(user);

        return approveResponse;
    }

    private HttpHeaders getHeaders() {
        HttpHeaders headers = new HttpHeaders();
        // Secret Key 사용 (DEV_... 형태)
        headers.set("Authorization", "SECRET_KEY " + kakaoSecretKey);
        headers.set("Content-Type", "application/json");
        return headers;
    }
}
