package kr.co.himedia.service;

import kr.co.himedia.entity.Knowledge;
import kr.co.himedia.repository.KnowledgeRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.retry.annotation.Backoff;
import org.springframework.retry.annotation.Retryable;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * RAG 지식 검색 서비스
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class KnowledgeService {

    private final KnowledgeRepository knowledgeRepository;
    private final RestTemplate restTemplate = new RestTemplate();

    @Value("${ai.server.url.embedding:http://localhost:8000/api/v1/test/predict/embedding}")
    private String embeddingApiUrl;

    /**
     * 자연어 쿼리를 입력받아 가장 관련 있는 지식 문서들을 반환
     */
    public List<String> searchKnowledge(String query, int limit) {
        // 1. AI 서버를 통한 임베딩 (Ollama)
        double[] vector = getEmbedding(query);

        if (vector == null) {
            log.error("Failed to get embedding for query: {}", query);
            return List.of();
        }

        // 2. DB 유사도 검색
        List<Knowledge> documents = knowledgeRepository.findSimilarDocuments(vector, limit);

        // 3. 텍스트 내용만 추출
        return documents.stream()
                .map(Knowledge::getContent)
                .collect(Collectors.toList());
    }

    /**
     * AI 서버에 임베딩 요청 (BE-AI-008)
     */
    @SuppressWarnings("unchecked")
    @Retryable(retryFor = Exception.class, maxAttempts = 3, backoff = @Backoff(delay = 2000))
    private double[] getEmbedding(String text) {
        if (text == null)
            return null;
        try {
            Map<String, String> request = Map.of("text", text);
            Map<String, Object> response = restTemplate.postForObject(embeddingApiUrl, request, Map.class);

            if (response != null && response.containsKey("embedding")) {
                Object embeddingObj = response.get("embedding");
                if (embeddingObj instanceof List) {
                    List<Double> embeddingList = (List<Double>) embeddingObj;
                    return embeddingList.stream().mapToDouble(Double::doubleValue).toArray();
                }
            }
        } catch (Exception e) {
            log.error("Embedding API call failed: {}. Retrying...", e.getMessage());
            throw new RuntimeException("임베딩 API 호출 실패", e);
        }
        return null;
    }
}
