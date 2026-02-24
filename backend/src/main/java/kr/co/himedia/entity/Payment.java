package kr.co.himedia.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.time.LocalDateTime;
import java.util.UUID;

@Entity
@Table(name = "payments")
@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class Payment {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID paymentId;

    // 결제 요청자
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id")
    private User user;

    // 카카오페이 결제 고유 번호 (20자)
    @Column(name = "tid")
    private String tid;

    // 주문 번호 (우리가 생성하는 고유 ID)
    @Column(name = "order_id", nullable = false, unique = true)
    private String orderId;

    // 결제 상품명 (PREMIUM, BUSINESS 등)
    @Column(name = "item_name")
    private String itemName;

    // 결제 금액
    @Column(name = "amount")
    private Integer amount;

    // 결제 상태 (PENDING, PAID, FAILED, CANCELED)
    @Enumerated(EnumType.STRING)
    @Column(name = "status")
    private PaymentStatus status;

    @Column(name = "sid")
    private String sid;

    // 결제 승인 일시
    @Column(name = "approved_at")
    private LocalDateTime approvedAt;

    // 생성 일시
    @Column(name = "created_at")
    private LocalDateTime createdAt;

    @PrePersist
    public void prePersist() {
        this.createdAt = LocalDateTime.now();
        if (this.status == null) {
            this.status = PaymentStatus.PENDING;
        }
    }

    public enum PaymentStatus {
        PENDING, PAID, FAILED, CANCELED
    }
}
