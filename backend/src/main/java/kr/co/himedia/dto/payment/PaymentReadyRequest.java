package kr.co.himedia.dto.payment;

import lombok.Data;

@Data
public class PaymentReadyRequest {
    private String itemName; // PREMIUM or BUSINESS
    private Integer totalAmount; // 금액
}
