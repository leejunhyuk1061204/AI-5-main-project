package kr.co.himedia.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.IdClass;
import jakarta.persistence.Table;
import java.io.Serializable;
import java.time.OffsetDateTime;
import java.util.UUID;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.EqualsAndHashCode;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

@Entity
@Table(name = "obd_logs")
@Getter
@Builder
@NoArgsConstructor
@AllArgsConstructor
@IdClass(ObdLog.ObdLogId.class)
public class ObdLog {

    @Id
    private OffsetDateTime time;

    @Id
    @Column(name = "vehicles_id")
    private UUID vehicleId;

    private Double rpm;
    private Double speed;
    private Double voltage;

    @Column(name = "coolant_temp")
    private Double coolantTemp;

    @Column(name = "engine_load")
    private Double engineLoad;

    @Column(name = "fuel_trim_short")
    private Double fuelTrimShort;

    @Column(name = "fuel_trim_long")
    private Double fuelTrimLong;

    @Column(name = "json_extra")
    @JdbcTypeCode(SqlTypes.JSON)
    private String jsonExtra;

    @Getter
    @NoArgsConstructor
    @AllArgsConstructor
    @Builder
    @EqualsAndHashCode
    public static class ObdLogId implements Serializable {
        private OffsetDateTime time;
        private UUID vehicleId;
    }
}
