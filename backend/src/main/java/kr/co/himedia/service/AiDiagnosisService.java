package kr.co.himedia.service;

import kr.co.himedia.dto.ai.AiUnifiedRequestDto;
import kr.co.himedia.dto.ai.DiagnosisRequestDto;
import kr.co.himedia.dto.ai.DtcDto;
import kr.co.himedia.dto.ai.UnifiedDiagnosisRequestDto;
import kr.co.himedia.entity.DtcHistory;
import kr.co.himedia.entity.ObdLog;
import kr.co.himedia.repository.DtcHistoryRepository;
import kr.co.himedia.repository.ObdLogRepository;
import kr.co.himedia.repository.TripSummaryRepository;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.FileSystemResource;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestTemplate;

import java.io.File;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.stream.Collectors;

/**
 * AI 진단 및 DTC 처리 서비스
 * Hybrid Request Logic 포함 (Local: Multipart, S3: JSON)
 */
@Slf4j
@Service
public class AiDiagnosisService {

    private final DtcHistoryRepository dtcHistoryRepository;
    private final RabbitTemplate rabbitTemplate;
    private final RestTemplate restTemplate;
    private final KnowledgeService knowledgeService;
    private final ObdLogRepository obdLogRepository;
    private final TripSummaryRepository tripSummaryRepository;

    @Autowired
    public AiDiagnosisService(DtcHistoryRepository dtcHistoryRepository,
            RabbitTemplate rabbitTemplate,
            KnowledgeService knowledgeService,
            ObdLogRepository obdLogRepository,
            TripSummaryRepository tripSummaryRepository) {
        this.dtcHistoryRepository = dtcHistoryRepository;
        this.rabbitTemplate = rabbitTemplate;
        this.knowledgeService = knowledgeService;
        this.obdLogRepository = obdLogRepository;
        this.tripSummaryRepository = tripSummaryRepository;

        // Timeout 설정 추가 (Hang 방지)
        org.springframework.http.client.SimpleClientHttpRequestFactory factory = new org.springframework.http.client.SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(5000); // 5초
        factory.setReadTimeout(15000); // 15초
        this.restTemplate = new RestTemplate(factory);
    }

    @Value("${app.storage.type:local}")
    private String storageType;

    @Value("${ai.server.url.visual:http://localhost:8000/api/v1/predict/vision}")
    private String aiServerVisualUrl;

    @Value("${ai.server.url.audio:http://localhost:8000/api/v1/predict/audio}")
    private String aiServerAudioUrl;

    @Value("${ai.server.url.comprehensive:http://localhost:8000/api/v1/test/predict/comprehensive}")
    private String aiServerUnifiedUrl;

    /**
     * DTC 이력 저장 및 AI 분석 이벤트 발행
     */
    @Transactional
    public void processDtc(DtcDto dtcDto) {
        DtcHistory history = DtcHistory.builder()
                .vehiclesId(UUID.fromString(dtcDto.getVehicleId()))
                .dtcCode(dtcDto.getDtcCode())
                .description(dtcDto.getDescription())
                .severity(dtcDto.getSeverity())
                .status(DtcHistory.DtcStatus.valueOf(dtcDto.getStatus()))
                .build();
        dtcHistoryRepository.save(history);

        rabbitTemplate.convertAndSend("car-sentry.exchange", "ai.diagnosis.dtc", dtcDto);
        log.info("Published DTC event to RabbitMQ: {}", dtcDto.getDtcCode());
    }

    /**
     * AI 진단 요청 (동기/비동기 혼합 가능)
     */
    public Object requestDiagnosis(DiagnosisRequestDto requestDto) {
        if ("local".equalsIgnoreCase(storageType)) {
            String targetUrl = "VISION".equalsIgnoreCase(requestDto.getType())
                    ? "http://localhost:8000/api/v1/test/predict/visual"
                    : "http://localhost:8000/api/v1/test/predict/audio";
            return sendLocalFileRequest(targetUrl, requestDto.getMediaUrl());
        } else {
            String targetUrl = "VISION".equalsIgnoreCase(requestDto.getType()) ? aiServerVisualUrl : aiServerAudioUrl;
            return sendS3UrlRequest(targetUrl, requestDto.getMediaUrl(), requestDto.getType());
        }
    }

    /**
     * 통합 진단 요청 (Trigger 2: 수동 진단 실시간 응답용)
     * Multipart로 받은 파일들을 분석하고, LSTM 데이터와 결합하여 통합 진단 수행
     */
    public Object requestUnifiedDiagnosis(UnifiedDiagnosisRequestDto requestDto,
            org.springframework.web.multipart.MultipartFile image,
            org.springframework.web.multipart.MultipartFile audio) {
        log.info("Starting Manual Unified Diagnosis for vehicle: {}", requestDto.getVehicleId());
        return processUnifiedFlow(requestDto, image, audio);
    }

