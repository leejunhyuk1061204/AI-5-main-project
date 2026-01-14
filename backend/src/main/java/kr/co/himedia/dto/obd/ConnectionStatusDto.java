package kr.co.himedia.dto.obd;

import lombok.*;

import java.time.LocalDateTime;

@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class ConnectionStatusDto {
    private boolean connected;
    private LocalDateTime lastDataTime;
    private String statusMessage; // e.g., "DRIVING", "PARKED"
}
