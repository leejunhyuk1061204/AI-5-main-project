package kr.co.himedia.dto.obd;

import lombok.*;

import java.util.UUID;

@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class ObdDeviceDto {
    private UUID id;
    private String deviceId;
    private String deviceType;
    private String name;
}
