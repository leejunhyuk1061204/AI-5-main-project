package kr.co.himedia.dto.payment;

import lombok.Data;

@Data
public class KakaoReadyResponse {
    private String tid; // 결제 고유 번호
    private String next_redirect_app_url; // 앱에서 띄울 결제 페이지 URL
    private String next_redirect_mobile_url;
    private String next_redirect_pc_url;
    private String android_app_scheme;
    private String ios_app_scheme;
    private String created_at;
    private String orderId; // 프론트엔드 전달용 (우리가 생성한 주문 ID)
}
