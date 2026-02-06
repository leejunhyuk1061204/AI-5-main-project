package kr.co.himedia.dto.ai;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import java.util.List;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class DtcBatchRequest {
    private String vehicleId;
    private List<DtcInfo> dtcs;
    private FreezeFrameData freezeFrame;

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class DtcInfo {
        private String code;
        private String type; // STORED, PENDING, PERMANENT
        private String status; // ACTIVE, RESOLVED
    }

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class FreezeFrameData {
        private Double rpm;
        private Double speed;
        private Double coolantTemp;
        private Double engineLoad;
        private Double ambientTemp;
        private Double fuelPressure;
        private String pidsSnapshot;
    }
}
