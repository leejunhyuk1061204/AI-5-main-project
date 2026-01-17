package kr.co.himedia.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import kr.co.himedia.common.exception.BaseException;
import kr.co.himedia.common.exception.ErrorCode;
import kr.co.himedia.dto.ai.*;
import kr.co.himedia.entity.*;
import kr.co.himedia.entity.DiagSession.DiagStatus;
import kr.co.himedia.entity.DiagSession.DiagTriggerType;
import kr.co.himedia.repository.*;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.client.RestTemplate;

import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;

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
    private final VehicleRepository vehicleRepository;
    private final VehicleConsumableRepository vehicleConsumableRepository;
    private final DiagSessionRepository diagSessionRepository;
    private final DiagResultRepository diagResultRepository;
    private final ObjectMapper objectMapper;

    @Autowired
    public AiDiagnosisService(DtcHistoryRepository dtcHistoryRepository,
            RabbitTemplate rabbitTemplate,
            KnowledgeService knowledgeService,
            ObdLogRepository obdLogRepository,
            VehicleRepository vehicleRepository,
            VehicleConsumableRepository vehicleConsumableRepository,
            DiagSessionRepository diagSessionRepository,
            DiagResultRepository diagResultRepository,
            ObjectMapper objectMapper) {
        this.dtcHistoryRepository = dtcHistoryRepository;
        this.rabbitTemplate = rabbitTemplate;
        this.knowledgeService = knowledgeService;
        this.obdLogRepository = obdLogRepository;
        this.vehicleRepository = vehicleRepository;
        this.vehicleConsumableRepository = vehicleConsumableRepository;
        this.diagSessionRepository = diagSessionRepository;
        this.diagResultRepository = diagResultRepository;
        this.objectMapper = objectMapper;

        // Timeout 설정 추가 (Hang 방지)
        org.springframework.http.client.SimpleClientHttpRequestFactory factory = new org.springframework.http.client.SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(5000); // 5초
        factory.setReadTimeout(15000); // 15초
        this.restTemplate = new RestTemplate(factory);
    }

    @Value("${app.storage.type:local}")
    private String storageType;

    @Value("${ai.server.url.visual:http://localhost:8000/api/v1/test/predict/visual}")
    private String aiServerVisualUrl;

    @Value("${ai.server.url.audio:http://localhost:8000/api/v1/test/predict/audio}")
    private String aiServerAudioUrl;

    @Value("${ai.server.url.comprehensive:http://localhost:8000/api/v1/test/predict/comprehensive}")
    private String aiServerUnifiedUrl;

    @Value("${ai.server.url.anomaly:http://localhost:8000/api/v1/test/predict/anomaly}")
    private String aiServerAnomalyUrl;

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
     */
    @Transactional
    public Object requestUnifiedDiagnosis(UnifiedDiagnosisRequestDto requestDto,
            org.springframework.web.multipart.MultipartFile image,
            org.springframework.web.multipart.MultipartFile audio) {
        log.info("Starting Manual Unified Diagnosis for vehicle: {}", requestDto.getVehicleId());

        DiagSession session = diagSessionRepository.save(new DiagSession(
                requestDto.getVehicleId(),
                null, // Manual trigger might not have tripId in this context
                DiagTriggerType.MANUAL));

        return processUnifiedFlow(session, requestDto, image, audio);
    }

    /**
     * 통합 진단 비동기 처리 (Trigger 1: 운행 종료 등 이벤트 기반)
     */
    public void requestUnifiedDiagnosisAsync(UnifiedDiagnosisRequestDto requestDto) {
        log.info("Starting Async Unified Diagnosis for vehicle: {}", requestDto.getVehicleId());

        CompletableFuture.runAsync(() -> {
            try {
                DiagSession session = diagSessionRepository.save(new DiagSession(
                        requestDto.getVehicleId(),
                        null, // Needs tripId if available
                        DiagTriggerType.ANOMALY));

                processUnifiedFlow(session, requestDto, null, null);
            } catch (Exception e) {
                log.error("Async Unified Diagnosis Failed", e);
                throw new RuntimeException("비동기 통합 진단 실패", e);
            }
        });
    }

    private Object processUnifiedFlow(DiagSession session, UnifiedDiagnosisRequestDto requestDto,
            org.springframework.web.multipart.MultipartFile image,
            org.springframework.web.multipart.MultipartFile audio) {

        UUID sessionId = session.getDiagSessionId();
        try {
            session.updateStatus(DiagStatus.PROCESSING, "[Step 1/5] 병렬 분석 시작 (이미지/음성/OBD)");
            diagSessionRepository.save(session);

            log.info("[Step 1/5] 병렬 분석 시작 (이미지/음성/OBD) [Session: {}]", sessionId);
            CompletableFuture<Map<String, Object>> visualTask = CompletableFuture.supplyAsync(() -> {
                if (image != null && !image.isEmpty()) {
                    try {
                        Path uploadsDir = Paths.get("uploads").toAbsolutePath();
                        java.nio.file.Files.createDirectories(uploadsDir);
                        String filename = "visual_" + System.currentTimeMillis() + "_" + image.getOriginalFilename();
                        Path filePath = uploadsDir.resolve(filename);
                        image.transferTo(filePath.toFile());

                        log.info("[Async] Visual Analysis Started for file: {}", filename);
                        @SuppressWarnings("unchecked")
                        Map<String, Object> result = (Map<String, Object>) sendLocalFileRequest(aiServerVisualUrl,
                                filename);
                        log.info("[Async] Visual Analysis Completed: {}", result.getOrDefault("category", "N/A"));
                        return result;
                    } catch (Exception e) {
                        log.error("Visual Analysis Failed", e);
                        throw new RuntimeException("시각 분석 실패", e);
                    }
                }
                return requestDto.getVisualAnalysis();
            });

            CompletableFuture<Map<String, Object>> audioTask = CompletableFuture.supplyAsync(() -> {
                if (audio != null && !audio.isEmpty()) {
                    try {
                        Path uploadsDir = Paths.get("uploads").toAbsolutePath();
                        java.nio.file.Files.createDirectories(uploadsDir);
                        String filename = "audio_" + System.currentTimeMillis() + "_" + audio.getOriginalFilename();
                        Path filePath = uploadsDir.resolve(filename);
                        audio.transferTo(filePath.toFile());

                        log.info("[Async] Audio Analysis Started for file: {}", filename);
                        @SuppressWarnings("unchecked")
                        Map<String, Object> result = (Map<String, Object>) sendLocalFileRequest(aiServerAudioUrl,
                                filename);
                        log.info("[Async] Audio Analysis Completed: {}", result.getOrDefault("status", "N/A"));
                        return result;
                    } catch (Exception e) {
                        log.error("Audio Analysis Failed", e);
                        throw new RuntimeException("오디오 분석 실패", e);
                    }
                }
                return requestDto.getAudioAnalysis();
            });

            CompletableFuture<Map<String, Object>> anomalyTask = CompletableFuture.supplyAsync(() -> {
                try {
                    UUID vehicleId = requestDto.getVehicleId();
                    List<Map<String, Object>> timeSeries;
                    if (requestDto.getLstmAnalysis() != null && !requestDto.getLstmAnalysis().isEmpty()) {
                        @SuppressWarnings("unchecked")
                        List<Map<String, Object>> logs = (List<Map<String, Object>>) requestDto.getLstmAnalysis()
                                .get("logs");
                        timeSeries = logs != null ? logs : List.of();
                    } else {
                        java.time.OffsetDateTime threeDaysAgo = java.time.OffsetDateTime.now(java.time.ZoneOffset.UTC)
                                .minusDays(3);
                        java.time.OffsetDateTime now = java.time.OffsetDateTime.now(java.time.ZoneOffset.UTC);
                        List<ObdLog> logs = obdLogRepository.findByVehicleIdAndTimeBetweenOrderByTimeAsc(vehicleId,
                                threeDaysAgo, now);

                        if (logs.isEmpty()) {
                            log.warn("[Anomaly] No OBD logs found for vehicle: {}", vehicleId);
                            throw new BaseException(ErrorCode.INSUFFICIENT_DATA, "이상 탐지를 위한 OBD 데이터가 존재하지 않습니다.");
                        }

                        timeSeries = logs.stream().limit(100).map(l -> {
                            Map<String, Object> point = new HashMap<>();
                            point.put("rpm", l.getRpm());
                            point.put("load", l.getEngineLoad() != null ? l.getEngineLoad() : 0.0);
                            point.put("coolant", l.getCoolantTemp() != null ? l.getCoolantTemp() : 0.0);
                            point.put("voltage", l.getSpeed() != null ? l.getSpeed() / 10.0 : 12.0);
                            return point;
                        }).collect(Collectors.toList());
                    }

                    log.info("[Anomaly] Sending {} data points to anomaly detection", timeSeries.size());
                    Map<String, Object> anomalyRequest = Map.of("time_series", timeSeries);

                    @SuppressWarnings("unchecked")
                    Map<String, Object> response = restTemplate.postForObject(aiServerAnomalyUrl, anomalyRequest,
                            Map.class);

                    if (response != null) {
                        log.info("[Anomaly] Detection complete. is_anomaly={}, factors={}",
                                response.get("is_anomaly"), response.get("contributing_factors"));
                        return response;
                    }

                    throw new BaseException(ErrorCode.INTERNAL_SERVER_ERROR, "AI 분석 서버로부터 응답을 받을 수 없습니다.");
                } catch (BaseException e) {
                    throw e;
                } catch (Exception e) {
                    log.error("Anomaly detection failed", e);
                    throw new BaseException(ErrorCode.INTERNAL_SERVER_ERROR, "이상 탐지 분석 중 오류가 발생했습니다.");
                }
            });

            // 모든 분석 완료 대기 (60초 타임아웃 적용)
            try {
                CompletableFuture.allOf(visualTask, audioTask, anomalyTask).get(60, TimeUnit.SECONDS);
            } catch (Exception e) {
                log.error("[Timeout/Error] Parallel analysis failed or timed out", e);
                throw new RuntimeException("병렬 분석 작업 중 타임아웃 또는 에러가 발생했습니다.", e);
            }

            session.updateStatus(DiagStatus.PROCESSING, "[Step 2/5] 분석 완료, Context 취합 중...");
            diagSessionRepository.save(session);

            log.info("[Step 2/5] 분석 완료, Context 취합 중... [Session: {}]", sessionId);

            Map<String, Object> visualResult = visualTask.join();
            Map<String, Object> audioResult = audioTask.join();
            Map<String, Object> anomalyResult = anomalyTask.join();

            AiUnifiedRequestDto.AiUnifiedRequestDtoBuilder aiRequestBuilder = AiUnifiedRequestDto.builder()
                    .vehicleId(requestDto.getVehicleId())
                    .visualAnalysis(visualResult)
                    .audioAnalysis(audioResult)
                    .anomalyAnalysis(anomalyResult);

            populateVehicleAndConsumableInfo(aiRequestBuilder, requestDto.getVehicleId());

            StringBuilder searchQuery = new StringBuilder();
            if (visualResult != null && visualResult.containsKey("category")) {
                searchQuery.append(visualResult.get("category")).append(" ");
            }
            if (audioResult != null && audioResult.containsKey("status")) {
                searchQuery.append(audioResult.get("status")).append(" ");
            }
            if (anomalyResult != null && Boolean.TRUE.equals(anomalyResult.get("is_anomaly"))) {
                @SuppressWarnings("unchecked")
                List<String> factors = (List<String>) anomalyResult.get("contributing_factors");
                if (factors != null && !factors.isEmpty()) {
                    searchQuery.append(String.join(" ", factors)).append(" 이상징후");
                } else {
                    searchQuery.append("차량 이상징후");
                }
            }

            String query = searchQuery.toString().trim();
            if (!query.isEmpty()) {
                session.updateStatus(DiagStatus.PROCESSING, "[Step 3/5] RAG 지식 검색 수행 중");
                diagSessionRepository.save(session);

                log.info("[Step 3/5] RAG 지식 검색 수행 (Query: '{}') [Session: {}]", query, sessionId);
                java.util.List<String> knowledgeResults = knowledgeService.searchKnowledge(query, 3);
                if (knowledgeResults != null && !knowledgeResults.isEmpty()) {
                    aiRequestBuilder.knowledgeData(knowledgeResults);
                }
            }

            AiUnifiedRequestDto aiRequest = aiRequestBuilder.build();

            session.updateStatus(DiagStatus.PROCESSING, "[Step 4/5] AI 서버 최종 통합 진단 요청 중");
            diagSessionRepository.save(session);

            log.info("[Step 4/5] AI 서버 최종 통합 진단 요청 전송... [URL: {}]", aiServerUnifiedUrl);
            @SuppressWarnings("unchecked")
            Map<String, Object> response = (Map<String, Object>) restTemplate.postForObject(aiServerUnifiedUrl,
                    aiRequest, Map.class);

            saveDiagnosisResult(sessionId, response);
            session.updateStatus(DiagStatus.DONE, "[Step 5/5] 진단 완료 및 저장 성공");
            diagSessionRepository.save(session);

            String risk = (String) response.getOrDefault("risk_level", "UNKNOWN");
            log.info("[Step 5/5] AI 통합 진단 완료 및 DB 저장 성공! [Session: {}] [Risk: {}]", sessionId, risk);
            log.info(">>>> [Final Report Summary]: {}", response.get("report"));

            return response;
        } catch (Exception e) {
            log.error("Unified Diagnosis Flow Failed [Session: {}]", sessionId, e);
            session.updateStatus(DiagStatus.FAILED, "진단 실패: " + e.getMessage());
            diagSessionRepository.save(session);
            throw new RuntimeException("통합 진단 프로세스 실패: " + e.getMessage(), e);
        }
    }

    private void saveDiagnosisResult(UUID sessionId, Map<String, Object> response) {
        try {
            String finalReport = (String) response.getOrDefault("report", "진단 보고서 생성 실패");
            String riskStr = (String) response.getOrDefault("risk_level", "LOW");
            DiagResult.RiskLevel riskLevel = DiagResult.RiskLevel.valueOf(riskStr.toUpperCase());

            Object issuesObj = response.get("detected_issues");
            Object actionsObj = response.get("recommended_actions");

            DiagResult result = DiagResult.builder()
                    .diagSessionId(sessionId)
                    .finalReport(finalReport)
                    .riskLevel(riskLevel)
                    .detectedIssues(objectMapper.writeValueAsString(issuesObj))
                    .actionsJson(objectMapper.writeValueAsString(actionsObj))
                    .build();

            diagResultRepository.save(result);
        } catch (Exception e) {
            log.error("Failed to save diagnosis result to DB", e);
            throw new RuntimeException("진단 결과 DB 저장 실패", e);
        }
    }

    private void populateVehicleAndConsumableInfo(AiUnifiedRequestDto.AiUnifiedRequestDtoBuilder builder,
            UUID vehicleId) {
        try {
            vehicleRepository.findById(vehicleId).ifPresent(vehicle -> {
                Map<String, Object> vehicleInfo = new HashMap<>();
                vehicleInfo.put("manufacturer", vehicle.getManufacturer());
                vehicleInfo.put("model", vehicle.getModelName());
                vehicleInfo.put("year", vehicle.getModelYear());
                vehicleInfo.put("fuel_type", vehicle.getFuelType());
                if (vehicle.getTotalMileage() != null) {
                    vehicleInfo.put("total_mileage", vehicle.getTotalMileage());
                }
                builder.vehicleInfo(vehicleInfo);

                List<VehicleConsumable> consumables = vehicleConsumableRepository.findByVehicle(vehicle);
                List<Map<String, Object>> consumablesStatus = new ArrayList<>();

                for (VehicleConsumable vc : consumables) {
                    Map<String, Object> status = new HashMap<>();
                    status.put("item", vc.getItem());
                    status.put("wear_factor", vc.getWearFactor());

                    // 잔여 수명 계산
                    Double remainingLifePct = calculateRemainingLife(vehicle.getTotalMileage(), vc);
                    status.put("remaining_life_pct", remainingLifePct);

                    consumablesStatus.add(status);
                }
                if (!consumablesStatus.isEmpty()) {
                    builder.consumablesStatus(consumablesStatus);
                }
                log.info("Populated vehicle and consumables info for diagnosis. Vehicle: {}", vehicle.getModelName());
            });
        } catch (Exception e) {
            log.error("Failed to populate vehicle/consumable info", e);
            // 진단 자체는 중단하지 않음
        }
    }

    private Double calculateRemainingLife(Double currentMileage, VehicleConsumable vc) {
        try {
            Double mileageLife = null;
            if (currentMileage != null && vc.getLastMaintenanceMileage() != null
                    && vc.getReplacementIntervalMileage() != null) {
                double usedMileage = currentMileage - vc.getLastMaintenanceMileage();
                mileageLife = 100.0 - (usedMileage / vc.getReplacementIntervalMileage() * 100.0);
            }

            Double timeLife = null;
            if (vc.getLastMaintenanceDate() != null && vc.getReplacementIntervalMonths() != null) {
                long monthsPassed = ChronoUnit.MONTHS.between(vc.getLastMaintenanceDate(), LocalDate.now());
                timeLife = 100.0 - ((double) monthsPassed / vc.getReplacementIntervalMonths() * 100.0);
            }

            if (mileageLife != null && timeLife != null) {
                return Math.max(0.0, Math.min(mileageLife, timeLife));
            } else if (mileageLife != null) {
                return Math.max(0.0, mileageLife);
            } else if (timeLife != null) {
                return Math.max(0.0, timeLife);
            }
        } catch (Exception e) {
            log.warn("Failed to calculate remaining life for item: {}", vc.getItem());
        }
        return null;
    }

    private Object sendLocalFileRequest(String url, String filename) {
        try {
            // uploads 폴더의 파일 URL을 AI 서버에 전송
            // AI 서버가 이 URL에서 파일을 다운로드함
            String fileUrl = "http://localhost:8080/uploads/" + filename;

            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);

            Map<String, String> body = new HashMap<>();
            body.put("file_url", fileUrl);

            HttpEntity<Map<String, String>> requestEntity = new HttpEntity<>(body, headers);
            log.info("Sending file URL to AI server: {}", fileUrl);
            return restTemplate.postForObject(url, requestEntity, Map.class);
        } catch (Exception e) {
            log.error("Failed to send file URL request", e);
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
