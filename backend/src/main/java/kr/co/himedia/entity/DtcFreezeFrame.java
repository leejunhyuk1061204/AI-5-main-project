package kr.co.himedia.entity;

import jakarta.persistence.*;
import lombok.*;
import java.util.UUID;

/**
 * DTC 고장 시점 스냅샷 (Mode 02 데이터)
 * DB 설계서 2.4.2 규격 준수
 */
@Entity
@Table(name = "dtc_freeze_frames")
@Getter
@Setter
@Builder
@AllArgsConstructor
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class DtcFreezeFrame {

    @Id
    @GeneratedValue(strategy = GenerationType.AUTO)
    @Column(name = "frame_id")
    private UUID frameId;

    @OneToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "dtc_id", nullable = false, unique = true)
    private DtcHistory dtcHistory;

    @Column(name = "rpm")
    private Double rpm;

    @Column(name = "speed")
    private Double speed;

    @Column(name = "coolant_temp")
    private Double coolantTemp;

    @Column(name = "engine_load")
    private Double engineLoad;

    @Column(name = "ambient_temp")
    private Double ambientTemp;

    @Column(name = "fuel_pressure")
    private Double fuelPressure;

    @Column(name = "pids_snapshot", columnDefinition = "TEXT")
    private String pidsSnapshot; // JSON String
}
