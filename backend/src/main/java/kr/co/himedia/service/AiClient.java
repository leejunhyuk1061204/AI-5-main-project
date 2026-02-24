package kr.co.himedia.service;

import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.retry.annotation.Backoff;
import org.springframework.retry.annotation.Retryable;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;
import java.util.Map;

/**
 * AI 서버와의 개별 API 통신을 전담하는 컴포넌트입니다.
 * 각 메서드에는 @Retryable이 적용되어 일시적인 네트워크 오류 시 자동 재시도합니다.
 */
@Slf4j
@Component
public class AiClient {

    private final RestTemplate restTemplate;

    @Value("${ai.server.url}")
    private String aiServerBaseUrl;

    public AiClient() {
        org.springframework.http.client.SimpleClientHttpRequestFactory factory = new org.springframework.http.client.SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(5000);
        factory.setReadTimeout(300000); // 15분 단위 청크 데이터 처리 등 긴 분석 시간을 고려하여 5분으로 상향

        // InputStream을 여러 번 읽을 수 있도록 BufferingClientHttpRequestFactory 사용
        org.springframework.http.client.ClientHttpRequestFactory bufferingFactory = new org.springframework.http.client.BufferingClientHttpRequestFactory(
                factory);
        this.restTemplate = new RestTemplate(bufferingFactory);

        // AI 통신 로깅용 인터셉터 추가
        this.restTemplate.getInterceptors().add(new AiLoggingInterceptor());
    }

    /**
     * AI 서버와의 통신 요청/응답 전문을 가로채서 로깅하는 인터셉터
     */
    private class AiLoggingInterceptor implements org.springframework.http.client.ClientHttpRequestInterceptor {
        private final org.slf4j.Logger aiLogger = org.slf4j.LoggerFactory.getLogger("AI_COMMUNICATION_LOG");

        @Override
        public org.springframework.http.client.ClientHttpResponse intercept(
                org.springframework.http.HttpRequest request, byte[] body,
                org.springframework.http.client.ClientHttpRequestExecution execution) throws java.io.IOException {

            String reqBody = new String(body, java.nio.charset.StandardCharsets.UTF_8);
            aiLogger.info("========== [AI Request] ==========");
            aiLogger.info("URI: {} {}", request.getMethod(), request.getURI());
            aiLogger.info("Request Body: {}", reqBody);

            long start = System.currentTimeMillis();
            org.springframework.http.client.ClientHttpResponse response = execution.execute(request, body);
            long end = System.currentTimeMillis();

            // BufferingClientHttpRequestFactory 덕분에 응답 바디를 읽어도 실제 클라이언트단에서 다시 읽을 수 있음
            String resBody = org.springframework.util.StreamUtils.copyToString(response.getBody(),
                    java.nio.charset.StandardCharsets.UTF_8);

            aiLogger.info("========== [AI Response] ==========");
            aiLogger.info("Status: {} ({}ms)", response.getStatusCode(), (end - start));
            aiLogger.info("Response Body: {}", resBody);
            aiLogger.info("===================================\n");

            return response;
        }
    }

    @Retryable(retryFor = Exception.class, maxAttempts = 3, backoff = @Backoff(delay = 2000))
    public Map<String, Object> callVisualAnalysis(String imageUrl, java.util.UUID vehicleId, java.util.UUID sessionId) {
        log.info("[Retryable] Requesting Visual Analysis - Vehicle: {}, Session: {}, URL: {}", vehicleId, sessionId,
                imageUrl);
        try {
            Map<String, Object> request = new java.util.HashMap<>();
            request.put("imageUrl", imageUrl);
            request.put("vehicleId", vehicleId != null ? vehicleId.toString() : null);
            request.put("sessionId", sessionId != null ? sessionId.toString() : null);

            String requestUrl = aiServerBaseUrl + "/api/v1/visual";
            @SuppressWarnings("unchecked")
            Map<String, Object> result = restTemplate.postForObject(requestUrl, request, Map.class);
            return result;
        } catch (Exception e) {
            log.error("[AiClient] Visual Analysis Failed [Vehicle: {}, Session: {}]. URL: {}, Error: {}",
                    vehicleId, sessionId, aiServerBaseUrl + "/api/v1/visual", e.getMessage());
            throw e;
        }
    }

