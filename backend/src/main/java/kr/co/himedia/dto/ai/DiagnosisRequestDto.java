package kr.co.himedia.dto.ai;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

/**
 * AI 진단 요청을 위한 데이터 전송 객체
 */
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class DiagnosisRequestDto {
    private String vehicleId;
    private String type; // VISION, AUDIO, ANOMALY
    private String mediaUrl; // S3 URL (Hybrid: 로컬 업로드 시 S3 URL로 변환되어 전달되거나, 로컬 경로는 내부 처리)
    private String description; // 사용자 코멘트
}
