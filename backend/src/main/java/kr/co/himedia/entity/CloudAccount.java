package kr.co.himedia.entity;

import jakarta.persistence.*;
import kr.co.himedia.common.BaseEntity;
import lombok.*;

import java.time.LocalDateTime;
import java.util.UUID;

@Entity
@Table(name = "cloud_accounts")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class CloudAccount extends BaseEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id", nullable = false)
    private User user;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private CloudProvider provider;

    @Column(name = "provider_user_id")
    private String providerUserId;

    @Column(name = "access_token", columnDefinition = "TEXT")
    private String accessToken;

    @Column(name = "refresh_token", columnDefinition = "TEXT")
    private String refreshToken;

    @Column(name = "expires_at")
    private LocalDateTime expiresAt;

    @Column(name = "last_synced_at")
    private LocalDateTime lastSyncedAt;
}
