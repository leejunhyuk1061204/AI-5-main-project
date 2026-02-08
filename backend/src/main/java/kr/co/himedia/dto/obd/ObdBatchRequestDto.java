package kr.co.himedia.dto.obd;

import java.util.List;
import java.util.UUID;
import lombok.Getter;
import lombok.Setter;
import lombok.ToString;

@Getter
@Setter
@ToString
public class ObdBatchRequestDto {
    private String batchId;
    private UUID vehicleId;
    private List<ObdLogDto> logs;
}
