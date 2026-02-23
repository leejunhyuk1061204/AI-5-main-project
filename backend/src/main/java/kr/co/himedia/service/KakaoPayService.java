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

    // @Value("${app.backend-url}")
    // private String backendUrl;

    private static final String KAKAO_PAY_HOST = "https://open-api.kakaopay.com/online/v1/payment";
    private static final String CID_ONETIME = "TC0ONETIME"; // 테스트용 단건 결제 CID
    private static final String CID_SUBSCRIPTION = "TCSUBSCRIP"; // 테스트용 정기 결제 CID

    /**
     * 카카오페이 결제 준비를 요청하고 결제 정보를 저장합니다.
     */
    @Transactional
    public KakaoReadyResponse ready(String userId, PaymentReadyRequest request, String baseUrl) {
        User user = userRepository.findById(UUID.fromString(userId))
                .orElseThrow(() -> new IllegalArgumentException("User not found"));

        // 주문 번호 생성
        String orderId = UUID.randomUUID().toString();

        // 정기 결제 여부 판단 (Premium, Business인 경우 SUBSCRIPTION 사용)
        String cid = ("Premium".equalsIgnoreCase(request.getItemName())
                || "Business".equalsIgnoreCase(request.getItemName()))
                        ? CID_SUBSCRIPTION
                        : CID_ONETIME;

        // 카카오페이 요청 본문
        Map<String, Object> parameters = new HashMap<>();
        parameters.put("cid", cid);
        parameters.put("partner_order_id", orderId);
        parameters.put("partner_user_id", userId);
        parameters.put("item_name", request.getItemName());
        parameters.put("quantity", 1); // 카카오페이 신규 JSON API에서는 Integer를 요구합니다.
        parameters.put("total_amount", request.getTotalAmount()); // Integer
        parameters.put("tax_free_amount", 0); // Integer

        // 카카오페이는 http/https URL만 허용하므로 백엔드 콜백 사용
        // baseUrl은 동적으로 추출되므로 로컬 IP(192.168.x.x)가 자동으로 사용됨
        parameters.put("approval_url", baseUrl + "/api/v1/payment/ready/success?order_id=" + orderId);
        parameters.put("cancel_url", baseUrl + "/api/v1/payment/ready/cancel");
        parameters.put("fail_url", baseUrl + "/api/v1/payment/ready/fail");

        // 헤더 설정
        HttpHeaders headers = getHeaders();
        HttpEntity<Map<String, Object>> requestEntity = new HttpEntity<>(parameters, headers);

        log.info("[KakaoPay] Requesting ready API from Kakao with orderId: {}", orderId);

        // API 호출
        ResponseEntity<KakaoReadyResponse> response;
        try {
            response = restTemplate.postForEntity(
                    KAKAO_PAY_HOST + "/ready",
                    requestEntity,
                    KakaoReadyResponse.class);
        } catch (Exception e) {
            log.error("[KakaoPay] Kakao API call failed: {}", e.getMessage());
            if (e instanceof org.springframework.web.client.HttpStatusCodeException) {
                log.error("[KakaoPay] Error full response: {}",
                        ((org.springframework.web.client.HttpStatusCodeException) e).getResponseBodyAsString());
            }
            throw new RuntimeException("Kakao Pay API call failed", e);
        }

        KakaoReadyResponse readyResponse = response.getBody();
        log.info("[KakaoPay] Ready API response received. TID: {}",
                readyResponse != null ? readyResponse.getTid() : "null");

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

    /**
     * 카카오페이 결제 승인을 요청하고 멤버십 등급을 업데이트합니다.
     */
    @Transactional
    public KakaoApproveResponse approve(String userId, PaymentApproveRequest request) {
        Payment payment = paymentRepository.findByOrderId(request.getOrderId())
                .orElseThrow(() -> new IllegalArgumentException("Payment info not found"));

        // 본인 확인 (선택 사항)
        if (!payment.getUser().getUserId().toString().equals(userId)) {
            throw new IllegalArgumentException("User mismatch");
        }

        // 카카오페이 승인 요청
        Map<String, Object> parameters = new HashMap<>();
        parameters.put("cid", payment.getItemName().toLowerCase().contains("free") ? CID_ONETIME : CID_SUBSCRIPTION);
        parameters.put("tid", payment.getTid());
        parameters.put("partner_order_id", request.getOrderId());
        parameters.put("partner_user_id", userId);
        parameters.put("pg_token", request.getPgToken());

        HttpEntity<Map<String, Object>> requestEntity = new HttpEntity<>(parameters, getHeaders());

        ResponseEntity<KakaoApproveResponse> response = restTemplate.postForEntity(
                KAKAO_PAY_HOST + "/approve",
                requestEntity,
                KakaoApproveResponse.class);

        KakaoApproveResponse approveResponse = response.getBody();
        return processApproveResult(payment, approveResponse);
    }

    /**
     * 주문 ID를 기반으로 결제를 승인 처리합니다. (백엔드 콜백용)
     */
    @Transactional
    public KakaoApproveResponse approveByOrderId(String orderId, String pgToken) {
        log.info("[KakaoPay] Backend callback approve for orderId: {}", orderId);

        Payment payment = paymentRepository.findByOrderId(orderId)
                .orElseThrow(() -> new IllegalArgumentException("Payment info not found"));

        if (payment.getStatus() == Payment.PaymentStatus.PAID) {
            log.info("[KakaoPay] Already paid. Skipping approve for orderId: {}", orderId);
            return null; // 이미 처리됨
        }

        // 카카오페이 승인 요청
        Map<String, Object> parameters = new HashMap<>();
        parameters.put("cid", payment.getItemName().toLowerCase().contains("free") ? CID_ONETIME : CID_SUBSCRIPTION);
        parameters.put("tid", payment.getTid());
        parameters.put("partner_order_id", orderId);
        parameters.put("partner_user_id", payment.getUser().getUserId().toString());
        parameters.put("pg_token", pgToken);

        HttpEntity<Map<String, Object>> requestEntity = new HttpEntity<>(parameters, getHeaders());

        ResponseEntity<KakaoApproveResponse> response = restTemplate.postForEntity(
                KAKAO_PAY_HOST + "/approve",
                requestEntity,
                KakaoApproveResponse.class);

        KakaoApproveResponse approveResponse = response.getBody();
        return processApproveResult(payment, approveResponse);
    }

    /**
     * 승인 결과 처리 공통 로직 (상태 업데이트 및 멤버십 부여)
     */
    private KakaoApproveResponse processApproveResult(Payment payment, KakaoApproveResponse approveResponse) {
        // 결제 완료 처리
        payment.setStatus(Payment.PaymentStatus.PAID);
        payment.setApprovedAt(LocalDateTime.now());
        if (approveResponse != null && approveResponse.getSid() != null) {
            payment.setSid(approveResponse.getSid());
        }
        paymentRepository.save(payment);

        // 멤버십 등급 업데이트 및 만료일 설정 (누적 연장 로직)
        User user = payment.getUser();
        if (approveResponse != null && approveResponse.getSid() != null) {
            user.setKakaoSid(approveResponse.getSid());
        }

        if ("Business".equalsIgnoreCase(payment.getItemName())) {
            user.setUserLevel(UserLevel.BUSINESS);
        } else {
            user.setUserLevel(UserLevel.PREMIUM);
        }

        LocalDateTime now = LocalDateTime.now();
        LocalDateTime currentExpiry = user.getMembershipExpiry();

        if (currentExpiry != null && currentExpiry.isAfter(now)) {
            // 이미 프리미엄 기간이 남아있다면 기존 만료일에서 30일 연장
            user.setMembershipExpiry(currentExpiry.plusDays(30));
        } else {
            // 만료되었거나 처음 구매라면 현재 시간으로부터 30일 부여
            user.setMembershipExpiry(now.plusDays(30));
        }

        userRepository.save(user);
        log.info("[KakaoPay] Payment success and membership updated for user: {}", user.getEmail());

        return approveResponse;
    }

    /**
     * 사용자의 멤버십을 FREE로 초기화합니다.
     */
    @Transactional
    public void resetMembership(String userId) {
        User user = userRepository.findById(UUID.fromString(userId))
                .orElseThrow(() -> new IllegalArgumentException("User not found"));

        log.info("[Membership] Resetting membership to FREE for user: {}", userId);

        user.setUserLevel(UserLevel.FREE);
        user.setMembershipExpiry(null);
        userRepository.save(user);
    }

    private HttpHeaders getHeaders() {
        HttpHeaders headers = new HttpHeaders();
        // Secret Key 사용 (DEV_... 형태)
        headers.set("Authorization", "SECRET_KEY " + kakaoSecretKey);
        headers.set("Content-Type", "application/json");
        return headers;
    }
}
