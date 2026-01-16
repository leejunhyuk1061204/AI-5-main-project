package kr.co.himedia.entity;

import jakarta.persistence.*;
import lombok.*;

import java.util.UUID;

@Entity
@Table(name = "diag_results")
@Getter
@Builder
@AllArgsConstructor
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class DiagResult {

    @Id
    @GeneratedValue(strategy = GenerationType.AUTO)
    @Column(name = "diag_result_id")
    private UUID diagResultId;

    @Column(name = "diag_session_id", nullable = false)
    private UUID diagSessionId;

    @Column(name = "final_report", columnDefinition = "TEXT")
    private String finalReport;

    @Column(name = "risk_level")
    @Enumerated(EnumType.STRING)
    private RiskLevel riskLevel;

    // JSONB 데이터들을 보관 (간소화를 위해 String 또는 전용 컨버터 사용 가능하나
    // 여기서는 기본적으로 Map 구조를 String으로 변환 저장하거나 필드로 관리)

    @Column(name = "detected_issues", columnDefinition = "TEXT")
    private String detectedIssues; // JSON String

    @Column(name = "actions_json", columnDefinition = "TEXT")
    private String actionsJson; // JSON String

    public enum RiskLevel {
        LOW, MID, HIGH, CRITICAL
    }
}
