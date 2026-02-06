package kr.co.himedia.entity;

import jakarta.persistence.*;
import lombok.*;

import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.util.UUID;

@Entity
@Table(name = "obd_device_vehicle_history")
@Getter
@Setter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
@Builder
public class ObdDeviceVehicleHistory {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @Column(name = "obd_device_id", nullable = false)
    private UUID obdDeviceId;

    @Column(name = "vehicles_id", nullable = false)
    private UUID vehiclesId;

    @Column(name = "calid", length = 255)
    private String calid;

    @Column(name = "cvn", length = 255)
    private String cvn;

    @Column(name = "last_connected_at", nullable = false)
    private OffsetDateTime lastConnectedAt;

    @Column(name = "created_at")
    private LocalDateTime createdAt;

    @Column(name = "updated_at")
    private LocalDateTime updatedAt;

    @PrePersist
    protected void onCreate() {
        if (createdAt == null) createdAt = LocalDateTime.now();
        updatedAt = LocalDateTime.now();
        if (lastConnectedAt == null) lastConnectedAt = OffsetDateTime.now();
    }

    @PreUpdate
    protected void onUpdate() {
        updatedAt = LocalDateTime.now();
    }
}