    @Retryable(retryFor = Exception.class, maxAttempts = 3, backoff = @Backoff(delay = 2000))
    public Map<String, Object> callAudioAnalysis(String audioUrl, java.util.UUID vehicleId, java.util.UUID sessionId) {
        log.info("[Retryable] Requesting Audio Analysis - Vehicle: {}, Session: {}, URL: {}", vehicleId, sessionId,
                audioUrl);
        try {
            Map<String, Object> request = new java.util.HashMap<>();
            request.put("audioUrl", audioUrl);
            request.put("vehicleId", vehicleId != null ? vehicleId.toString() : null);
            request.put("sessionId", sessionId != null ? sessionId.toString() : null);

            String requestUrl = aiServerBaseUrl + "/api/v1/predict/audio";
            @SuppressWarnings("unchecked")
            Map<String, Object> result = restTemplate.postForObject(requestUrl, request, Map.class);
            return result;
        } catch (Exception e) {
            log.error("[AiClient] Audio Analysis Failed [Vehicle: {}, Session: {}]. URL: {}, Error: {}",
                    vehicleId, sessionId, aiServerBaseUrl + "/api/v1/predict/audio", e.getMessage());
            throw e;
        }
    }

    @Retryable(retryFor = Exception.class, maxAttempts = 2, backoff = @Backoff(delay = 3000))
    public Map<String, Object> callAnomalyDetection(Map<String, Object> request) {
        log.info("[Retryable] Requesting Anomaly Detection");
        String requestUrl = aiServerBaseUrl + "/api/v1/predict/anomaly";
        @SuppressWarnings("unchecked")
        Map<String, Object> result = (Map<String, Object>) restTemplate.postForObject(requestUrl, request,
                Map.class);
        return result;
    }

    @Retryable(retryFor = Exception.class, maxAttempts = 2, backoff = @Backoff(delay = 5000))
    public Map<String, Object> callComprehensiveDiagnosis(Map<String, Object> request) {
        log.info("[Retryable] Requesting Comprehensive Diagnosis");
        String requestUrl = aiServerBaseUrl + "/api/v1/connect/predict/comprehensive";
        try {
            @SuppressWarnings("unchecked")
            Map<String, Object> result = (Map<String, Object>) restTemplate.postForObject(requestUrl, request,
                    Map.class);
            return result;
        } catch (Exception e) {
            log.error("[AiClient] Comprehensive Diagnosis Failed. URL: {}, Error: {}", requestUrl,
                    e.getMessage());
            throw e;
        }
    }

    /**
     * 텍스트 임베딩 요청 (Ollama)
     */
    @SuppressWarnings("unchecked")
    @Retryable(retryFor = Exception.class, maxAttempts = 3, backoff = @Backoff(delay = 2000))
    public double[] getEmbedding(String text) {
        if (text == null || text.isBlank())
            return null;
        try {
            String requestUrl = aiServerBaseUrl + "/api/v1/predict/embedding";
            Map<String, String> request = Map.of("text", text);
            log.info("[Embedding] Request url={}, textLength={}, textPreview={}",
                    requestUrl, text.length(),
                    text.length() > 200 ? text.substring(0, 200) + "..." : text);
            Map<String, Object> response = restTemplate.postForObject(requestUrl, request, Map.class);

            if (response != null && response.containsKey("embedding")) {
                Object embeddingObj = response.get("embedding");
                if (embeddingObj instanceof java.util.List) {
                    java.util.List<Double> embeddingList = (java.util.List<Double>) embeddingObj;
                    return embeddingList.stream().mapToDouble(Double::doubleValue).toArray();
                }
            }
        } catch (Exception e) {
            log.error("[AiClient] Embedding API call failed: {}", e.getMessage());
            throw new RuntimeException("임베딩 API 호출 실패", e);
        }
        return null;
    }

}
