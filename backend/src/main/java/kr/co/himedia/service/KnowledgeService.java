package kr.co.himedia.service;

import kr.co.himedia.entity.DtcCode;
import kr.co.himedia.entity.Knowledge;
import kr.co.himedia.repository.DtcCodeRepository;
import kr.co.himedia.repository.KnowledgeRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.retry.annotation.Backoff;
import org.springframework.retry.annotation.Retryable;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.stream.Collectors;

/**
 * RAG 지식 검색 서비스
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class KnowledgeService {

    private final KnowledgeRepository knowledgeRepository;
    private final DtcCodeRepository dtcCodeRepository;
    private final RestTemplate restTemplate = new RestTemplate();

    @Value("${ai.server.url:http://localhost:8001}")
    private String aiServerBaseUrl;

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
     * 자연어 쿼리 + 제조사/모델 필터링 + 유사도 임계값 검색
     */
    public List<String> searchKnowledgeWithFilter(String query, String manufacturer, String model, int limit,
            Double threshold) {
        if (threshold == null || threshold <= 0) {
            threshold = 0.4; // 기본 유사도 임계값
        }

        // 1. 임베딩 벡터 생성
        double[] vector = getEmbedding(query);
        if (vector == null) {
            log.error("Failed to get embedding for filtered search: {}", query);
            return List.of();
        }

        // 2. 필터링된 DB 검색
        List<Knowledge> documents = knowledgeRepository.findSimilarDocumentsWithFilter(
                manufacturer, model, vector, threshold, limit);

        log.info("RAG Filtered Search: query='{}', mfr='{}', model='{}', threshold={}, results={}",
                query, manufacturer, model, threshold, documents.size());

        // 3. 텍스트 추출
        return documents.stream()
                .map(Knowledge::getContent)
                .collect(Collectors.toList());
    }

    /**
     * DTC 코드를 기반으로 관련 매뉴얼 검색 (Dual Description Strategy)
     */
    public List<String> searchDtcInformation(String code, String manufacturer, int limit) {
        List<String> results = new ArrayList<>();
        String searchContext = code;

        // 1. DTC 정보 조회 (DtcCodeRepository)
        if (manufacturer != null && !manufacturer.isBlank()) {
            Optional<DtcCode> exact = dtcCodeRepository.findByCodeAndManufacturer(code, manufacturer);
            if (exact.isEmpty()) {
                exact = dtcCodeRepository.findByCodeGeneric(code);
            }

            if (exact.isPresent()) {
                String descKo = exact.get().getDescriptionKo();
                String descEn = exact.get().getDescriptionEn();

                // RAG 검색용 컨텍스트는 '영어 설명' 우선 (없으면 한국어)
                String description = (descEn != null && !descEn.isBlank()) ? descEn : descKo;
                searchContext = description;

                // 결과에는 영어 정의만 포함 (LLM 참고용)
                if (descEn != null && !descEn.isBlank())
                    results.add("[DTC Definition (En)] " + descEn);
            }
        }

        /*
         * 사용자 요청 반영: DTC 조회 시 매뉴얼 검색(RAG)은 수행하지 않음.
         * 매뉴얼 검색이 필요하면 searchKnowledge()를 별도로 호출해야 함.
         */
        return results;
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
            String embeddingUrl = aiServerBaseUrl + "/api/v1/predict/embedding";
            log.info("[Embedding] Request url={}, textLength={}, textPreview={}",
                    embeddingUrl, text.length(), text.length() > 200 ? text.substring(0, 200) + "..." : text);
            Map<String, Object> response = restTemplate.postForObject(embeddingUrl, request, Map.class);

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
