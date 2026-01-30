package kr.co.himedia.service;

import kr.co.himedia.common.exception.BaseException;
import kr.co.himedia.common.exception.ErrorCode;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.FileSystemResource;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.retry.annotation.Backoff;
import org.springframework.retry.annotation.Retryable;
import org.springframework.stereotype.Component;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestTemplate;

import kr.co.himedia.dto.maintenance.ai.AiWearFactorRequest;
import kr.co.himedia.dto.maintenance.ai.AiWearFactorResponse;

import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Map;

/**
 * AI 서버와의 개별 API 통신을 전담하는 컴포넌트입니다.
 * 각 메서드에는 @Retryable이 적용되어 일시적인 네트워크 오류 시 자동 재시도합니다.
 */
@Slf4j
@Component
public class AiClient {

    private final RestTemplate restTemplate;

    @Value("${ai.server.url.visual:http://localhost:8001/api/v1/connect/predict/visual}")
    private String aiServerVisualUrl;

    @Value("${ai.server.url.audio:http://localhost:8001/api/v1/connect/predict/audio}")
    private String aiServerAudioUrl;

    @Value("${ai.server.url.comprehensive:http://localhost:8001/api/v1/connect/predict/comprehensive}")
    private String aiServerUnifiedUrl;

    @Value("${ai.server.url.anomaly:http://localhost:8001/api/v1/connect/predict/anomaly}")
    private String aiServerAnomalyUrl;

    @Value("${ai.server.url.wear-factor:http://localhost:8001/api/v1/connect/predict/wear-factor}")
    private String aiServerWearFactorUrl;

    public AiClient() {
        org.springframework.http.client.SimpleClientHttpRequestFactory factory = new org.springframework.http.client.SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(5000);
        factory.setReadTimeout(300000); // 15분 단위 청크 데이터 처리 등 긴 분석 시간을 고려하여 5분으로 상향
        this.restTemplate = new RestTemplate(factory);
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

            @SuppressWarnings("unchecked")
            Map<String, Object> result = restTemplate.postForObject(aiServerVisualUrl, request, Map.class);
            return result;
        } catch (Exception e) {
            log.error("[AiClient] Visual Analysis Failed [Vehicle: {}, Session: {}]. URL: {}, Error: {}",
                    vehicleId, sessionId, aiServerVisualUrl, e.getMessage());
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

            @SuppressWarnings("unchecked")
            Map<String, Object> result = restTemplate.postForObject(aiServerAudioUrl, request, Map.class);
            return result;
        } catch (Exception e) {
            log.error("[AiClient] Audio Analysis Failed [Vehicle: {}, Session: {}]. URL: {}, Error: {}",
                    vehicleId, sessionId, aiServerAudioUrl, e.getMessage());
            throw e;
        }
    }

    @Retryable(retryFor = Exception.class, maxAttempts = 2, backoff = @Backoff(delay = 3000))
    public Map<String, Object> callAnomalyDetection(Map<String, Object> request) {
        log.info("[Retryable] Requesting Anomaly Detection");
        @SuppressWarnings("unchecked")
        Map<String, Object> result = (Map<String, Object>) restTemplate.postForObject(aiServerAnomalyUrl, request,
                Map.class);
        return result;
    }

    @Retryable(retryFor = Exception.class, maxAttempts = 2, backoff = @Backoff(delay = 5000))
    public Map<String, Object> callComprehensiveDiagnosis(Map<String, Object> request) {
        log.info("[Retryable] Requesting Comprehensive Diagnosis");
        try {
            @SuppressWarnings("unchecked")
            Map<String, Object> result = (Map<String, Object>) restTemplate.postForObject(aiServerUnifiedUrl, request,
                    Map.class);
            return result;
        } catch (Exception e) {
            log.error("[AiClient] Comprehensive Diagnosis Failed. URL: {}, Error: {}", aiServerUnifiedUrl,
                    e.getMessage());
            throw e;
        }
    }

    /**
     * 소모품 마모율 예측 요청
     */
    @Retryable(retryFor = Exception.class, maxAttempts = 2, backoff = @Backoff(delay = 2000))
    public AiWearFactorResponse getWearFactor(AiWearFactorRequest request) {
        log.info("[Retryable] Requesting Batch Wear Factor Prediction");
        return restTemplate.postForObject(aiServerWearFactorUrl, request, AiWearFactorResponse.class);
    }
}
