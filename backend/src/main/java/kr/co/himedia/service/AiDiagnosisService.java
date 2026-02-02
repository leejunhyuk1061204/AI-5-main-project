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
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.beans.factory.annotation.Value;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;
import kr.co.himedia.service.file.FileStorageService;
import java.util.stream.Collectors;

/**
 * AI 진단 및 DTC 처리 서비스
 * Hybrid Request Logic 포함 (Local: Multipart, S3: JSON)
 */
@Slf4j
@Service
public class AiDiagnosisService {

    private final DtcHistoryRepository dtcHistoryRepository;
    private final DtcCodeRepository dtcCodeRepository; // Added
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
    private final NotificationService notificationService;
    private final UserService userService;
    private final UserRepository userRepository;
    private final FileStorageService fileStorageService;

    // 글로벌 AI 리소스 통합 제어 (RTX 3090 안정성을 위해 최대 6개 요청 제한)
    private final java.util.concurrent.Semaphore globalAiSemaphore = new java.util.concurrent.Semaphore(6);

    public AiDiagnosisService(DtcHistoryRepository dtcHistoryRepository,
            DtcCodeRepository dtcCodeRepository, // Added
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
            NotificationService notificationService,
            UserService userService,
            UserRepository userRepository,
            FileStorageService fileStorageService) {
        this.dtcHistoryRepository = dtcHistoryRepository;
        this.dtcCodeRepository = dtcCodeRepository; // Added
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
        this.notificationService = notificationService;
        this.userService = userService;
        this.userRepository = userRepository;
        this.fileStorageService = fileStorageService;
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
     * RabbitMQ 제거 후 직접 호출로 변경 (Immediate Alert)
     */
    @Transactional
    public void processDtc(DtcDto dtcDto) {
        // 0. 한국어/영어 설명 조회 (DB Lookup)
        String descriptionKo = dtcDto.getDescriptionKo();
        String descriptionEn = dtcDto.getDescriptionEn();

        if (descriptionKo == null || descriptionKo.isEmpty()) {
            descriptionKo = "상세 설명 없음";
        }
        String ttsPhrase = dtcDto.getDtcCode(); // Default

        try {
            Optional<DtcCode> codeEntity = dtcCodeRepository.findByCodeGeneric(dtcDto.getDtcCode());
            if (codeEntity.isPresent()) {
                descriptionKo = codeEntity.get().getDescriptionKo();
                descriptionEn = codeEntity.get().getDescriptionEn();

                ttsPhrase = codeEntity.get().getTtsPhrase();

                // DTO 업데이트 (알림 전송 시 활용)
                dtcDto.setDescriptionKo(descriptionKo);
                dtcDto.setDescriptionEn(descriptionEn);
                dtcDto.setSummaryKo(codeEntity.get().getSummaryKo());
                dtcDto.setSummaryEn(codeEntity.get().getSummaryEn());
            }
        }
        }catch(

    Exception e)
    {
        log.warn("Failed to fetch DtcCode details from DB: {}", e.getMessage());
    }

    // 1. DTC 이력 저장
    DtcHistory history = DtcHistory.builder()
            .vehiclesId(UUID.fromString(dtcDto.getVehicleId()))
            .dtcCode(dtcDto.getDtcCode())
            .description(descriptionKo) // 한국어 설명 저장 (History는 한국어 유지)
            .severity(dtcDto.getSeverity())
            .status(DtcHistory.DtcStatus.valueOf(dtcDto.getStatus()))
            .build();dtcHistoryRepository.save(history);log.info("Saved DTC History: {} ({})",dtcDto.getDtcCode(),descriptionKo);

    // 2. RAG 및 FCM 알림 발송 (직접 호출)
    try
    {
        sendDtcNotification(dtcDto, ttsPhrase);
    }catch(
    Exception e)
    {
        log.error("Failed to send DTC notification", e);
    }

    // 3. AI 심층 진단 연결 (DTC 발생 시 자동 진단 트리거)
    try
    {
        UnifiedDiagnosisRequestDto diagReq = UnifiedDiagnosisRequestDto.builder()
                .vehicleId(UUID.fromString(dtcDto.getVehicleId()))
                .dtcCode(dtcDto.getDtcCode())
                .build();
        // [수정] AUTO -> DTC (최근 3일 데이터 분석)
        requestUnifiedDiagnosis(diagReq, null, null, DiagTriggerType.DTC);
        log.info("Automatically triggered AI Diagnosis for DTC: {}", dtcDto.getDtcCode());
    }catch(
    Exception e)
    {
        log.error("Failed to trigger automatic AI diagnosis", e);
    }
    }

