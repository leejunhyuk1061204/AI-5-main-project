package kr.co.himedia.dto.ai;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

/**
 * DTC(Diagnostic Trouble Code) 보고를 위한 데이터 전송 객체
 */
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class DtcDto {
    private String vehicleId;
    private String dtcCode;
    private String description;
    private String severity; // CRITICAL, WARNING, INFO
    private String status; // ACTIVE, STORED, PENDING
}