    /**
     * 통합 진단 비동기 처리 (Trigger 1: 운행 종료 등 이벤트 기반)
     */
    public void requestUnifiedDiagnosisAsync(UnifiedDiagnosisRequestDto requestDto) {
        log.info("Starting Async Unified Diagnosis for vehicle: {}", requestDto.getVehicleId());

        CompletableFuture.runAsync(() -> {
            try {
                // Async Trigger의 경우 파일이 없을 수 있음 (null 전달)
                processUnifiedFlow(requestDto, null, null);
                log.info("Async Unified Diagnosis Completed for vehicle: {}", requestDto.getVehicleId());
            } catch (Exception e) {
                log.error("Async Unified Diagnosis Failed", e);
            }
        });
    }

    private Object processUnifiedFlow(UnifiedDiagnosisRequestDto requestDto,
            org.springframework.web.multipart.MultipartFile image,
            org.springframework.web.multipart.MultipartFile audio) {
        log.info("Processing Unified Flow for vehicle: {}", requestDto.getVehicleId());

        // 1. 병렬 분석 요청 (Step 1)
        CompletableFuture<Map<String, Object>> visualTask = CompletableFuture.supplyAsync(() -> {
            if (image != null && !image.isEmpty()) {
                try {
                    File tempFile = File.createTempFile("visual_", "_" + image.getOriginalFilename());
                    image.transferTo(tempFile);
                    log.info("[Async] Visual Analysis Started");
                    @SuppressWarnings("unchecked")
                    Map<String, Object> result = (Map<String, Object>) sendLocalFileRequest(aiServerVisualUrl,
                            tempFile.getAbsolutePath());
                    tempFile.delete();
                    return result;
                } catch (Exception e) {
                    log.error("Visual Analysis Failed", e);
                    return Map.of("error", e.getMessage());
                }
            }
            return requestDto.getVisualAnalysis();
        });

        CompletableFuture<Map<String, Object>> audioTask = CompletableFuture.supplyAsync(() -> {
            if (audio != null && !audio.isEmpty()) {
                try {
                    File tempFile = File.createTempFile("audio_", "_" + audio.getOriginalFilename());
                    audio.transferTo(tempFile);
                    log.info("[Async] Audio Analysis Started");
                    @SuppressWarnings("unchecked")
                    Map<String, Object> result = (Map<String, Object>) sendLocalFileRequest(aiServerAudioUrl,
                            tempFile.getAbsolutePath());
                    tempFile.delete();
                    return result;
                } catch (Exception e) {
                    log.error("Audio Analysis Failed", e);
                    return Map.of("error", e.getMessage());
                }
            }
            return requestDto.getAudioAnalysis();
        });

        // 2. OBD 데이터 조회 (Fallback Logic: 최근 3일 데이터 없으면 TripSummary 사용)
        CompletableFuture<Map<String, Object>> lstmTask = CompletableFuture.supplyAsync(() -> {
            if (requestDto.getLstmAnalysis() != null && !requestDto.getLstmAnalysis().isEmpty()) {
                return requestDto.getLstmAnalysis();
            }

            try {
                UUID vehicleId = UUID.fromString(requestDto.getVehicleId());
                java.time.OffsetDateTime treeDaysAgo = java.time.OffsetDateTime.now(java.time.ZoneOffset.UTC)
                        .minusDays(3);
                java.time.OffsetDateTime now = java.time.OffsetDateTime.now(java.time.ZoneOffset.UTC);

                List<ObdLog> logs = obdLogRepository.findByVehicleIdAndTimeBetweenOrderByTimeAsc(vehicleId, treeDaysAgo,
                        now);

                if (!logs.isEmpty()) {
                    log.info("[LSTM] Found {} logs for the last 3 days.", logs.size());
                    Map<String, Object> result = new HashMap<>();
                    result.put("is_anomaly", false);
                    result.put("data_source", "OBD_LOGS");
                    result.put("logCount", logs.size());
                    result.put("logs", logs.stream().limit(100).map(l -> Map.of(
                            "time", l.getTime().toString(),
                            "rpm", l.getRpm(),
                            "speed", l.getSpeed())).collect(Collectors.toList()));
                    return result;
                }

                // Fallback: TripSummary 사용
                return tripSummaryRepository.findLatestTripByVehicleId(vehicleId)
                        .map(ts -> {
                            log.info("[Fallback] OBD data absent. Using latest TripSummary.");
                            Map<String, Object> result = new HashMap<>();
                            result.put("is_anomaly", false);
                            result.put("data_source", "TRIP_SUMMARY");
                            result.put("distance", ts.getDistance() != null ? ts.getDistance() : 0.0);
                            result.put("avgSpeed", ts.getAverageSpeed() != null ? ts.getAverageSpeed() : 0.0);
                            result.put("topSpeed", ts.getTopSpeed() != null ? ts.getTopSpeed() : 0.0);
                            result.put("score", ts.getDriveScore() != null ? ts.getDriveScore() : 100);
                            return result;
                        })
                        .orElseGet(() -> {
                            Map<String, Object> result = new HashMap<>();
                            result.put("is_anomaly", false);
                            result.put("data_source", "NONE");
                            result.put("message", "최근 주행 데이터가 전혀 없습니다.");
                            return result;
                        });
            } catch (Exception e) {
                log.error("LSTM data preparation failed", e);
                return Map.of("error", e.getMessage());
            }
        });

        // 모든 분석 완료 대기
        CompletableFuture.allOf(visualTask, audioTask, lstmTask).join();

        Map<String, Object> visualResult = visualTask.join();
        Map<String, Object> audioResult = audioTask.join();
        Map<String, Object> lstmResult = lstmTask.join();

        // 3. 결과 취합 및 RAG 검색 (Step 2)
        AiUnifiedRequestDto.AiUnifiedRequestDtoBuilder aiRequestBuilder = AiUnifiedRequestDto.builder()
                .vehicleId(requestDto.getVehicleId())
                .visualAnalysis(visualResult)
                .audioAnalysis(audioResult)
                .lstmAnalysis(lstmResult);

        try {
            StringBuilder searchQuery = new StringBuilder();
            if (visualResult != null && visualResult.containsKey("category")) {
                searchQuery.append(visualResult.get("category")).append(" ");
            }
            if (audioResult != null && audioResult.containsKey("status")) {
                searchQuery.append(audioResult.get("status")).append(" ");
            }
            if (lstmResult != null && Boolean.TRUE.equals(lstmResult.get("is_anomaly"))) {
                searchQuery.append("이상징후 ");
            }

            String query = searchQuery.toString().trim();
            if (!query.isEmpty()) {
                log.info("[RAG] 검색 수행: Query='{}'", query);
                java.util.List<String> knowledgeResults = knowledgeService.searchKnowledge(query, 3);
                aiRequestBuilder.knowledgeData(knowledgeResults);
            }
        } catch (Exception e) {
            log.warn("[RAG] 지식 검색 실패: {}", e.getMessage());
        }

        AiUnifiedRequestDto aiRequest = aiRequestBuilder.build();

        // 4. 최종 진단 요청 (Step 3)
        try {
            log.info("[Final] Sending Unified Request to AI Server: {}", aiServerUnifiedUrl);
            return restTemplate.postForObject(aiServerUnifiedUrl, aiRequest, Map.class);
        } catch (Exception e) {
            log.error("Failed to send aggregated diagnosis dataset", e);
            throw new RuntimeException("AI 서버 통합 진단 요청 실패: " + e.getMessage(), e);
        }
    }

