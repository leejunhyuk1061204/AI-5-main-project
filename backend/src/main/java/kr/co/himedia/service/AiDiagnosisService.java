package kr.co.himedia.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import kr.co.himedia.domain.DiagAction;
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
    private final AiEvidenceRepository aiEvidenceRepository;
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
            AiEvidenceRepository aiEvidenceRepository,
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
        this.aiEvidenceRepository = aiEvidenceRepository;
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
                .messageType(DiagnosisTaskMessage.MessageType.INITIAL)
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
                .messageType(DiagnosisTaskMessage.MessageType.INITIAL)
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
        DiagSession session = diagSessionRepository.findById(sessionId)
                .orElseThrow(() -> new RuntimeException("Session not found: " + sessionId));

        try {
            // [Branch] Initial Diagnosis vs Reply Diagnosis
            if (taskMessage.getMessageType() == DiagnosisTaskMessage.MessageType.REPLY) {
                processReplyPhase(taskMessage, session);
            } else {
                processInitialPhase(taskMessage, session);
            }
        } catch (Exception e) {
            log.error("Unified Diagnosis Pipeline Failed [Session: {}]", sessionId, e);
            session.updateStatus(DiagStatus.FAILED, "진단 실패: " + e.getMessage());
            diagSessionRepository.save(session);
            throw new RuntimeException("진단 파이프라인 오류", e);
        }
    }

    private void processInitialPhase(DiagnosisTaskMessage taskMessage, DiagSession session) throws Exception {
        UUID sessionId = session.getDiagSessionId();
        UnifiedDiagnosisRequestDto requestDto = taskMessage.getRequestDto();
        String imageFile = taskMessage.getImageFilename();
        String audioFile = taskMessage.getAudioFilename();

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

        // 모든 결과 대기
        CompletableFuture.allOf(visualTask, audioTask, anomalyTask).get(80, TimeUnit.SECONDS);

        Map<String, Object> visualResult = visualTask.join();
        Map<String, Object> audioResult = audioTask.join();
        Map<String, Object> anomalyResult = anomalyTask.join();

        // 2. 통합 요청 객체 구축 및 RAG 검색
        AiUnifiedRequestDto.AiUnifiedRequestDtoBuilder aiRequestBuilder = AiUnifiedRequestDto.builder()
                .visualAnalysis(visualResult)
                .audioAnalysis(audioResult)
                .anomalyAnalysis(anomalyResult);

        populateVehicleAndConsumableInfo(aiRequestBuilder, requestDto.getVehicleId());

        String query = buildSearchQuery(visualResult, audioResult, anomalyResult);
        if (!query.isEmpty()) {
            List<String> knowledgeResults = knowledgeService.searchKnowledge(query, 3);
            aiRequestBuilder.knowledgeData(knowledgeResults);
        }

        // 3. 최종 통합 진단 요청 (Phase 1: 6대 항목)
        AiUnifiedRequestDto aiRequest = aiRequestBuilder.build();
        @SuppressWarnings("unchecked")
        Map<String, Object> finalResponse = aiClient
                .callComprehensiveDiagnosis(objectMapper.convertValue(aiRequest, Map.class));

        // 4. 결과 저장 및 상태 결정
        DiagStatus finalStatus = saveDiagnosisResult(sessionId, finalResponse, imageFile, audioFile, visualResult,
                audioResult);
        session.updateStatus(finalStatus, finalStatus == DiagStatus.DONE ? "[Step 5/5] 진단 완료 및 저장 성공"
                : "[Step 5/5] 추가 정보 요청됨 (ACTION_REQUIRED)");
        diagSessionRepository.save(session);

        // 5. 알림 발송
        String responseMode = (String) finalResponse.getOrDefault("response_mode", "REPORT");
        sendDiagnosisNotification(requestDto.getVehicleId(), sessionId, responseMode);
    }

    private void processReplyPhase(DiagnosisTaskMessage taskMessage, DiagSession session) throws Exception {
        UUID sessionId = session.getDiagSessionId();
        ReplyRequestDto replyDto = taskMessage.getReplyRequest();
        String imageFile = taskMessage.getImageFilename();
        String audioFile = taskMessage.getAudioFilename();

        session.updateStatus(DiagStatus.REPLY_PROCESSING, "[Chat] AI가 답변을 분석 중입니다...");
        diagSessionRepository.save(session);

        DiagResult existingResult = diagResultRepository.findByDiagSessionId(sessionId)
                .orElseThrow(() -> new RuntimeException("DiagResult not found for session: " + sessionId));

        // 1. 기존 대화 이력 파싱
        List<Map<String, Object>> conversation = new ArrayList<>();
        if (existingResult.getInteractiveJson() != null) {
            Map<String, Object> interactiveData = objectMapper.readValue(existingResult.getInteractiveJson(),
                    Map.class);
            List<Map<String, Object>> existingConv = (List<Map<String, Object>>) interactiveData.get("conversation");
            if (existingConv != null)
                conversation.addAll(existingConv);

            String aiMessage = (String) interactiveData.get("message");
            if (aiMessage != null) {
                Map<String, Object> aiTurn = new HashMap<>();
                aiTurn.put("role", "ai");
                aiTurn.put("content", aiMessage);
                aiTurn.put("timestamp", java.time.LocalDateTime.now().toString());
                conversation.add(aiTurn);
            }
        }

        // 2. 추가 미디어 분석 (YOLO/AST)
        Map<String, Object> visualResult = null;
        if (imageFile != null) {
            visualResult = aiClient.callVisualAnalysis(imageFile);
            saveEvidences(sessionId, imageFile, null, visualResult, null);
        }

        Map<String, Object> audioResult = null;
        if (audioFile != null) {
            audioResult = aiClient.callAudioAnalysis(audioFile);
            saveEvidences(sessionId, null, audioFile, null, audioResult);
        }

        // 3. 사용자 답변 및 미디어 분석 결과 합쳐서 이력 추가
        Map<String, Object> userTurn = new HashMap<>();
        userTurn.put("role", "user");
        userTurn.put("content", replyDto != null ? replyDto.getUserResponse() : "[Media Received]");
        userTurn.put("timestamp", java.time.LocalDateTime.now().toString());

        List<Map<String, Object>> mediaRefs = new ArrayList<>();
        if (visualResult != null) {
            mediaRefs.add(Map.of("type", "IMAGE", "analysis", visualResult.get("category")));
        }
        if (audioResult != null) {
            mediaRefs.add(Map.of("type", "AUDIO", "analysis", audioResult.get("status")));
        }
        if (!mediaRefs.isEmpty()) {
            userTurn.put("media_refs", mediaRefs);
        }
        conversation.add(userTurn);

        // 4. GPT 요청 (Phase 2: 7대 항목)
        AiUnifiedRequestDto.AiUnifiedRequestDtoBuilder aiRequestBuilder = AiUnifiedRequestDto.builder()
                .conversationHistory(conversation);

        populateVehicleAndConsumableInfo(aiRequestBuilder, session.getVehiclesId());
        // 필요 시 신규 분석 결과도 최상위에 포함
        if (visualResult != null)
            aiRequestBuilder.visualAnalysis(visualResult);
        if (audioResult != null)
            aiRequestBuilder.audioAnalysis(audioResult);

        @SuppressWarnings("unchecked")
        Map<String, Object> aiResponse = aiClient
                .callComprehensiveDiagnosis(objectMapper.convertValue(aiRequestBuilder.build(), Map.class));

        // 5. 결과 저장 및 상태 업데이트
        long userTurnCount = conversation.stream().filter(t -> "user".equals(t.get("role"))).count();
        log.info("[Reply] User Turn Count: {}", userTurnCount);

        String effectiveMode = updateReplyResult(sessionId, aiResponse, conversation, userTurnCount, existingResult);

        DiagStatus finalStatus = "REPORT".equalsIgnoreCase(effectiveMode) ? DiagStatus.DONE
                : DiagStatus.ACTION_REQUIRED;
        session.updateStatus(finalStatus, finalStatus == DiagStatus.DONE ? "최종 진단 리포트가 생성되었습니다." : "추가 정보를 기다리고 있습니다.");
        diagSessionRepository.save(session);

        // 6. 알림 발송
        sendDiagnosisNotification(session.getVehiclesId(), sessionId, effectiveMode);
    }

    private String buildSearchQuery(Map<String, Object> visualResult, Map<String, Object> audioResult,
            Map<String, Object> anomalyResult) {
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
        return searchQuery.toString().trim();
    }

    private String updateReplyResult(UUID sessionId, Map<String, Object> aiResponse,
            List<Map<String, Object>> conversation, long userTurnCount, DiagResult existingResult) throws Exception {
        String mode = (String) aiResponse.getOrDefault("response_mode", "REPORT");
        boolean forceReport = userTurnCount >= 3 && "INTERACTIVE".equalsIgnoreCase(mode);

        if (forceReport) {
            log.info("[Reply] Force switching to REPORT mode (Turns: {})", userTurnCount);
            mode = "REPORT";
        }

        diagResultRepository.delete(existingResult);
        DiagResult.DiagResultBuilder resultBuilder = DiagResult.builder()
                .diagSessionId(sessionId)
                .responseMode(mode)
                .confidenceLevel((String) aiResponse.getOrDefault("confidence_level", "LOW"))
                .summary((String) aiResponse.getOrDefault("summary", ""));

        if (aiResponse.containsKey("requested_actions") && aiResponse.get("requested_actions") != null) {
            @SuppressWarnings("unchecked")
            List<String> actions = (List<String>) aiResponse.get("requested_actions");
            if (!actions.isEmpty()) {
                try {
                    resultBuilder.requestedAction(DiagAction.valueOf(actions.get(0).toUpperCase()));
                } catch (Exception e) {
                    log.warn("[Reply] Unknown action requested: {}", actions.get(0));
                }
            }
        }

        if ("REPORT".equalsIgnoreCase(mode)) {
            // ... (기존 REPORT 저장 로직과 동일하거나 간소화)
            Map<String, Object> reportData = (Map<String, Object>) aiResponse.get("report_data");
            resultBuilder
                    .finalReport(reportData != null ? (String) reportData.get("final_guide") : "원인 파악 중 오류가 발생했습니다.");
            resultBuilder.detectedIssues(objectMapper
                    .writeValueAsString(reportData != null ? reportData.get("suspected_causes") : List.of()));
            resultBuilder.riskLevel(DiagResult.RiskLevel.LOW);
        } else {
            Map<String, Object> interactiveData = (Map<String, Object>) aiResponse.get("interactive_data");
            if (interactiveData == null) {
                interactiveData = new HashMap<>(); // Safeguard
            }
            interactiveData.put("conversation", conversation);
            resultBuilder.interactiveJson(objectMapper.writeValueAsString(interactiveData));
        }
        diagResultRepository.save(resultBuilder.build());

        return mode;
    }

    private void sendDiagnosisNotification(UUID vehicleId, UUID sessionId, String responseMode) {
        try {
            vehicleRepository.findById(vehicleId).ifPresent(vehicle -> {
                String fcmToken = userService.getFcmToken(vehicle.getUserId());
                if (fcmToken != null) {
                    boolean isInteractive = "INTERACTIVE".equalsIgnoreCase(responseMode);
                    String title = isInteractive ? "[확인 필요] 차량 진단 추가 요청" : "차량 정밀 진단 완료";
                    String body = isInteractive ? "정확한 분석을 위해 사진 촬영이나 소음 녹음이 필요합니다. 대화를 이어가보세요."
                            : "요청하신 차량의 AI 정밀 진단 분석이 완료되었습니다. 결과를 확인해보세요.";

                    Map<String, String> data = new HashMap<>();
                    data.put("type", isInteractive ? "DIAG_INTERACTIVE" : "DIAG_COMPLETE");
                    data.put("sessionId", sessionId.toString());
                    data.put("mode", responseMode);

                    fcmService.sendMessage("User-" + vehicle.getUserId(), fcmToken, title, body, data);
                    log.info("Sent Diagnosis Notification [Vehicle: {}, Mode: {}]", vehicleId, responseMode);
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
                    point.put("load", l.getEngineLoad());
                    point.put("coolant", l.getCoolantTemp());
                    point.put("voltage", l.getVoltage());
                    return point;
                }).collect(Collectors.toList());
            }

            return aiClient.callAnomalyDetection(Map.of("time_series", timeSeries));
        } catch (Exception e) {
            log.warn("Anomaly detection failed, continuing with partial results", e);
            return Map.of("is_anomaly", false, "error", e.getMessage());
        }
    }

    private DiagStatus saveDiagnosisResult(UUID sessionId, Map<String, Object> response,
            String imageFile, String audioFile,
            Map<String, Object> visualResult, Map<String, Object> audioResult) {
        try {
            String mode = (String) response.getOrDefault("response_mode", "REPORT");
            String confidence = (String) response.getOrDefault("confidence_level", "LOW");
            String summary = (String) response.getOrDefault("summary", "");

            DiagResult.DiagResultBuilder resultBuilder = DiagResult.builder()
                    .diagSessionId(sessionId)
                    .responseMode(mode)
                    .confidenceLevel(confidence)
                    .summary(summary);

            if ("REPORT".equalsIgnoreCase(mode)) {
                @SuppressWarnings("unchecked")
                Map<String, Object> reportData = (Map<String, Object>) response.get("report_data");
                if (reportData != null) {
                    resultBuilder.finalReport((String) reportData.get("final_guide"));
                    resultBuilder.detectedIssues(objectMapper.writeValueAsString(reportData.get("suspected_causes")));

                    // Risk Level 추출
                    String riskStr = (String) reportData.getOrDefault("risk_level", "LOW");
                    try {
                        resultBuilder.riskLevel(DiagResult.RiskLevel.valueOf(riskStr.toUpperCase()));
                    } catch (Exception e) {
                        resultBuilder.riskLevel(DiagResult.RiskLevel.LOW);
                    }
                }
                diagResultRepository.save(resultBuilder.build());

                // 증거 데이터 저장 (Evidence)
                saveEvidences(sessionId, imageFile, audioFile, visualResult, audioResult);

                return DiagStatus.DONE;
            } else {
                if (response.containsKey("requested_actions") && response.get("requested_actions") != null) {
                    @SuppressWarnings("unchecked")
                    List<String> actions = (List<String>) response.get("requested_actions");
                    if (!actions.isEmpty()) {
                        try {
                            resultBuilder.requestedAction(DiagAction.valueOf(actions.get(0).toUpperCase()));
                        } catch (Exception e) {
                            log.warn("[Diagnosis] Unknown action requested: {}", actions.get(0));
                        }
                    }
                }
                resultBuilder.interactiveJson(objectMapper.writeValueAsString(response.get("interactive_data")));
                diagResultRepository.save(resultBuilder.build());
                return DiagStatus.ACTION_REQUIRED;
            }
        } catch (Exception e) {
            log.error("Failed to save diagnosis result", e);
            throw new RuntimeException("진단 결과 저장 실패", e);
        }
    }

    private void saveEvidences(UUID sessionId, String imageFile, String audioFile,
            Map<String, Object> visualResult, Map<String, Object> audioResult) {
        if (imageFile != null) {
            AiEvidence.AiEvidenceBuilder builder = AiEvidence.builder()
                    .diagSessionId(sessionId)
                    .evidenceType(AiEvidence.EvidenceType.IMAGE)
                    .filePath(imageFile);

            if (visualResult != null) {
                builder.inferenceLabel((String) visualResult.get("category"))
                        .confidence(visualResult.containsKey("confidence")
                                ? Double.valueOf(visualResult.get("confidence").toString())
                                : null);
            }
            aiEvidenceRepository.save(builder.build());
        }

        if (audioFile != null) {
            AiEvidence.AiEvidenceBuilder builder = AiEvidence.builder()
                    .diagSessionId(sessionId)
                    .evidenceType(AiEvidence.EvidenceType.AUDIO)
                    .filePath(audioFile);

            if (audioResult != null) {
                builder.inferenceLabel((String) audioResult.get("status"))
                        .confidence(audioResult.containsKey("confidence")
                                ? Double.valueOf(audioResult.get("confidence").toString())
                                : null);
            }
            aiEvidenceRepository.save(builder.build());
        }
    }

    /**
     * 진단 결과 조회
     */
    @Transactional(readOnly = true)
    public DiagnosisResponseDto getDiagnosisResult(UUID sessionId) {
        DiagSession session = diagSessionRepository.findById(sessionId)
                .orElseThrow(() -> new RuntimeException("Session not found: " + sessionId));

        DiagResult result = diagResultRepository.findByDiagSessionId(sessionId).orElse(null);

        DiagnosisResponseDto.DiagnosisResponseDtoBuilder builder = DiagnosisResponseDto.builder()
                .sessionId(session.getDiagSessionId())
                .status(session.getStatus().name())
                .progressMessage(session.getProgressMessage())
                .createdAt(session.getCreatedAt());

        if (result != null) {
            builder.responseMode(result.getResponseMode())
                    .confidenceLevel(result.getConfidenceLevel())
                    .summary(result.getSummary())
                    .finalReport(result.getFinalReport())
                    .riskLevel(result.getRiskLevel() != null ? result.getRiskLevel().name() : null);

            try {
                if (result.getDetectedIssues() != null) {
                    builder.suspectedCauses(objectMapper.readValue(result.getDetectedIssues(), List.class));
                }
                if (result.getInteractiveJson() != null) {
                    builder.interactiveData(objectMapper.readValue(result.getInteractiveJson(), Map.class));
                }
                if (result.getRequestedAction() != null) {
                    builder.requestedAction(result.getRequestedAction());
                }
            } catch (Exception e) {
                log.error("Failed to parse JSON fields in DiagResult", e);
            }
        }

        return builder.build();
    }

    /**
     * 차량별 진단 목록 조회
     */
    @Transactional(readOnly = true)
    public List<DiagnosisListItemDto> getDiagnosisList(UUID vehicleId) {
        List<DiagSession> sessions = diagSessionRepository.findByVehiclesIdOrderByCreatedAtDesc(vehicleId);

        return sessions.stream().map(session -> {
            DiagResult result = diagResultRepository.findByDiagSessionId(session.getDiagSessionId()).orElse(null);

            return DiagnosisListItemDto.builder()
                    .sessionId(session.getDiagSessionId())
                    .status(session.getStatus().name())
                    .progressMessage(session.getProgressMessage())
                    .triggerType(session.getTriggerType().name())
                    .responseMode(result != null ? result.getResponseMode() : null)
                    .riskLevel(result != null && result.getRiskLevel() != null ? result.getRiskLevel().name() : null)
                    .createdAt(session.getCreatedAt())
                    .build();
        }).collect(Collectors.toList());
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

    @Transactional
    public Map<String, Object> replyToSession(UUID sessionId, ReplyRequestDto replyDto,
            org.springframework.web.multipart.MultipartFile additionalImage,
            org.springframework.web.multipart.MultipartFile additionalAudio) {

        log.info("[Reply] 세션 {} 에 대한 비동기 답변 처리 접수", sessionId);

        DiagSession session = diagSessionRepository.findById(sessionId)
                .orElseThrow(() -> new RuntimeException("Session not found: " + sessionId));

        if (session.getStatus() != DiagStatus.ACTION_REQUIRED) {
            throw new RuntimeException("현재 세션은 추가 답변을 받을 수 없는 상태입니다: " + session.getStatus());
        }

        // 1. 상태 변경 (폴링 시작 유도)
        session.updateStatus(DiagStatus.REPLY_PROCESSING, "답변 분석을 준비 중입니다...");
        diagSessionRepository.save(session);

        // 2. 미디어 파일 로컬 저장
        String imageFile = saveMultipartFile(additionalImage, "reply_visual");
        String audioFile = saveMultipartFile(additionalAudio, "reply_audio");

        // 3. RabbitMQ 메시지 발행
        DiagnosisTaskMessage message = DiagnosisTaskMessage.builder()
                .sessionId(sessionId)
                .replyRequest(replyDto)
                .messageType(DiagnosisTaskMessage.MessageType.REPLY)
                .imageFilename(imageFile)
                .audioFilename(audioFile)
                .build();

        rabbitTemplate.convertAndSend(kr.co.himedia.config.RabbitConfig.EXCHANGE_NAME,
                kr.co.himedia.config.RabbitConfig.ROUTING_KEY, message);

        return Map.of(
                "message", "답변이 접수되었습니다. 분석 완료 후 결과가 업데이트됩니다.",
                "sessionId", sessionId,
                "status", "REPLY_ACCEPTED");
    }
}
