package kr.co.himedia.dto.payment;

import lombok.Data;

@Data
public class PaymentApproveRequest {
    private String pgToken; // 카카오페이에서 받은 토큰
    private String orderId; // 우리가 생성한 주문 번호
}
