package kr.co.himedia.dto.obd;

import lombok.Getter;
import lombok.Setter;

import java.util.UUID;

@Getter
@Setter
public class ConnectHistoryRequest {
    private UUID vehicleId;
    private String vin;
    private String calid;
    private String cvn;
}
