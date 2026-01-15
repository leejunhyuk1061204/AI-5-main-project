package kr.co.himedia.entity;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.AccessLevel;
import org.hibernate.annotations.CreationTimestamp;

import java.time.LocalDateTime;
import java.util.UUID;

@Entity
@Table(name = "diag_sessions")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class DiagSession {

    @Id
    @GeneratedValue(strategy = GenerationType.AUTO)
    @Column(name = "diag_session_id")
    private UUID diagSessionId;

    @Column(name = "vehicles_id", nullable = false)
    private UUID vehiclesId;

    @Column(name = "trip_id")
    private UUID tripId;

    @Enumerated(EnumType.STRING)
    @Column(name = "trigger_type")
    private DiagTriggerType triggerType;

    @Enumerated(EnumType.STRING)
    @Column(name = "status")
    private DiagStatus status;

    @CreationTimestamp
    @Column(name = "created_at")
    private LocalDateTime createdAt;

    public DiagSession(UUID vehiclesId, UUID tripId, DiagTriggerType triggerType) {
        this.vehiclesId = vehiclesId;
        this.tripId = tripId;
        this.triggerType = triggerType;
        this.status = DiagStatus.PENDING;
    }

    public void updateStatus(DiagStatus status) {
        this.status = status;
    }

    public enum DiagTriggerType {
        MANUAL, DTC, ANOMALY, ROUTINE
    }

    public enum DiagStatus {
        PENDING, PROCESSING, DONE, FAILED
    }
}
