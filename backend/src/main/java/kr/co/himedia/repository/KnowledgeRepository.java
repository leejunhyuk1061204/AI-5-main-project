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
        /**
         * 벡터 유사도 검색 (Cosine Distance)
         * pgvector의 <=> 연산자를 사용함
         */
        @Query(value = "SELECT * FROM knowledge_vectors kv " +
                        "ORDER BY kv.embedding <=> cast(:embedding as vector) " +
                        "LIMIT :limit", nativeQuery = true)
        List<Knowledge> findSimilarDocuments(@Param("embedding") double[] embedding, @Param("limit") int limit);

        /**
         * 제조사, 모델 필터링 및 유사도 임계값을 적용한 벡터 유사도 검색
         * model은 부분 일치(LIKE '%modelName%')로 매칭 (car_model_master "MDX" vs 매뉴얼 "MDX V6-3.7L" 등)
         */
        @Query(value = "SELECT * FROM knowledge_vectors kv " +
                        "WHERE kv.metadata->>'manufacturer' = :manufacturer " +
                        "AND kv.metadata->>'model' LIKE ('%' || :modelName || '%') " +
                        "AND (kv.embedding <=> cast(:embedding as vector)) <= :threshold " +
                        "ORDER BY kv.embedding <=> cast(:embedding as vector) " +
                        "LIMIT :limit", nativeQuery = true)
        List<Knowledge> findSimilarDocumentsWithFilter(
                        @Param("manufacturer") String manufacturer,
                        @Param("modelName") String modelName,
                        @Param("embedding") double[] embedding,
                        @Param("threshold") double threshold,
                        @Param("limit") int limit);
}
