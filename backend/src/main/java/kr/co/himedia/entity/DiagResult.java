package kr.co.himedia.entity;

import jakarta.persistence.*;
import kr.co.himedia.domain.DiagAction;
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

    @Column(name = "response_mode", length = 20)
    private String responseMode; // REPORT | INTERACTIVE

    @Column(name = "confidence_level", length = 20)
    private String confidenceLevel; // HIGH | MEDIUM | LOW

    @Column(name = "summary", columnDefinition = "TEXT")
    private String summary;

    // JSONB 데이터들을 보관 (간소화를 위해 String 또는 전용 컨버터 사용 가능하나
    // 여기서는 기본적으로 Map 구조를 String으로 변환 저장하거나 필드로 관리)

    @Column(name = "detected_issues", columnDefinition = "TEXT")
    private String detectedIssues; // JSON String

    @Column(name = "actions_json", columnDefinition = "TEXT")
    private String actionsJson; // JSON String

    @Column(name = "interactive_json", columnDefinition = "TEXT")
    private String interactiveJson; // JSON String (질문 및 대화 이력)

    @Enumerated(EnumType.STRING)
    @Column(name = "requested_action", length = 30)
    private DiagAction requestedAction;

    public enum RiskLevel {
        LOW, MID, HIGH, CRITICAL
    }
}
