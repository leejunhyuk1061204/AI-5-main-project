package kr.co.himedia.dto.maintenance;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.time.LocalDate;

@Getter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class MaintenanceReceiptResponse {
    private String ocrText; // 원본 텍스트
    private String shopName; // 상호명 (추출)
    private LocalDate date; // 날짜 (추출)
    private Integer cost; // 금액 (추출)
    private String detectedItem; // 의심되는 정비 항목 (키워드 매칭)
}
