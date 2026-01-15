package kr.co.himedia.repository;

import kr.co.himedia.entity.Knowledge;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.UUID;

/**
 * RAG 지식 검색을 위한 Repository
 */
@Repository
public interface KnowledgeRepository extends JpaRepository<Knowledge, UUID> {

    /**
     * 벡터 유사도 검색 (Cosine Distance)
     * pgvector의 <=> 연산자를 사용함
     */
    @Query(value = "SELECT * FROM knowledge_vectors kv " +
            "ORDER BY kv.embedding <=> cast(:embedding as vector) " +
            "LIMIT :limit", nativeQuery = true)
    List<Knowledge> findSimilarDocuments(@Param("embedding") double[] embedding, @Param("limit") int limit);

    /**
     * 카테고리별 벡터 유사도 검색
     */
    @Query(value = "SELECT * FROM knowledge_vectors kv " +
            "WHERE kv.category = :category " +
            "ORDER BY kv.embedding <=> cast(:embedding as vector) " +
            "LIMIT :limit", nativeQuery = true)
    List<Knowledge> findSimilarDocumentsByCategory(@Param("category") String category,
            @Param("embedding") double[] embedding,
            @Param("limit") int limit);
}
