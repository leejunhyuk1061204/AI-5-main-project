// OBD 로그 엔티티: 차량에서 수집된 실시간 센서 데이터를 저장
// Persistable 구현으로 saveAll() 시 SELECT 없이 바로 INSERT 수행
package kr.co.himedia.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.IdClass;
import jakarta.persistence.Table;
import jakarta.persistence.Transient;
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
import org.springframework.data.domain.Persistable;

@Entity
@Table(name = "obd_logs")
@Getter
@Builder
@NoArgsConstructor
@AllArgsConstructor
@IdClass(ObdLog.ObdLogId.class)
public class ObdLog implements Persistable<ObdLog.ObdLogId> {

    @Override
    @Transient
    public ObdLogId getId() {
        return new ObdLogId(time, vehicleId);
    }

    @Override
    @Transient
    public boolean isNew() {
        return true; // 항상 새 엔티티로 인식 → SELECT 없이 바로 INSERT
    }

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