    /**
     * 통합 진단 요청 (Trigger 2: 수동 진단 - RabbitMQ 발행)
     * 기존 PENDING/FAILED 세션이 있으면 UPDATE, 없으면 INSERT
     */
    @Transactional
    public Map<String, Object> requestUnifiedDiagnosis(UnifiedDiagnosisRequestDto requestDto,
            org.springframework.web.multipart.MultipartFile image,
            org.springframework.web.multipart.MultipartFile audio,
            DiagTriggerType diagType) {
        log.info("[통합진단] 요청 - 차량: {}, 타입: {}", requestDto.getVehicleId(), diagType);

        // 기존 PENDING 세션이 있으면 재사용
        DiagSession session = diagSessionRepository
                .findFirstByVehiclesIdAndStatusOrderByCreatedAtDesc(
                        requestDto.getVehicleId(), DiagStatus.PENDING)
                .orElseGet(() -> {
                    // PENDING이 없으면 FAILED도 확인
                    return diagSessionRepository
                            .findFirstByVehiclesIdAndStatusOrderByCreatedAtDesc(
                                    requestDto.getVehicleId(), DiagStatus.FAILED)
                            .orElse(null);
                });

        if (session != null) {
            log.info("Reusing existing session [{}] with status [{}]", session.getDiagSessionId(), session.getStatus());
            session.updateStatus(DiagStatus.PENDING, "진단 대기 중 (재요청)");
        } else {
            session = new DiagSession(requestDto.getVehicleId(), null, diagType);
        }
        session = diagSessionRepository.save(session);

        String imageUrl = null;
        String audioUrl = null;
        try {
            if (image != null && !image.isEmpty())
                imageUrl = fileStorageService.uploadFile(image, "image");
            if (audio != null && !audio.isEmpty())
                audioUrl = fileStorageService.uploadFile(audio, "audio");
        } catch (Exception e) {
            log.error("Failed to upload file to storage", e);
            throw new RuntimeException("파일 업로드 실패", e);
        }

        DiagnosisTaskMessage message = DiagnosisTaskMessage.builder()
                .sessionId(session.getDiagSessionId())
                .requestDto(requestDto)
                .messageType(DiagnosisTaskMessage.MessageType.INITIAL)
                .imageUrl(imageUrl)
                .audioUrl(audioUrl)
                .build();

        rabbitTemplate.convertAndSend(kr.co.himedia.config.RabbitConfig.EXCHANGE_NAME,
                kr.co.himedia.config.RabbitConfig.ROUTING_KEY, message);

        return Map.of(
                "message", "진단 요청이 접수되었습니다. 분석 완료 후 결과가 업데이트됩니다.",
                "sessionId", session.getDiagSessionId(),
                "status", "ACCEPTED");
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
        String imageUrl = taskMessage.getImageUrl();
        String audioUrl = taskMessage.getAudioUrl();

        // 0. 세션별 통합 리소스 관리 (인당 최대 3개 슬롯 공유)
        java.util.concurrent.Semaphore sessionSemaphore = new java.util.concurrent.Semaphore(3);

        // 1. 병렬 분석 태스크 생성
        CompletableFuture<Map<String, Object>> visualTask = CompletableFuture.supplyAsync(() -> {
            try {
                if (imageUrl != null) {
                    log.info("[Visual] [Semaphore-Acquire] 진입 시도 (Global: {}, Session: {})",
                            globalAiSemaphore.availablePermits(), sessionSemaphore.availablePermits());
                    sessionSemaphore.acquire();
                    globalAiSemaphore.acquire();
                    log.info("[Visual] [Semaphore-Acquire] 진입 성공 (Global: {}, Session: {})",
                            globalAiSemaphore.availablePermits(),
                            sessionSemaphore.availablePermits());
                    try {
                        log.info("[Backend -> AI] Visual 분석 요청 시작 - URL: {}", imageUrl);
                        Map<String, Object> result = aiClient.callVisualAnalysis(imageUrl, requestDto.getVehicleId(),
                                sessionId);
                        log.info("[AI -> Backend] Visual 분석 응답 수신 - 결과: {}", objectMapper.writeValueAsString(result));
                        log.info("[Visual] 분석 완료 (Session: {})", sessionId);
                        return result;
                    } finally {
                        globalAiSemaphore.release();
                        sessionSemaphore.release();
                        log.info("[Visual] [Semaphore-Release] 반납 완료 (Global: {}, Session: {})",
                                globalAiSemaphore.availablePermits(), sessionSemaphore.availablePermits());
                    }
                }
                return requestDto.getVisualAnalysis();
            } catch (Exception e) {
                log.error("[Visual] 분석 실패", e);
                return null;
            }
        });

        CompletableFuture<Map<String, Object>> audioTask = CompletableFuture.supplyAsync(() -> {
            try {
                if (audioUrl != null) {
                    log.info("[Audio] [Semaphore-Acquire] 진입 시도 (Global: {}, Session: {})",
                            globalAiSemaphore.availablePermits(), sessionSemaphore.availablePermits());
                    sessionSemaphore.acquire();
                    globalAiSemaphore.acquire();
                    log.info("[Audio] [Semaphore-Acquire] 진입 성공 (Global: {}, Session: {})",
                            globalAiSemaphore.availablePermits(),
                            sessionSemaphore.availablePermits());
                    try {
                        Map<String, Object> result = aiClient.callAudioAnalysis(audioUrl, requestDto.getVehicleId(),
                                sessionId);
                        log.info("[Audio] 분석 완료 (Session: {})", sessionId);
                        return result;
                    } finally {
                        globalAiSemaphore.release();
                        sessionSemaphore.release();
                        log.info("[Audio] [Semaphore-Release] 반납 완료 (Global: {}, Session: {})",
                                globalAiSemaphore.availablePermits(), sessionSemaphore.availablePermits());
                    }
                }
                return requestDto.getAudioAnalysis();
            } catch (Exception e) {
                log.error("[Audio] 분석 실패", e);
                return null;
            }
        });

        CompletableFuture<Map<String, Object>> anomalyTask = CompletableFuture.supplyAsync(() -> {
            return performAnomalyDetection(requestDto, session.getTriggerType(), sessionSemaphore, sessionId);
        });

        // 모든 결과 대기 (15분 단위 청크 처리 등 대량 데이터 분석을 고려하여 10분으로 상향)
        CompletableFuture.allOf(visualTask, audioTask, anomalyTask).get(600, TimeUnit.SECONDS);

        Map<String, Object> visualResult = visualTask.join();
        Map<String, Object> audioResult = audioTask.join();
        Map<String, Object> anomalyResult = anomalyTask.join();

        // [Filter Logic] LLM 전송용 데이터 필터링 (토큰 절약)
        // 1. 이상(Anomaly)이 있는 청크만 우선 수집
        // 2. 만약 모두 정상(Normal)이라면, 가장 마지막(최신) 청크 하나만 전송
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> detailedResults = (List<Map<String, Object>>) anomalyResult.get("detailed_results");
        List<Map<String, Object>> filteredTimeline = new ArrayList<>();

        if (detailedResults != null && !detailedResults.isEmpty()) {
            List<Map<String, Object>> anomalies = detailedResults.stream()
                    .filter(r -> Boolean.TRUE.equals(r.get("is_anomaly")))
                    .collect(Collectors.toList());

            if (anomalies.isEmpty()) {
                // Case: All Normal -> Take last one
                filteredTimeline.add(detailedResults.get(detailedResults.size() - 1));
            } else {
                // Case: Has Anomaly -> Take all anomalies
                filteredTimeline.addAll(anomalies);
            }
        }

        Map<String, Object> llmAnomalyPayload = new HashMap<>();
        llmAnomalyPayload.put("lstm_timeline", filteredTimeline);
        llmAnomalyPayload.put("is_anomaly", anomalyResult.get("is_anomaly"));
        llmAnomalyPayload.put("chunk_count", anomalyResult.get("chunk_count"));

        // [DTC] DTC 정보가 있다면 영문 설명 추가
        Map<String, Object> dtcInfo = null;
        if (requestDto.getDtcCode() != null) {
            dtcInfo = new HashMap<>();
            dtcInfo.put("code", requestDto.getDtcCode());
            try {
                Optional<DtcCode> dtcEntity = dtcCodeRepository.findByCodeGeneric(requestDto.getDtcCode());
                if (dtcEntity.isPresent()) {
                    dtcInfo.put("description", dtcEntity.get().getDescriptionEn());
                    dtcInfo.put("summary", dtcEntity.get().getSummaryEn());
                } else {
                    dtcInfo.put("description", "No specific English description available.");
                }
            } catch (Exception e) {
                log.warn("Failed to fetch English DTC info for LLM: {}", e.getMessage());
            }
        }

        // 2. 통합 요청 객체 구축 및 RAG 검색
        AiUnifiedRequestDto.AiUnifiedRequestDtoBuilder aiRequestBuilder = AiUnifiedRequestDto.builder()
                .visualAnalysis(visualResult)
                .audioAnalysis(audioResult)
                .anomalyAnalysis(llmAnomalyPayload)
                .dtcInfo(dtcInfo);

        populateVehicleAndConsumableInfo(aiRequestBuilder, requestDto.getVehicleId());

        String query = buildSearchQuery(visualResult, audioResult, anomalyResult);
        if (!query.isEmpty()) {
            String manufacturer = null;
            String model = null;
            var vehicleOpt = vehicleRepository.findById(requestDto.getVehicleId());
            if (vehicleOpt.isPresent()) {
                manufacturer = vehicleOpt.get().getManufacturerEn();
                model = vehicleOpt.get().getModelNameEn();
            }

            List<String> knowledgeResults;
            if (manufacturer != null && model != null) {
                knowledgeResults = knowledgeService.searchKnowledgeWithFilter(query, manufacturer, model, 3, 0.4);
            } else {
                knowledgeResults = knowledgeService.searchKnowledge(query, 3);
            }
            aiRequestBuilder.knowledgeData(knowledgeResults);
        }

        // 3. 최종 통합 진단 요청 (Phase 1: Mock Response)
        log.info("[Initial] Mocking comprehensive diagnosis response for testing.");
        Map<String, Object> finalResponse = new HashMap<>();
        finalResponse.put("response_mode", "REPORT"); // 기본적으로 리포트 모드로 설정
        finalResponse.put("confidence_level", "HIGH");
        finalResponse.put("summary", "차량의 상태를 분석한 결과, 엔진 오일 압력 센서 및 배기 시스템에 점검이 필요할 수 있습니다.");
        
        Map<String, Object> reportData = new HashMap<>();
        reportData.put("final_guide", "엔진 오일의 상태를 먼저 점검하시고, 필요 시 전문가의 진단을 받으시기 바랍니다.");
        reportData.put("suspected_causes", List.of("엔진 오일 부족", "압력 센서 오작동"));
        finalResponse.put("report_data", reportData);

        // 4. 결과 저장 및 상태 결정
        DiagStatus finalStatus = saveDiagnosisResult(sessionId, finalResponse, imageUrl, audioUrl, visualResult,
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
        String imageUrl = taskMessage.getImageUrl();
        String audioUrl = taskMessage.getAudioUrl();

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
        if (imageUrl != null) {
            visualResult = aiClient.callVisualAnalysis(imageUrl, session.getVehiclesId(), sessionId);
            saveEvidences(sessionId, imageUrl, null, visualResult, null);
        }

        Map<String, Object> audioResult = null;
        if (audioUrl != null) {
            audioResult = aiClient.callAudioAnalysis(audioUrl, session.getVehiclesId(), sessionId);
            saveEvidences(sessionId, null, audioUrl, null, audioResult);
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

        // 4. GPT 요청 (Phase 2: Mock Response)
        log.info("[Reply] Mocking comprehensive diagnosis response for interactive turn.");
        Map<String, Object> aiResponse = new HashMap<>();
        aiResponse.put("response_mode", "REPORT");
        aiResponse.put("confidence_level", "HIGH");
        aiResponse.put("summary", "사용자 질문에 답변한 최종 리포트입니다.");

        Map<String, Object> reportData = new HashMap<>();
        reportData.put("final_guide", "고객님께서 문의하신 내용에 따르면, 추가적인 기계적 결함보다는 단순 소모품 교체 주기가 도래한 것으로 보입니다.");
        reportData.put("suspected_causes", List.of("소모품 마모", "정기 점검 필요"));
        aiResponse.put("report_data", reportData);

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
                searchQuery.append(String.join(" ", factors)).append(" anomaly");
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

        // [수정] 중복 방지: 기존 객체를 직접 수정 (delete-then-save 대신)
        existingResult.setResponseMode(mode);
        existingResult.setConfidenceLevel((String) aiResponse.getOrDefault("confidence_level", "LOW"));
        existingResult.setSummary((String) aiResponse.getOrDefault("summary", ""));

        if (aiResponse.containsKey("requested_actions") && aiResponse.get("requested_actions") != null) {
            @SuppressWarnings("unchecked")
            List<String> actions = (List<String>) aiResponse.get("requested_actions");
            if (!actions.isEmpty()) {
                try {
                    existingResult.setRequestedAction(DiagAction.valueOf(actions.get(0).toUpperCase()));
                } catch (Exception e) {
                    log.warn("[Reply] Unknown action requested: {}", actions.get(0));
                }
            }
        }

        if ("REPORT".equalsIgnoreCase(mode)) {
            Map<String, Object> reportData = (Map<String, Object>) aiResponse.get("report_data");
            existingResult.setFinalReport(
                    reportData != null ? (String) reportData.get("final_guide") : "원인 파악 중 오류가 발생했습니다.");
            existingResult.setDetectedIssues(objectMapper
                    .writeValueAsString(reportData != null ? reportData.get("suspected_causes") : List.of()));
            existingResult.setRiskLevel(DiagResult.RiskLevel.LOW);
        } else {
            Map<String, Object> interactiveData = (Map<String, Object>) aiResponse.get("interactive_data");
            if (interactiveData == null) {
                interactiveData = new HashMap<>(); // Safeguard
            }
            interactiveData.put("conversation", conversation);
            existingResult.setInteractiveJson(objectMapper.writeValueAsString(interactiveData));
        }
        diagResultRepository.save(existingResult);

        return mode;
    }

    private void sendDtcNotification(DtcDto dtcDto, String ttsPhrase) {
        try {
            // [수정] VIN 대신 VehicleId로 조회 (VIN 불일치 문제 해결)
            UUID vehicleId = UUID.fromString(dtcDto.getVehicleId());
            vehicleRepository.findById(vehicleId).ifPresent(vehicle -> {
                User user = userRepository.findById(vehicle.getUserId()).orElse(null);
                if (user == null)
                    return;

                String title = "차량 고장 코드 감지";
                // body에 한국어 설명 포함
                String body = "[" + dtcDto.getDtcCode() + "] " + dtcDto.getDescriptionKo();

                Map<String, String> data = new HashMap<>();
                data.put("type", "DTC_ALERT");
                data.put("dtcCode", dtcDto.getDtcCode());
                data.put("vehicleId", vehicle.getVehicleId().toString());
                if (ttsPhrase != null) {
                    data.put("ttsPhrase", ttsPhrase);
                }

                // NotificationService 사용
                notificationService.sendNotification(user, title, body,
                        kr.co.himedia.entity.Notification.NotificationType.DTC_ALERT, data);
            });
        } catch (Exception e) {
            log.error("Failed to send DTC notification", e);
        }

    }

    private void sendDiagnosisNotification(UUID vehicleId, UUID sessionId, String responseMode) {
        try {
            // 1. 세션 조회 및 TriggerType 확인
            DiagSession session = diagSessionRepository.findById(sessionId).orElse(null);
            if (session == null) {
                log.warn("Session not found for notification: {}", sessionId);
                return;
            }

            // [Filter] 대화형(수동) 진단인 경우 알림 발송 스킵
            DiagTriggerType trigger = session.getTriggerType();
            if (trigger == DiagTriggerType.DATA || trigger == DiagTriggerType.VISUAL
                    || trigger == DiagTriggerType.AUDIO) {
                log.info("Skipping notification for interactive session [Trigger: {}]", trigger);
                return;
            }

            vehicleRepository.findById(vehicleId).ifPresent(vehicle -> {
                // User 조회
                User user = userRepository.findById(vehicle.getUserId()).orElse(null);
                if (user == null)
                    return;

                String title = "AI 진단 완료";
                String body = "차량 진단 리포트가 도착했습니다. 지금 확인해보세요.";
                Map<String, String> data = new HashMap<>();
                data.put("type", "DIAG_ALERT");
                data.put("sessionId", sessionId.toString());
                data.put("vehicleId", vehicleId.toString());

                // Note: INTERACTIVE mode check might be redundant if we filter out checking
                // triggers,
                // but kept for safety or mixed scenarios.
                if ("INTERACTIVE".equals(responseMode)) {
                    // 수동 진단 필터링이 적용되었으므로 이 분기에는 도달하지 않아야 정상이지만,
                    // 예외적인 자동 대화형 모드 등이 있을 수 있으므로 유지
                    title = "AI 질문 도착";
                    body = "AI가 진단을 위해 추가 정보를 요청했습니다.";
                }

                // NotificationService를 통해 전송 (DB 저장 + RabbitMQ 발행)
                notificationService.sendNotification(user, title, body,
                        kr.co.himedia.entity.Notification.NotificationType.DIAG_ALERT, data);

                log.info("Sent Diagnosis Notification via NotificationService [Vehicle: {}, Mode: {}, Trigger: {}]",
                        vehicleId,
                        responseMode, trigger);
            });
        } catch (Exception e) {
            log.error("Failed to send diagnosis notification", e);
        }
    }

    private Map<String, Object> performAnomalyDetection(UnifiedDiagnosisRequestDto requestDto,
            DiagTriggerType triggerType, java.util.concurrent.Semaphore sessionSemaphore, java.util.UUID sessionId) {
        try {
            UUID vehicleId = requestDto.getVehicleId();
            List<List<Map<String, Object>>> chunks = new ArrayList<>();

            // 1. 데이터 수집 및 청크 분할
            if (triggerType == DiagTriggerType.AUTO && requestDto.getLstmAnalysis() != null
                    && !requestDto.getLstmAnalysis().isEmpty()) {
                log.info("[Anomaly] AUTO 모드: 현재 주행 데이터 기반 청크화");
                @SuppressWarnings("unchecked")
                List<Map<String, Object>> logs = (List<Map<String, Object>>) requestDto.getLstmAnalysis().get("logs");
                if (logs != null && !logs.isEmpty()) {
                    chunks = splitIntoChunks(logs, 900); // 15분(900초) 단위 분할
                }
            } else {
                log.info("[Anomaly] {} 모드: 최근 3일 데이터 조회 및 청크화", triggerType);
                java.time.OffsetDateTime threeDaysAgo = java.time.OffsetDateTime.now(java.time.ZoneOffset.UTC)
                        .minusDays(3);
                List<ObdLog> allLogs = obdLogRepository.findByVehicleIdAndTimeBetweenOrderByTimeAsc(vehicleId,
                        threeDaysAgo, java.time.OffsetDateTime.now(java.time.ZoneOffset.UTC));
                chunks = chunkByTripAndSubdivide(allLogs, 900);
            }

            if (chunks.isEmpty()) {
                return Map.of("is_anomaly", false, "reason", "no_obd_data");
            }

            log.info("[Anomaly] 총 {}개의 청크 분석 시작 (병렬 처리)", chunks.size());

            // 람다 식 내에서 참조하기 위해 effectively final 변수로 복사
            final List<List<Map<String, Object>>> finalChunks = chunks;

            // 2. 병렬 전송 및 결과 수집 (세션당 병렬도는 CompletableFuture가 처리, 글로벌은 Semaphore가 제한)
            List<java.util.concurrent.CompletableFuture<Map<String, Object>>> futures = finalChunks.stream()
                    .map(chunk -> java.util.concurrent.CompletableFuture.supplyAsync(() -> {
                        try {
                            int chunkIndex = finalChunks.indexOf(chunk) + 1;
                            int totalChunks = finalChunks.size();
                            log.info("[Anomaly-Parallel] [Semaphore-Acquire] 진입 시도 (Global: {}, Session: {})",
                                    globalAiSemaphore.availablePermits(), sessionSemaphore.availablePermits());
                            sessionSemaphore.acquire(); // 세션당 최대 3개 제한 (시각/청각과 공유)
                            globalAiSemaphore.acquire(); // 글로벌 6개 제한 중 하나 획득
                            log.info("[Anomaly-Parallel] [Semaphore-Acquire] 진입 성공 (Global: {}, Session: {})",
                                    globalAiSemaphore.availablePermits(), sessionSemaphore.availablePermits());

                            Map<String, Object> payload = new java.util.HashMap<>();
                            payload.put("time_series", chunk);
                            payload.put("vehicle_id", requestDto.getVehicleId().toString());
                            payload.put("session_id", sessionId.toString());
                            payload.put("chunk_index", chunkIndex);
                            payload.put("total_chunks", totalChunks);

                            log.info(
                                    "[Anomaly-Parallel] 청강 전송 시작 ({}/{}) [Vehicle: {}, Session: {}]",
                                    chunkIndex, totalChunks, requestDto.getVehicleId(), sessionId);

                            return aiClient.callAnomalyDetection(payload);
                        } catch (InterruptedException e) {
                            Thread.currentThread().interrupt();
                            Map<String, Object> errorMap = new HashMap<>();
                            errorMap.put("error", "Interrupted");
                            return errorMap;
                        } finally {
                            globalAiSemaphore.release(); // 완료 후 해제
                            sessionSemaphore.release(); // 세션 리소스 반납
                            log.info("[Anomaly-Parallel] [Semaphore-Release] 반납 완료 (Global: {}, Session: {})",
                                    globalAiSemaphore.availablePermits(), sessionSemaphore.availablePermits());
                        }
                    })).collect(Collectors.toList());

            // 모든 청크 결과 대기
            List<Map<String, Object>> results = futures.stream()
                    .map(java.util.concurrent.CompletableFuture::join)
                    .collect(Collectors.toList());

            // 3. 결과 취합 (사용자 가이드에 따라 우선 리스트로 반환 - 추후 Aggregation 로직 강화 가능)
            boolean isAnyAnomaly = results.stream()
                    .anyMatch(r -> r.get("is_anomaly") != null && (boolean) r.get("is_anomaly"));

            log.info("[Anomaly] 분석 완료. 이상 징후 발견 여부: {}", isAnyAnomaly);

            return Map.of(
                    "is_anomaly", isAnyAnomaly,
                    "detailed_results", results,
                    "chunk_count", chunks.size());

        } catch (Exception e) {
            log.error("Anomaly detection failed", e);
            return Map.of("is_anomaly", false, "error", e.getMessage());
        }
    }

    /**
     * 데이터를 15분(maxSize) 단위로 단순 분할 (자동 진단용)
     */
    private List<List<Map<String, Object>>> splitIntoChunks(List<Map<String, Object>> logs, int maxSize) {
        List<List<Map<String, Object>>> chunks = new ArrayList<>();
        for (int i = 0; i < logs.size(); i += maxSize) {
            int end = Math.min(i + maxSize, logs.size());
            List<Map<String, Object>> chunk = new ArrayList<>(logs.subList(i, end));
            // 60초(60개) 미만 자투리는 무시 (설계 반영)
            if (chunk.size() >= 60 || chunks.isEmpty()) {
                chunks.add(chunk);
            }
        }
        return chunks;
    }

    /**
     * 주행(trip_id)별로 1차 그룹화 후, 각 주행을 15분 단위로 2차 분할 (수동 진단용)
     */
    private List<List<Map<String, Object>>> chunkByTripAndSubdivide(List<ObdLog> logs, int maxSize) {
        List<List<Map<String, Object>>> finalChunks = new ArrayList<>();

        // 시간 기반 그룹화 (시간 간격이 5분 이상 벌어지면 다른 주행으로 간주)
        List<List<ObdLog>> tripGroups = new ArrayList<>();
        if (logs.isEmpty())
            return finalChunks;

        List<ObdLog> currentGroup = new ArrayList<>();
        currentGroup.add(logs.get(0));
        for (int i = 1; i < logs.size(); i++) {
            long diffSec = java.time.Duration.between(logs.get(i - 1).getTime(), logs.get(i).getTime()).getSeconds();
            if (Math.abs(diffSec) > 300) { // 5분Gap
                tripGroups.add(currentGroup);
                currentGroup = new ArrayList<>();
            }
            currentGroup.add(logs.get(i));
        }
        tripGroups.add(currentGroup);

        for (List<ObdLog> group : tripGroups) {
            List<Map<String, Object>> mappedLogs = group.stream().map(l -> {
                Map<String, Object> p = new HashMap<>();
                p.put("rpm", l.getRpm());
                p.put("speed", l.getSpeed());
                p.put("load", l.getEngineLoad());
                p.put("coolant", l.getCoolantTemp());
                p.put("voltage", l.getVoltage());
                p.put("time", l.getTime().toString());
                return p;
            }).collect(Collectors.toList());

            finalChunks.addAll(splitIntoChunks(mappedLogs, maxSize));
        }
        return finalChunks;
    }

    private DiagStatus saveDiagnosisResult(UUID sessionId, Map<String, Object> response,
            String imageFile, String audioFile,
            Map<String, Object> visualResult, Map<String, Object> audioResult) {
        try {
            String mode = (String) response.getOrDefault("response_mode", "REPORT");
            String confidence = (String) response.getOrDefault("confidence_level", "LOW");
            String summary = (String) response.getOrDefault("summary", "");

            // [수정] 중복 저장 방지: 기존 결과가 있으면 업데이트
            DiagResult diagResult = diagResultRepository.findAllByDiagSessionId(sessionId).stream()
                    .findFirst()
                    .orElseGet(() -> DiagResult.builder().build());

            diagResult.setDiagSessionId(sessionId);
            diagResult.setResponseMode(mode);
            diagResult.setConfidenceLevel(confidence);
            diagResult.setSummary(summary);

            if ("REPORT".equalsIgnoreCase(mode)) {
                @SuppressWarnings("unchecked")
                Map<String, Object> reportData = (Map<String, Object>) response.get("report_data");
                if (reportData != null) {
                    diagResult.setFinalReport((String) reportData.get("final_guide"));
                    diagResult.setDetectedIssues(objectMapper.writeValueAsString(reportData.get("suspected_causes")));

                    // Risk Level 추출
                    String riskStr = (String) reportData.getOrDefault("risk_level", "LOW");
                    try {
                        diagResult.setRiskLevel(DiagResult.RiskLevel.valueOf(riskStr.toUpperCase()));
                    } catch (Exception e) {
                        diagResult.setRiskLevel(DiagResult.RiskLevel.LOW);
                    }
                }
                diagResultRepository.save(diagResult);

                // 증거 데이터 저장 (Evidence)
                saveEvidences(sessionId, imageFile, audioFile, visualResult, audioResult);

                return DiagStatus.DONE;
            } else {
                if (response.containsKey("requested_actions") && response.get("requested_actions") != null) {
                    @SuppressWarnings("unchecked")
                    List<String> actions = (List<String>) response.get("requested_actions");
                    if (!actions.isEmpty()) {
                        try {
                            diagResult.setRequestedAction(DiagAction.valueOf(actions.get(0).toUpperCase()));
                        } catch (Exception e) {
                            log.warn("[Diagnosis] Unknown action requested: {}", actions.get(0));
                        }
                    }
                }
                diagResult.setInteractiveJson(objectMapper.writeValueAsString(response.get("interactive_data")));
                diagResultRepository.save(diagResult);
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

        DiagResult result = diagResultRepository.findAllByDiagSessionId(sessionId).stream()
                .findFirst()
                .orElse(null);

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
                    .triggerTypeLabel(getTriggerTypeLabel(session.getTriggerType()))
                    .responseMode(result != null ? result.getResponseMode() : null)
                    .riskLevel(result != null && result.getRiskLevel() != null ? result.getRiskLevel().name() : null)
                    .createdAt(session.getCreatedAt())
                    .build();
        }).collect(Collectors.toList());
    }

    /**
     * 진단 타입 한글 라벨 변환 헬퍼
     */
    private String getTriggerTypeLabel(DiagTriggerType type) {
        switch (type) {
            case AUTO:
                return "자동 진단";
            case DATA:
                return "데이터 진단";
            case VISUAL:
                return "사진 진단";
            case AUDIO:
                return "소리 진단";
            case DTC:
                return "고장코드 진단";
            case ROUTINE:
                return "정기 진단";
            default:
                return "진단";
        }
    }

    private void populateVehicleAndConsumableInfo(AiUnifiedRequestDto.AiUnifiedRequestDtoBuilder builder,
            UUID vehicleId) {
        vehicleRepository.findById(vehicleId).ifPresent(vehicle -> {
            Map<String, Object> vehicleInfo = new HashMap<>();
            vehicleInfo.put("manufacturer", vehicle.getManufacturerEn());
            vehicleInfo.put("model", vehicle.getModelNameEn());
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

        // 2. 미디어 파일 저장소 업로드
        String imageUrl = null;
        String audioUrl = null;
        try {
            if (additionalImage != null && !additionalImage.isEmpty())
                imageUrl = fileStorageService.uploadFile(additionalImage, "image");
            if (additionalAudio != null && !additionalAudio.isEmpty())
                audioUrl = fileStorageService.uploadFile(additionalAudio, "audio");
        } catch (Exception e) {
            log.error("Failed to upload additional media", e);
            throw new RuntimeException("추가 미디어 파일 업로드 실패", e);
        }

        // 3. RabbitMQ 메시지 발행
        DiagnosisTaskMessage message = DiagnosisTaskMessage.builder()
                .sessionId(sessionId)
                .replyRequest(replyDto)
                .messageType(DiagnosisTaskMessage.MessageType.REPLY)
                .imageUrl(imageUrl)
                .audioUrl(audioUrl)
                .build();

        rabbitTemplate.convertAndSend(kr.co.himedia.config.RabbitConfig.EXCHANGE_NAME,
                kr.co.himedia.config.RabbitConfig.ROUTING_KEY, message);

        return Map.of(
                "message", "답변이 접수되었습니다. 분석 완료 후 결과가 업데이트됩니다.",
                "sessionId", sessionId,
                "status", "REPLY_ACCEPTED");
    }
}
