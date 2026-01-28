package kr.co.himedia.smartcar.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

/**
 * 스마트카 연동 결과를 상세히 전달하기 위한 DTO
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class SmartcarSyncResponse {
    private int totalCount;
    private List<VehicleSyncResult> results;

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class VehicleSyncResult {
        private String manufacturer;
        private String modelName;
        private String vin;
        private String status; // "CONNECTED" (Existing) or "REGISTERED" (New)
    }
}
