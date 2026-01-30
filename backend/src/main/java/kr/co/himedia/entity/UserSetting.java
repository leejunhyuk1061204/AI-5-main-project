package kr.co.himedia.entity;

import jakarta.persistence.*;
import lombok.*;

import java.util.UUID;

@Entity
@Table(name = "user_settings")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class UserSetting {

    @Id
    @Column(name = "user_id")
    private UUID userId;

    @OneToOne(fetch = FetchType.LAZY)
    @MapsId
    @JoinColumn(name = "user_id")
    private User user;

    @Column(name = "noti_maintenance", nullable = false)
    @Builder.Default
    private Boolean notiMaintenance = true;

    @Column(name = "noti_anomaly", nullable = false)
    @Builder.Default
    private Boolean notiAnomaly = true;

    @Column(name = "noti_dtc_tts", nullable = false)
    @Builder.Default
    private Boolean notiDtcTts = true;

    @Column(name = "noti_marketing", nullable = false)
    @Builder.Default
    private Boolean notiMarketing = false;

    @Column(name = "night_push_allowed", nullable = false)
    @Builder.Default
    private Boolean nightPushAllowed = false;
}