    private Object sendLocalFileRequest(String url, String localFileUrl) {
        try {
            String filename = localFileUrl.substring(localFileUrl.lastIndexOf("/") + 1);
            Path filePath = Paths.get("uploads").resolve(filename).toAbsolutePath();
            File file = filePath.toFile();

            if (!file.exists()) {
                throw new RuntimeException("File not found locally: " + filePath);
            }

            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.MULTIPART_FORM_DATA);

            MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();
            body.add("file", new FileSystemResource(file));

            HttpEntity<MultiValueMap<String, Object>> requestEntity = new HttpEntity<>(body, headers);
            return restTemplate.postForObject(url, requestEntity, Map.class);
        } catch (Exception e) {
            log.error("Failed to send local file request", e);
            throw new RuntimeException("AI Server Request Failed (Local)", e);
        }
    }

    private Object sendS3UrlRequest(String url, String mediaUrl, String type) {
        try {
            Map<String, String> body = new HashMap<>();
            if ("VISION".equalsIgnoreCase(type)) {
                body.put("imageUrl", mediaUrl);
            } else {
                body.put("audioUrl", mediaUrl);
            }
            return restTemplate.postForObject(url, body, Map.class);
        } catch (Exception e) {
            log.error("Failed to send S3 URL request", e);
            throw new RuntimeException("AI Server Request Failed (S3)", e);
        }
    }
}
