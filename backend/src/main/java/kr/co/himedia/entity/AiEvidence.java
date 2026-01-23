package kr.co.himedia.entity;

import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.CreationTimestamp;

import java.time.LocalDateTime;
import java.util.UUID;

/**
 * AI 진단 근거 데이터 (이미지, 오디오 파일 경로 등)를 저장하는 엔티티
 */
@Entity
@Table(name = "ai_evidences")
@Getter
@Builder
@AllArgsConstructor
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class AiEvidence {

    @Id
    @GeneratedValue(strategy = GenerationType.AUTO)
    @Column(name = "evidence_id")
    private UUID evidenceId;

    @Column(name = "diag_session_id", nullable = false)
    private UUID diagSessionId;

    @Enumerated(EnumType.STRING)
    @Column(name = "evidence_type", length = 20)
    private EvidenceType evidenceType; // IMAGE, AUDIO

    @Column(name = "file_path", nullable = false)
    private String filePath;

    @Column(name = "inference_label")
    private String inferenceLabel; // AI가 판단한 라벨 (예: "정상 소음", "벨트 마모")

    @Column(name = "confidence")
    private Double confidence;

    @CreationTimestamp
    @Column(name = "created_at", updatable = false)
    private LocalDateTime createdAt;

    public enum EvidenceType {
        IMAGE, AUDIO, DATA
    }
}
