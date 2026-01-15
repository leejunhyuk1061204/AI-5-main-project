package kr.co.himedia.entity;

import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.util.Map;
import java.util.UUID;

/**
 * RAG 지식 베이스 벡터 데이터 엔티티
 */
@Entity
@Table(name = "knowledge_vectors")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Knowledge {

    @Id
    @GeneratedValue(strategy = GenerationType.AUTO)
    @Column(name = "knowledge_id", columnDefinition = "UUID")
    private UUID knowledgeId;

    @Column(length = 20)
    private String category;

    @Column(columnDefinition = "TEXT")
    private String content;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(columnDefinition = "JSONB")
    private Map<String, Object> metadata;

    @Column(name = "content_hash", unique = true, length = 64)
    private String contentHash;

    // embedding 필드는 네이티브 쿼리로 처리하므로 엔티티 매핑에서 제외하거나
    // 특수 타입을 사용해야 함. 여기서는 조회를 위해 Transient 처리하거나 제외.
}
