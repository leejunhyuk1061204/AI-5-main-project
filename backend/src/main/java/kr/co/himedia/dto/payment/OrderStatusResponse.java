package kr.co.himedia.dto.payment;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class OrderStatusResponse {
    private String status;       // PENDING, PAID, FAILED, CANCELED
    private String membership;  // PAID일 때만 (PREMIUM, BUSINESS 등)
}
