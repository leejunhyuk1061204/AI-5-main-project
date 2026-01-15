package kr.co.himedia.entity;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.AccessLevel;

import java.time.LocalDateTime;
import java.util.UUID;

@Entity
@Table(name = "dtc_history")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class DtcHistory {

    @Id
    @GeneratedValue(strategy = GenerationType.AUTO)
    @Column(name = "dtc_id")
    private UUID dtcId;

    @Column(name = "vehicles_id", nullable = false)
    private UUID vehiclesId;

    @Column(name = "dtc_code", nullable = false)
    private String dtcCode;

    @Column(name = "description")
    private String description;

    @Enumerated(EnumType.STRING)
    @Column(name = "dtc_type")
    private DtcType dtcType;

    @Enumerated(EnumType.STRING)
    @Column(name = "status")
    private DtcStatus status;

    @Column(name = "discovered_at")
    private LocalDateTime discoveredAt;

    @Column(name = "resolved_at")
    private LocalDateTime resolvedAt;

    public DtcHistory(UUID vehiclesId, String dtcCode, String description, DtcType dtcType, DtcStatus status) {
        this.vehiclesId = vehiclesId;
        this.dtcCode = dtcCode;
        this.description = description;
        this.dtcType = dtcType;
        this.status = status;
        this.discoveredAt = LocalDateTime.now();
    }

    public enum DtcType {
        STORED, PENDING, PERMANENT
    }

    public enum DtcStatus {
        ACTIVE, RESOLVED, CLEARED
    }
}
