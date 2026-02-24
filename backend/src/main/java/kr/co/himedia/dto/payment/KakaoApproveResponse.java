package kr.co.himedia.dto.payment;

import lombok.Data;

@Data
public class KakaoApproveResponse {
    private String aid; // 요청 고유 번호
    private String tid; // 결제 고유 번호
    private String cid; // 가맹점 코드
    private String partner_order_id; // 가맹점 주문 번호
    private String partner_user_id; // 가맹점 회원 id
    private String payment_method_type; // 결제 수단
    private Amount amount; // 결제 금액 정보
    private String item_name; // 상품명
    private String approved_at; // 결제 승인 시각
    private String sid; // 정기결제 고유 번호

    @Data
    public static class Amount {
        private Integer total; // 전체 결제 금액
        private Integer tax_free; // 비과세 금액
        private Integer vat; // 부가세 금액
    }
}
