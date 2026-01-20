package kr.co.himedia.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import kr.co.himedia.dto.ai.*;
import kr.co.himedia.entity.*;
import kr.co.himedia.entity.DiagSession.DiagStatus;
import kr.co.himedia.entity.DiagSession.DiagTriggerType;
import kr.co.himedia.repository.*;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import java.util.stream.Collectors;
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
    private final KnowledgeService knowledgeService;
    private final ObdLogRepository obdLogRepository;
    private final VehicleRepository vehicleRepository;
    private final VehicleConsumableRepository vehicleConsumableRepository;
    private final DiagSessionRepository diagSessionRepository;
    private final DiagResultRepository diagResultRepository;
    private final AiClient aiClient;
    private final ObjectMapper objectMapper;

    private final FcmService fcmService;
    private final UserService userService;

    @Autowired
    public AiDiagnosisService(DtcHistoryRepository dtcHistoryRepository,
            RabbitTemplate rabbitTemplate,
            KnowledgeService knowledgeService,
            ObdLogRepository obdLogRepository,
            VehicleRepository vehicleRepository,
            VehicleConsumableRepository vehicleConsumableRepository,
            DiagSessionRepository diagSessionRepository,
            DiagResultRepository diagResultRepository,
            AiClient aiClient,
            ObjectMapper objectMapper,
            FcmService fcmService,
            UserService userService) {
        this.dtcHistoryRepository = dtcHistoryRepository;
        this.rabbitTemplate = rabbitTemplate;
        this.knowledgeService = knowledgeService;
        this.obdLogRepository = obdLogRepository;
        this.vehicleRepository = vehicleRepository;
        this.vehicleConsumableRepository = vehicleConsumableRepository;
        this.diagSessionRepository = diagSessionRepository;
        this.diagResultRepository = diagResultRepository;
        this.aiClient = aiClient;
        this.objectMapper = objectMapper;
        this.fcmService = fcmService;
        this.userService = userService;
    }

    @Value("${app.storage.type:local}")
    private String storageType;

    @Value("${ai.server.url.visual:http://localhost:8001/api/v1/connect/predict/visual}")
    private String aiServerVisualUrl;

    @Value("${ai.server.url.audio:http://localhost:8001/api/v1/connect/predict/audio}")
    private String aiServerAudioUrl;

    @Value("${ai.server.url.comprehensive:http://localhost:8001/api/v1/connect/predict/comprehensive}")
    private String aiServerUnifiedUrl;

    @Value("${ai.server.url.anomaly:http://localhost:8001/api/v1/connect/predict/anomaly}")
    private String aiServerAnomalyUrl;

    /**
     * DTC 이력 저장 및 즉시 AI 분석/알림 (비동기 아님 - 외부 API 포함)
     * RabbitMQ 제거 후 직접 호출로 변경
     */
    @Transactional
    public void processDtc(DtcDto dtcDto) {
        // 1. DTC 이력 저장
        DtcHistory history = DtcHistory.builder()
                .vehiclesId(UUID.fromString(dtcDto.getVehicleId()))
                .dtcCode(dtcDto.getDtcCode())
                .description(dtcDto.getDescription())
                .severity(dtcDto.getSeverity())
                .status(DtcHistory.DtcStatus.valueOf(dtcDto.getStatus()))
                .build();
        dtcHistoryRepository.save(history);
        log.info("Saved DTC History: {}", dtcDto.getDtcCode());

        // 2. RAG 및 FCM 알림 발송 (직접 호출)
        try {
            sendDtcNotification(dtcDto);
        } catch (Exception e) {
            log.error("Failed to send DTC notification", e);
            // 알림 실패가 Transaction 롤백을 유발하지 않도록 함 (선택 사항)
            // @Transactional이 걸려있으므로 RuntimeException은 롤백됨.
            // 알림만 실패하고 저장은 성공하게 하려면 try-catch 필수.
        }
    }

    private void sendDtcNotification(DtcDto dtcDto) {
        // 1. 차량 정보 및 소유주 확인
        UUID vehicleId = UUID.fromString(dtcDto.getVehicleId());
        Vehicle vehicle = vehicleRepository.findById(vehicleId)
                .orElseThrow(() -> new RuntimeException("Vehicle not found: " + vehicleId));

        String fcmToken = userService.getFcmToken(vehicle.getUserId());
        if (fcmToken == null) {
            log.info("No FCM token for user. Skip notification. UserID: {}", vehicle.getUserId());
            return;
        }

        // 2. RAG 지식 검색 (이미 번역/정제된 텍스트 가정)
        String query = dtcDto.getDtcCode() + " " + dtcDto.getDescription();
        List<String> searchResults = knowledgeService.searchKnowledge(query, 1);

        // RAG 결과가 있으면 그것을 '설명'으로 사용, 없으면 기본 설명 사용
        String explanation = searchResults.isEmpty() ? dtcDto.getDescription() : searchResults.get(0);

        // 3. 알림 메시지 구성 (최소한의 조립)
        String title = "차량 이상 감지";
        String body = dtcDto.getDtcCode() + ": " + explanation;

        // 4. TTS용 텍스트 (프론트엔드가 읽을 원문 그대로 전달)
        String ttsText = explanation;

        Map<String, String> data = new HashMap<>();
        data.put("type", "DTC_ALERT");
        data.put("dtcCode", dtcDto.getDtcCode());
        data.put("tts", ttsText);

        // 5. FCM 발송
        fcmService.sendMessage("User-" + vehicle.getUserId(), fcmToken, title, body, data);
    }

    /**
     * AI 진단 요청 (AiClient 사용)
     */
    public Object requestDiagnosis(DiagnosisRequestDto requestDto) {
        if ("VISION".equalsIgnoreCase(requestDto.getType())) {
            return aiClient.callVisualAnalysis(requestDto.getMediaUrl());
        } else {
            return aiClient.callAudioAnalysis(requestDto.getMediaUrl());
        }
    }

    /**
     * 통합 진단 요청 (Trigger 2: 수동 진단 - RabbitMQ 발행)
     * 기존 PENDING/FAILED 세션이 있으면 UPDATE, 없으면 INSERT
     */
    @Transactional
    public Map<String, Object> requestUnifiedDiagnosis(UnifiedDiagnosisRequestDto requestDto,
            org.springframework.web.multipart.MultipartFile image,
            org.springframework.web.multipart.MultipartFile audio) {
        log.info("Requesting Manual Unified Diagnosis (Async via MQ) for vehicle: {}", requestDto.getVehicleId());

        // 기존 PENDING 세션이 있으면 재사용
        DiagSession session = diagSessionRepository
                .findFirstByVehiclesIdAndTriggerTypeAndStatusOrderByCreatedAtDesc(
                        requestDto.getVehicleId(), DiagTriggerType.MANUAL, DiagStatus.PENDING)
                .orElseGet(() -> {
                    // PENDING이 없으면 FAILED도 확인
                    return diagSessionRepository
                            .findFirstByVehiclesIdAndTriggerTypeAndStatusOrderByCreatedAtDesc(
                                    requestDto.getVehicleId(), DiagTriggerType.MANUAL, DiagStatus.FAILED)
                            .orElse(null);
                });

        if (session != null) {
            log.info("Reusing existing session [{}] with status [{}]", session.getDiagSessionId(), session.getStatus());
            session.updateStatus(DiagStatus.PENDING, "진단 대기 중 (재요청)");
        } else {
            session = new DiagSession(requestDto.getVehicleId(), null, DiagTriggerType.MANUAL);
        }
        session = diagSessionRepository.save(session);

        String imageFile = saveMultipartFile(image, "visual");
        String audioFile = saveMultipartFile(audio, "audio");

        DiagnosisTaskMessage message = DiagnosisTaskMessage.builder()
                .sessionId(session.getDiagSessionId())
                .requestDto(requestDto)
                .imageFilename(imageFile)
                .audioFilename(audioFile)
                .build();

        rabbitTemplate.convertAndSend(kr.co.himedia.config.RabbitConfig.EXCHANGE_NAME,
                kr.co.himedia.config.RabbitConfig.ROUTING_KEY, message);

        return Map.of(
                "message", "진단 요청이 접수되었습니다. 분석 완료 후 결과가 업데이트됩니다.",
                "sessionId", session.getDiagSessionId(),
                "status", "ACCEPTED");
    }

    /**
     * 통합 진단 비동기 처리 (Trigger 1: 운행 종료 등 이벤트 기반 - RabbitMQ 발행)
     */
    public void requestUnifiedDiagnosisAsync(UnifiedDiagnosisRequestDto requestDto) {
        log.info("Requesting Auto Unified Diagnosis (Async via MQ) for vehicle: {}", requestDto.getVehicleId());

        DiagSession session = diagSessionRepository.save(new DiagSession(
                requestDto.getVehicleId(),
                requestDto.getTripId(),
                DiagTriggerType.ANOMALY));

        DiagnosisTaskMessage message = DiagnosisTaskMessage.builder()
                .sessionId(session.getDiagSessionId())
                .requestDto(requestDto)
                .build();

        rabbitTemplate.convertAndSend(kr.co.himedia.config.RabbitConfig.EXCHANGE_NAME,
                kr.co.himedia.config.RabbitConfig.ROUTING_KEY, message);
    }

    private String saveMultipartFile(org.springframework.web.multipart.MultipartFile file, String prefix) {
        if (file == null || file.isEmpty())
            return null;
        try {
            Path uploadsDir = Paths.get("uploads").toAbsolutePath();
            java.nio.file.Files.createDirectories(uploadsDir);
            String filename = prefix + "_" + System.currentTimeMillis() + "_" + file.getOriginalFilename();
            Path filePath = uploadsDir.resolve(filename);
            file.transferTo(filePath.toFile());
            return filename;
        } catch (Exception e) {
            log.error("Failed to save multipart file", e);
            throw new RuntimeException("파일 저장 실패", e);
        }
    }

    /**
     * 실제 분석 파이프라인 (컨슈머에서 호출)
     */
    public void processUnifiedFlow(DiagnosisTaskMessage taskMessage) {
        UUID sessionId = taskMessage.getSessionId();
        UnifiedDiagnosisRequestDto requestDto = taskMessage.getRequestDto();
        String imageFile = taskMessage.getImageFilename();
        String audioFile = taskMessage.getAudioFilename();

        DiagSession session = diagSessionRepository.findById(sessionId)
                .orElseThrow(() -> new RuntimeException("Session not found: " + sessionId));

        try {
            session.updateStatus(DiagStatus.PROCESSING, "[Step 1/5] 병렬 분석 시작 (이미지/음성/OBD)");
            diagSessionRepository.save(session);

            log.info("[Step 1/5] Parallel analysis starting [Session: {}]", sessionId);

            // 1. 병렬 분석 태스크 생성
            CompletableFuture<Map<String, Object>> visualTask = CompletableFuture.supplyAsync(() -> {
                if (imageFile != null) {
                    return aiClient.callVisualAnalysis(imageFile);
                }
                return requestDto.getVisualAnalysis();
            });

            CompletableFuture<Map<String, Object>> audioTask = CompletableFuture.supplyAsync(() -> {
                if (audioFile != null) {
                    return aiClient.callAudioAnalysis(audioFile);
                }
                return requestDto.getAudioAnalysis();
            });

            CompletableFuture<Map<String, Object>> anomalyTask = CompletableFuture.supplyAsync(() -> {
                return performAnomalyDetection(requestDto);
            });

            // 모든 결과 대기 (80초 타임아웃 - 개별 재시도는 AiClient에서 처리)
            try {
                CompletableFuture.allOf(visualTask, audioTask, anomalyTask).get(80, TimeUnit.SECONDS);
            } catch (Exception e) {
                log.error("[Timeout/Error] Parallel analysis failed or timed out", e);
                throw new RuntimeException("병렬 분석 작업 중 타임아웃 또는 에러 발생", e);
            }

            Map<String, Object> visualResult = visualTask.join();
            Map<String, Object> audioResult = audioTask.join();
            Map<String, Object> anomalyResult = anomalyTask.join();

            // 2. 통합 요청 객체 구축 및 RAG 검색
            session.updateStatus(DiagStatus.PROCESSING, "[Step 2/5] 분석 완료, 컨텍스트 취합 중...");
            diagSessionRepository.save(session);

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
                }
            }

            String query = searchQuery.toString().trim();
            if (!query.isEmpty()) {
                session.updateStatus(DiagStatus.PROCESSING, "[Step 3/5] RAG 지식 검색 수행 중");
                diagSessionRepository.save(session);
                log.info("[Step 3/5] RAG 검색 수행 (Query: '{}') [Session: {}]", query, sessionId);
                List<String> knowledgeResults = knowledgeService.searchKnowledge(query, 3);
                aiRequestBuilder.knowledgeData(knowledgeResults);
            }

            // 3. 최종 통합 진단 요청
            AiUnifiedRequestDto aiRequest = aiRequestBuilder.build();
            session.updateStatus(DiagStatus.PROCESSING, "[Step 4/5] AI 서버 최종 통합 진단 중");
            diagSessionRepository.save(session);

            log.info("[Step 4/5] AI 서버 최종 통합 진단 요청 [Session: {}]", sessionId);
            @SuppressWarnings("unchecked")
            Map<String, Object> finalResponse = aiClient
                    .callComprehensiveDiagnosis(objectMapper.convertValue(aiRequest, Map.class));

            // 4. 결과 저장
            saveDiagnosisResult(sessionId, finalResponse);
            session.updateStatus(DiagStatus.DONE, "[Step 5/5] 진단 완료 및 저장 성공");
            diagSessionRepository.save(session);

            log.info("[Step 5/5] AI 통합 진단 최종 완료 [Session: {}]", sessionId);

            // 5. FCM 알림 발송 (진단 완료)
            sendDiagnosisNotification(requestDto.getVehicleId(), sessionId);

        } catch (Exception e) {
            log.error("Unified Diagnosis Pipeline Failed [Session: {}]", sessionId, e);
            session.updateStatus(DiagStatus.FAILED, "진단 실패: " + e.getMessage());
            diagSessionRepository.save(session);
            throw new RuntimeException("진단 파이프라인 오류", e);
        }
    }

    private void sendDiagnosisNotification(UUID vehicleId, UUID sessionId) {
        try {
            vehicleRepository.findById(vehicleId).ifPresent(vehicle -> {
                String fcmToken = userService.getFcmToken(vehicle.getUserId());
                if (fcmToken != null) {
                    String title = "차량 정밀 진단 완료";
                    String body = "요청하신 차량의 AI 정밀 진단 분석이 완료되었습니다. 결과를 확인해보세요.";
                    Map<String, String> data = new HashMap<>();
                    data.put("type", "DIAG_COMPLETE");
                    data.put("sessionId", sessionId.toString());

                    fcmService.sendMessage("User-" + vehicle.getUserId(), fcmToken, title, body, data);
                    log.info("Sent Diagnosis Completion Notification [Vehicle: {}]", vehicleId);
                }
            });
        } catch (Exception e) {
            log.error("Failed to send diagnosis notification", e);
        }
    }

    private Map<String, Object> performAnomalyDetection(UnifiedDiagnosisRequestDto requestDto) {
        try {
            UUID vehicleId = requestDto.getVehicleId();
            List<Map<String, Object>> timeSeries;

            if (requestDto.getLstmAnalysis() != null && !requestDto.getLstmAnalysis().isEmpty()) {
                @SuppressWarnings("unchecked")
                List<Map<String, Object>> logs = (List<Map<String, Object>>) requestDto.getLstmAnalysis().get("logs");
                timeSeries = logs != null ? logs : List.of();
            } else {
                java.time.OffsetDateTime threeDaysAgo = java.time.OffsetDateTime.now(java.time.ZoneOffset.UTC)
                        .minusDays(3);
                java.time.OffsetDateTime now = java.time.OffsetDateTime.now(java.time.ZoneOffset.UTC);
                List<ObdLog> logs = obdLogRepository.findByVehicleIdAndTimeBetweenOrderByTimeAsc(vehicleId,
                        threeDaysAgo, now);

                if (logs.isEmpty()) {
                    return Map.of("is_anomaly", false, "reason", "no_obd_data");
                }

                timeSeries = logs.stream().limit(100).map(l -> {
                    Map<String, Object> point = new HashMap<>();
                    point.put("rpm", l.getRpm());
                    point.put("load", l.getEngineLoad() != null ? l.getEngineLoad() : 0.0);
                    point.put("coolant", l.getCoolantTemp() != null ? l.getCoolantTemp() : 0.0);
                    point.put("voltage", l.getVoltage() != null ? l.getVoltage() : 12.0); // Fixed: Use real voltage
                    return point;
                }).collect(Collectors.toList());
            }

            return aiClient.callAnomalyDetection(Map.of("time_series", timeSeries));
        } catch (Exception e) {
            log.warn("Anomaly detection failed, continuing with partial results", e);
            return Map.of("is_anomaly", false, "error", e.getMessage());
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
            log.error("Failed to save diagnosis result", e);
            throw new RuntimeException("DB 저장 실패", e);
        }
    }

    private void populateVehicleAndConsumableInfo(AiUnifiedRequestDto.AiUnifiedRequestDtoBuilder builder,
            UUID vehicleId) {
        vehicleRepository.findById(vehicleId).ifPresent(vehicle -> {
            Map<String, Object> vehicleInfo = new HashMap<>();
            vehicleInfo.put("manufacturer", vehicle.getManufacturer());
            vehicleInfo.put("model", vehicle.getModelName());
            vehicleInfo.put("year", vehicle.getModelYear());
            vehicleInfo.put("fuel_type", vehicle.getFuelType());
            vehicleInfo.put("total_mileage", vehicle.getTotalMileage());
            builder.vehicleInfo(vehicleInfo);

            List<VehicleConsumable> consumables = vehicleConsumableRepository.findByVehicleWithItem(vehicle);
            List<Map<String, Object>> statusList = consumables.stream().map(vc -> {
                Map<String, Object> status = new HashMap<>();
                status.put("item", vc.getConsumableItem().getCode());
                // WearFactor는 AI가 계산한 값 (이제 DB에 저장됨)
                status.put("wear_factor", vc.getWearFactor());
                status.put("remaining_life_pct", vc.getRemainingLife() != null ? vc.getRemainingLife() : 100.0);
                return status;
            }).collect(Collectors.toList());
            builder.consumablesStatus(statusList);
        });
    }

    // calculateRemainingLife 제거 (VehicleConsumable.currentLife 사용)
}
