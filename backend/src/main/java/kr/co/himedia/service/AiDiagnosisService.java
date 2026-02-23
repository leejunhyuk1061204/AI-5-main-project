package kr.co.himedia.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import kr.co.himedia.domain.DiagAction;
import kr.co.himedia.dto.ai.*;
import kr.co.himedia.common.SseEmitters;
import kr.co.himedia.common.exception.BaseException;
import kr.co.himedia.common.exception.ErrorCode;
import kr.co.himedia.entity.*;
import kr.co.himedia.entity.DiagSession.DiagStatus;
import kr.co.himedia.entity.DiagSession.DiagTriggerType;
import kr.co.himedia.repository.*;
import kr.co.himedia.entity.CloudTelemetry;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import java.util.stream.Collectors;
import java.util.concurrent.TimeUnit;

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
    private final DtcFreezeFrameRepository dtcFreezeFrameRepository;
    private final DtcCodeRepository dtcCodeRepository;
    private final CloudTelemetryRepository cloudTelemetryRepository;
    private final AiClient aiClient;
    private final OpenAiDiagnosisService openAiDiagnosisService;
    private final ObjectMapper objectMapper;

    private final FcmService fcmService;
    private final UserService userService;
    private final AiMediaService aiMediaService;
    private final SseEmitters sseEmitters;
    private final NotificationService notificationService;
    private final UserRepository userRepository;

    // 글로벌 AI 리소스 통합 제어 (RTX 3090 안정성을 위해 최대 6개 요청 제한)
    private final java.util.concurrent.Semaphore globalAiSemaphore = new java.util.concurrent.Semaphore(6);

    /** LLM에 보낼 소모품: 이 수치 이하면 "주의 필요"로 포함 */
    private static final double CONSUMABLE_ATTENTION_THRESHOLD_PCT = 80.0;
    /** DTC 진단 시 함께 보낼 엔진/배기 관련 소모품 코드 (시드와 동일하게 유지) */
    private static final Set<String> CONSUMABLE_CODES_DTC_RELATED = Set.of(
            "ENGINE_OIL", "AIR_FILTER", "FUEL_FILTER", "SPARK_PLUG", "COOLANT");
    /** 항상 포함할 핵심 소모품 (안전/엔진) */
    private static final Set<String> CONSUMABLE_CODES_ALWAYS = Set.of(
            "ENGINE_OIL", "BRAKE_PAD_FRONT", "BRAKE_PAD_REAR", "BATTERY_12V");

    public AiDiagnosisService(DtcHistoryRepository dtcHistoryRepository,
            RabbitTemplate rabbitTemplate,
            KnowledgeService knowledgeService,
            ObdLogRepository obdLogRepository,
            VehicleRepository vehicleRepository,
            VehicleConsumableRepository vehicleConsumableRepository,
            DiagSessionRepository diagSessionRepository,
            DiagResultRepository diagResultRepository,
            AiEvidenceRepository aiEvidenceRepository,
            DtcFreezeFrameRepository dtcFreezeFrameRepository,
            DtcCodeRepository dtcCodeRepository,
            CloudTelemetryRepository cloudTelemetryRepository,
            AiClient aiClient,
            OpenAiDiagnosisService openAiDiagnosisService,
            ObjectMapper objectMapper,
            FcmService fcmService,
            UserService userService,
            AiMediaService aiMediaService,
            SseEmitters sseEmitters,
            NotificationService notificationService,
            UserRepository userRepository) {
        this.dtcHistoryRepository = dtcHistoryRepository;
        this.rabbitTemplate = rabbitTemplate;
        this.knowledgeService = knowledgeService;
        this.obdLogRepository = obdLogRepository;
        this.vehicleRepository = vehicleRepository;
        this.vehicleConsumableRepository = vehicleConsumableRepository;
        this.diagSessionRepository = diagSessionRepository;
        this.diagResultRepository = diagResultRepository;
        this.aiEvidenceRepository = aiEvidenceRepository;
        this.dtcFreezeFrameRepository = dtcFreezeFrameRepository;
        this.dtcCodeRepository = dtcCodeRepository;
        this.cloudTelemetryRepository = cloudTelemetryRepository;
        this.aiClient = aiClient;
        this.openAiDiagnosisService = openAiDiagnosisService;
        this.objectMapper = objectMapper;
        this.fcmService = fcmService;
        this.userService = userService;
        this.aiMediaService = aiMediaService;
        this.sseEmitters = sseEmitters;
        this.notificationService = notificationService;
        this.userRepository = userRepository;
    }

    /**
     * DLQ로 이동한 진단 작업에 대한 후속 처리.
     * 이미 여러 차례 재시도 후에도 실패한 경우이므로,
     * 여기에서 최종 1회만 실패 FCM을 발송한다.
     */
    public void handleDeadDiagnosisTask(DiagnosisTaskMessage taskMessage) {
        UUID sessionId = taskMessage.getSessionId();
        if (sessionId == null) {
            log.error("[DLQ Handler] Dead task without sessionId: {}", taskMessage);
            return;
        }

        DiagSession session = diagSessionRepository.findById(sessionId).orElse(null);
        if (session == null) {
            log.error("[DLQ Handler] DiagSession not found for dead task. sessionId={}", sessionId);
            return;
        }

        DiagTriggerType triggerType = session.getTriggerType();

        // 세션 상태를 FAILED로 보정 (이미 FAILED일 수도 있음)
        session.updateStatus(DiagStatus.FAILED, "진단 실패: 시스템에서 여러 차례 재시도했지만 완료되지 않았습니다.");
        diagSessionRepository.save(session);

        // AUTO/DTC만 실패 FCM 발송 대상 (한 세션당 1회)
        if (triggerType == DiagTriggerType.AUTO || triggerType == DiagTriggerType.DTC) {
            try {
                sendDiagnosisFailureNotification(session.getVehiclesId(), sessionId,
                        "시스템에서 여러 차례 재시도했지만 진단을 완료하지 못했습니다.");
            } catch (Exception e) {
                log.error("[DLQ Handler] Failed to send final diagnosis failure notification. sessionId={}", sessionId,
                        e);
            }
        } else {
            log.info("[DLQ Handler] Non AUTO/DTC dead task. No failure FCM sent. sessionId={}", sessionId);
        }
    }

    @Value("${app.storage.type:local}")
    private String storageType;

    @Value("${ai.server.url.visual:http://localhost:8001/api/v1/connect/predict/visual}")
    private String aiServerVisualUrl;

    @Value("${ai.server.url.audio:http://localhost:8001/api/v1/connect/predict/audio}")
    private String aiServerAudioUrl;

    @Value("${ai.server.url.comprehensive:http://localhost:8001/api/v1/connect/predict/comprehensive}")
    private String aiServerUnifiedUrl;

    @Value("${ai.server.url.anomaly:http://localhost:8001/api/v1/predict/anomaly}")
    private String aiServerAnomalyUrl;

    public org.springframework.web.servlet.mvc.method.annotation.SseEmitter subscribe(UUID sessionId) {
        return sseEmitters.add(sessionId.toString());
    }

    /**
     * DTC 이력 저장 및 즉시 AI 분석/알림 (비동기 아님 - 외부 API 포함)
     * RabbitMQ 제거 후 직접 호출로 변경
     */
    /**
     * 단일 DTC 처리 (하위 호환성 유지)
     */
    @Transactional
    public void processDtc(DtcDto dtcDto) {
        DtcBatchRequest batchRequest = DtcBatchRequest.builder()
                .vehicleId(dtcDto.getVehicleId())
                .dtcs(List.of(new DtcBatchRequest.DtcInfo(
                        dtcDto.getDtcCode(),
                        "STORED",
                        dtcDto.getStatus() != null ? dtcDto.getStatus() : "ACTIVE")))
                .build();
        processDtcBatch(batchRequest);
    }

    @Transactional
    public void processDtcBatch(DtcBatchRequest request) {
        UUID vehicleId = UUID.fromString(request.getVehicleId());
        Vehicle vehicle = vehicleRepository.findById(vehicleId)
                .orElseThrow(() -> new RuntimeException("Vehicle not found: " + vehicleId));

        List<String> savedCodes = new ArrayList<>();
        List<String> descriptions = new ArrayList<>();
        boolean freezeFrameSaved = false;

        // 1. 모든 DTC 저장
        for (DtcBatchRequest.DtcInfo info : request.getDtcs()) {
            // 상세 정보 조회 (DTC 마스터 테이블 활용)
            Optional<DtcCode> master = dtcCodeRepository.findByCodeGeneric(info.getCode());
            String desc = master.isPresent() ? master.get().getDescriptionKo() : "알 수 없는 고장 코드";

            DtcHistory.DtcType dtcType = parseDtcType(info.getType());
            DtcHistory.DtcStatus dtcStatus = parseDtcStatus(info.getStatus());

            DtcHistory history = DtcHistory.builder()
                    .vehiclesId(vehicleId)
                    .dtcCode(info.getCode())
                    .description(desc)
                    .status(dtcStatus)
                    .dtcType(dtcType)
                    .build();
            history = dtcHistoryRepository.save(history);

            savedCodes.add(info.getCode());
            descriptions.add(desc);

            // 2. Freeze Frame 저장: 첫 번째 DTC에만 1건 저장 (중복 방지)
            if (request.getFreezeFrame() != null && !freezeFrameSaved) {
                DtcFreezeFrame ff = DtcFreezeFrame.builder()
                        .dtcHistory(history)
                        .rpm(request.getFreezeFrame().getRpm())
                        .speed(request.getFreezeFrame().getSpeed())
                        .voltage(request.getFreezeFrame().getVoltage())
                        .coolantTemp(request.getFreezeFrame().getCoolantTemp())
                        .engineLoad(request.getFreezeFrame().getEngineLoad())
                        .fuelTrimShort(request.getFreezeFrame().getFuelTrimShort())
                        .fuelTrimLong(request.getFreezeFrame().getFuelTrimLong())
                        .intakeTemp(request.getFreezeFrame().getIntakeTemp())
                        .map(request.getFreezeFrame().getMap())
                        .maf(request.getFreezeFrame().getMaf())
                        .throttlePos(request.getFreezeFrame().getThrottlePos())
                        .engineRuntime(request.getFreezeFrame().getEngineRuntime())
                        .ambientTemp(request.getFreezeFrame().getAmbientTemp())
                        .fuelPressure(request.getFreezeFrame().getFuelPressure())
                        .pidsSnapshot(request.getFreezeFrame().getPidsSnapshot())
                        .build();
                dtcFreezeFrameRepository.save(ff);
                freezeFrameSaved = true;
            }
        }

        // 3. 통합 알림 발송
        if (!savedCodes.isEmpty()) {
            sendBatchDtcNotification(vehicle, savedCodes, descriptions);
        }

        // 4. DTC 모드 진단 트리거 (비동기)
        if (!request.getDtcs().isEmpty()) {
            try {
                triggerDtcDiagnosis(vehicleId, request.getDtcs());
            } catch (Exception e) {
                log.error("[DTC] Failed to trigger DTC diagnosis for vehicle {}", vehicleId, e);
            }
        }
    }

    /** type 문자열을 DtcType으로 변환. null/unknown 시 STORED fallback */
    private DtcHistory.DtcType parseDtcType(String type) {
        if (type == null || type.isBlank())
            return DtcHistory.DtcType.STORED;
        try {
            return DtcHistory.DtcType.valueOf(type.trim().toUpperCase());
        } catch (IllegalArgumentException e) {
            log.warn("[DTC Batch] Unknown dtc_type '{}', fallback to STORED", type);
            return DtcHistory.DtcType.STORED;
        }
    }

    /** status 문자열을 DtcStatus로 변환. null/unknown 시 ACTIVE fallback */
    private DtcHistory.DtcStatus parseDtcStatus(String status) {
        if (status == null || status.isBlank())
            return DtcHistory.DtcStatus.ACTIVE;
        try {
            return DtcHistory.DtcStatus.valueOf(status.trim().toUpperCase());
        } catch (IllegalArgumentException e) {
            log.warn("[DTC Batch] Unknown status '{}', fallback to ACTIVE", status);
            return DtcHistory.DtcStatus.ACTIVE;
        }
    }

    private void sendBatchDtcNotification(Vehicle vehicle, List<String> codes, List<String> descs) {
        int count = codes.size();
        // 설명 문장에서 끝의 "입니다.", "합니다." 등은 제거해서 TTS 문장이 어색하지 않도록 정규화
        List<String> normalized = descs.stream()
                .limit(2)
                .map(d -> d == null ? "" : d.replaceAll("\\s*(입니다\\.?|합니다\\.?)$", ""))
                .collect(Collectors.toList());
        String summary = String.join(", ", normalized);
        if (count > 2)
            summary += " 등";

        String title = "차량 이상 감지 (" + count + "건)";
        String body = codes.get(0) + " 외 " + (count - 1) + "건의 고장이 감지되었습니다.";

        // 스마트 TTS 문장 생성
        String ttsText = String.format("%d건의 차량 이상이 감지되었습니다. 주요 이상 항목은 %s입니다. 안전한 곳에 정차하신 후 상세 내용을 확인해 주세요.",
                count, summary);
        log.info("[Notification-TTS] vehicle={}, tts={}", vehicle.getVehicleId(), ttsText);

        Map<String, String> data = new HashMap<>();
        data.put("type", "DTC_BATCH_ALERT");
        data.put("codes", String.join(",", codes));
        data.put("tts", ttsText);

        // DB에 알림 저장 및 푸시 발송 (NotificationService 사용)
        User user = userRepository.findById(vehicle.getUserId())
                .orElseThrow(() -> new BaseException(ErrorCode.USER_NOT_FOUND));
        notificationService.sendNotification(user, title, body, Notification.NotificationType.DTC_ALERT, data);
        log.info("[Notification] Sent Batch DTC Alert: vehicle={}, userId={}, codes={}",
                vehicle.getVehicleId(), user.getUserId(), codes);
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

        String imageFile;
        String audioFile;
        try {
            imageFile = (image != null && !image.isEmpty()) ? aiMediaService.uploadMedia(image, "visual") : null;
            audioFile = (audio != null && !audio.isEmpty()) ? aiMediaService.uploadMedia(audio, "audio") : null;
        } catch (Exception e) {
            log.error("Failed to upload media", e);
            throw new RuntimeException("미디어 업로드 실패", e);
        }

        DiagnosisTaskMessage message = DiagnosisTaskMessage.builder()
                .sessionId(session.getDiagSessionId())
                .requestDto(requestDto)
                .messageType(DiagnosisTaskMessage.MessageType.INITIAL)
                .imageUrl(imageFile)
                .audioUrl(audioFile)
                .build();

        // 2-2. 메시지 발행 (Transaction Commit 후 실행)
        org.springframework.transaction.support.TransactionSynchronizationManager.registerSynchronization(
                new org.springframework.transaction.support.TransactionSynchronization() {
                    @Override
                    public void afterCommit() {
                        rabbitTemplate.convertAndSend(kr.co.himedia.config.RabbitConfig.EXCHANGE_NAME,
                                kr.co.himedia.config.RabbitConfig.ROUTING_KEY, message);
                    }
                });

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
            DiagTriggerType triggerType = session.getTriggerType();
            log.error("Unified Diagnosis Pipeline Failed [Session: {}, Trigger: {}] {}", sessionId, triggerType,
                    e.getMessage(), e);
            session.updateStatus(DiagStatus.FAILED, "진단 실패: " + e.getMessage());
            diagSessionRepository.save(session);

            // VISUAL/AUDIO/DATA/ROUTINE 등: 화면에서 SSE 구독 중이면 failed 이벤트 전송
            if (triggerType != DiagTriggerType.AUTO && triggerType != DiagTriggerType.DTC) {
                try {
                    sseEmitters.send(sessionId.toString(), "failed", "진단 실패: " + e.getMessage());
                } catch (Exception sseError) {
                    log.warn("Failed to send FAILED SSE event for session {}", sessionId, sseError);
                }
            }
            // AUTO/DTC: 여기서는 실패 FCM을 보내지 않고, DLQ 컨슈머에서 최종 1회만 발송
            throw new RuntimeException("진단 파이프라인 오류", e);
        }
    }

    private void processInitialPhase(DiagnosisTaskMessage taskMessage, DiagSession session) throws Exception {
        UUID sessionId = session.getDiagSessionId();
        UnifiedDiagnosisRequestDto requestDto = taskMessage.getRequestDto();
        String imageFile = taskMessage.getImageUrl();
        String audioFile = taskMessage.getAudioUrl();

        // 0. SSE 연결 대기 (프론트 구독·연결 시간만 확보, 과도한 대기 제거)
        try {
            log.info("[Diagnosis] Waiting for SSE connection... (2s)");
            Thread.sleep(2000);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }

        // [Step 1] 진단 시작 (RabbitMQ Consumer 진입)
        sseEmitters.send(sessionId.toString(), "step1", "[Step 1/5] 진단 요청이 시스템에 접수되었습니다.");

        // 0. 세션별 통합 리소스 관리 (인당 최대 3개 슬롯 공유)
        java.util.concurrent.Semaphore sessionSemaphore = new java.util.concurrent.Semaphore(3);

        // 1. 병렬 분석 태스크 생성
        CompletableFuture<Map<String, Object>> visualTask = CompletableFuture.supplyAsync(() -> {
            if (imageFile != null) {
                try {
                    log.info("[Visual] [Semaphore-Acquire] 진입 시도 (Global: {}, Session: {})",
                            globalAiSemaphore.availablePermits(), sessionSemaphore.availablePermits());
                    sessionSemaphore.acquire();
                    globalAiSemaphore.acquire();
                    log.info("[Visual] [Semaphore-Acquire] 진입 성공 (Global: {}, Session: {})",
                            globalAiSemaphore.availablePermits(), sessionSemaphore.availablePermits());
                    try {
                        Map<String, Object> result = aiClient.callVisualAnalysis(imageFile, requestDto.getVehicleId(),
                                sessionId);
                        log.info("[Visual] 분석 완료 (Session: {})", sessionId);
                        return result;
                    } finally {
                        globalAiSemaphore.release();
                        sessionSemaphore.release();
                        log.info("[Visual] [Semaphore-Release] 반납 완료 (Global: {}, Session: {})",
                                globalAiSemaphore.availablePermits(), sessionSemaphore.availablePermits());
                    }
                } catch (Exception e) {
                    log.error("[Visual] 분석 실패", e);
                    // 상위 진단 파이프라인에서 FAILED 처리하도록 예외 전파
                    throw new RuntimeException("Visual analysis failed", e);
                }
            }
            return requestDto.getVisualAnalysis();
        });

        CompletableFuture<Map<String, Object>> audioTask = CompletableFuture.supplyAsync(() -> {
            if (audioFile != null) {
                try {
                    log.info("[Audio] [Semaphore-Acquire] 진입 시도 (Global: {}, Session: {})",
                            globalAiSemaphore.availablePermits(), sessionSemaphore.availablePermits());
                    sessionSemaphore.acquire();
                    globalAiSemaphore.acquire();
                    log.info("[Audio] [Semaphore-Acquire] 진입 성공 (Global: {}, Session: {})",
                            globalAiSemaphore.availablePermits(),
                            sessionSemaphore.availablePermits());
                    try {
                        Map<String, Object> result = aiClient.callAudioAnalysis(audioFile, requestDto.getVehicleId(),
                                sessionId);
                        log.info("[Audio] 분석 완료 (Session: {})", sessionId);
                        return result;
                    } finally {
                        globalAiSemaphore.release();
                        sessionSemaphore.release();
                        log.info("[Audio] [Semaphore-Release] 반납 완료 (Global: {}, Session: {})",
                                globalAiSemaphore.availablePermits(), sessionSemaphore.availablePermits());
                    }
                } catch (Exception e) {
                    log.error("[Audio] 분석 실패", e);
                    // 상위 진단 파이프라인에서 FAILED 처리하도록 예외 전파
                    throw new RuntimeException("Audio analysis failed", e);
                }
            }
            return requestDto.getAudioAnalysis();
        });

        CompletableFuture<Map<String, Object>> anomalyTask = CompletableFuture.supplyAsync(() -> {
            return performAnomalyDetection(requestDto, session, sessionSemaphore);
        });

        // [Step 2] 전처리 및 분석 준비 완료 (이미지/오디오 로드됨, 태스크 생성됨)
        sseEmitters.send(sessionId.toString(), "step2", "[Step 2/5] 멀티미디어 및 주행 데이터 전처리 완료");

        // 모든 결과 대기 (15분 단위 청크 처리 등 대량 데이터 분석을 고려하여 10분으로 상향)
        CompletableFuture.allOf(visualTask, audioTask, anomalyTask).get(600, TimeUnit.SECONDS);

        Map<String, Object> visualResult = visualTask.join();
        Map<String, Object> audioResult = audioTask.join();
        Map<String, Object> anomalyResult = anomalyTask.join();

        // [Step 3] AI 병렬 분석 완료
        sseEmitters.send(sessionId.toString(), "step3", "[Step 3/5] AI 정밀 분석 완료 (시각/청각/데이터)");

        // [Filter Logic] LLM 전송: 전부 정상이면 lstm_timeline=[], 하나라도 이상이면 is_anomaly + 해당
        // events만 한 덩어리로 전달
        // [Filter Logic] LLM 전송: 전부 정상이면 lstm_timeline=[], 하나라도 이상이면 is_anomaly + 해당
        // events만 한 덩어리로 전달
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> detailedResults = (List<Map<String, Object>>) anomalyResult.get("detailed_results");
        List<Map<String, Object>> lstmTimeline = new ArrayList<>();

        if (detailedResults != null && !detailedResults.isEmpty()) {
            List<Map<String, Object>> anomalies = detailedResults.stream()
                    .filter(r -> Boolean.TRUE.equals(r.get("is_anomaly")))
                    .collect(Collectors.toList());

            if (anomalies.isEmpty()) {
                // 전부 정상: lstm_timeline은 빈 배열 (is_anomaly=false만 상위에서 전달)
            } else {
                // 하나라도 이상: is_anomaly=true + 해당 청크들의 events를 한 배열로 모아서 한 덩어리로 전달
                List<Map<String, Object>> mergedEvents = new ArrayList<>();
                double maxScore = 0.0;
                for (Map<String, Object> chunk : anomalies) {
                    Object scoreObj = chunk.get("anomaly_score");
                    if (scoreObj instanceof Number) {
                        maxScore = Math.max(maxScore, ((Number) scoreObj).doubleValue());
                    }
                    Object eventsObj = chunk.get("events");
                    if (eventsObj instanceof List) {
                        @SuppressWarnings("unchecked")
                        List<Map<String, Object>> events = (List<Map<String, Object>>) eventsObj;
                        mergedEvents.addAll(events);
                    }
                }
                Map<String, Object> singlePayload = new HashMap<>();
                singlePayload.put("is_anomaly", true);
                singlePayload.put("anomaly_score", maxScore);
                singlePayload.put("events", mergedEvents);
                lstmTimeline.add(singlePayload);
            }
        }

        Map<String, Object> llmAnomalyPayload = new HashMap<>();
        llmAnomalyPayload.put("lstm_timeline", lstmTimeline);
        llmAnomalyPayload.put("is_anomaly", anomalyResult.get("is_anomaly"));

        // 2. 통합 요청 객체 구축 및 RAG 검색
        AiUnifiedRequestDto.AiUnifiedRequestDtoBuilder aiRequestBuilder = AiUnifiedRequestDto.builder()
                .visualAnalysis(visualResult)
                .audioAnalysis(audioResult)
                .anomalyAnalysis(llmAnomalyPayload);

        populateVehicleAndConsumableInfo(aiRequestBuilder, requestDto.getVehicleId());

        // DTC 모드일 경우 dtc_info 추가
        Map<String, Object> dtcInfo = null;
        if (session.getTriggerType() == DiagTriggerType.DTC) {
            dtcInfo = buildDtcInfoForSession(session);
            if (dtcInfo != null) {
                aiRequestBuilder.dtcInfo(dtcInfo);
                log.info("[DTC Mode] Added dtc_info to LLM request for session: {}", sessionId);
            }
        }

        // RAG 검색: 검색에 쓰는 키워드만 정제해 임베딩, 제조사/모델 있으면 필터 검색
        String searchKeywords = buildSearchKeywordsForRag(visualResult, audioResult, anomalyResult, dtcInfo);
        List<String> knowledgeResults = new ArrayList<>();

        Optional<Vehicle> vehicleOpt = vehicleRepository.findById(requestDto.getVehicleId());
        // DTC 정의 정보 우선 추가 (DTC 모드일 경우)
        if (dtcInfo != null && dtcInfo.containsKey("dtc_list")) {
            @SuppressWarnings("unchecked")
            List<Map<String, Object>> dtcList = (List<Map<String, Object>>) dtcInfo.get("dtc_list");
            if (dtcList != null && !dtcList.isEmpty() && vehicleOpt.isPresent()) {
                String manufacturer = vehicleOpt.get().getManufacturerEn();
                for (Map<String, Object> dtcItem : dtcList) {
                    String code = (String) dtcItem.get("code");
                    if (code != null) {
                        List<String> dtcDefs = knowledgeService.searchDtcInformation(code, manufacturer, 2);
                        log.info("[RAG-DTC] Code={}, Manufacturer={}, Results={}", code, manufacturer, dtcDefs.size());
                        if (!dtcDefs.isEmpty()) {
                            log.debug("[RAG-DTC] Contents: {}", dtcDefs);
                        }
                        knowledgeResults.addAll(dtcDefs);
                    }
                }
            }
        }

        // 일반 RAG: 제조사/모델 있으면 필터 검색, 없으면 전체 유사도 검색
        if (!searchKeywords.isEmpty()) {
            String manufacturer = vehicleOpt.map(Vehicle::getManufacturerEn).orElse(null);
            String modelName = vehicleOpt.map(Vehicle::getModelNameEn).orElse(null);
            boolean useFilter = manufacturer != null && !manufacturer.isBlank()
                    && modelName != null && !modelName.isBlank();

            List<String> generalKnowledge;
            if (useFilter) {
                generalKnowledge = knowledgeService.searchKnowledgeWithFilter(
                        searchKeywords, manufacturer, modelName, 3, 0.4);
                log.info("[RAG-General] Filtered query='{}', mfr='{}', model='{}', Results={}",
                        searchKeywords, manufacturer, modelName, generalKnowledge.size());
            } else {
                generalKnowledge = knowledgeService.searchKnowledge(searchKeywords, 3);
                log.info("[RAG-General] Query='{}', Results={}", searchKeywords, generalKnowledge.size());
            }
            if (!generalKnowledge.isEmpty()) {
                log.debug("[RAG-General] Contents: {}", generalKnowledge);
            }
            knowledgeResults.addAll(generalKnowledge);
        }

        if (!knowledgeResults.isEmpty()) {
            aiRequestBuilder.knowledgeData(knowledgeResults);
        }

        // [Step 4] RAG 검색 완료
        sseEmitters.send(sessionId.toString(), "step4", "[Step 4/5] 결함 원인 추론 및 정비 매뉴얼 매칭 완료");

        // 3. 최종 통합 진단 요청 (Phase 1: 6대 항목)
        AiUnifiedRequestDto aiRequest = aiRequestBuilder.build();
        Map<String, Object> llmPayload = objectMapper.convertValue(aiRequest, Map.class);
        logLlmRequest(llmPayload, sessionId);
        Map<String, Object> openAiPayload = buildOpenAiPayload(llmPayload);
        Map<String, Object> finalResponse = openAiDiagnosisService.generateDiagnosisReport(openAiPayload);

        // 4. 결과 저장 및 상태 결정
        DiagStatus finalStatus = saveDiagnosisResult(sessionId, finalResponse, imageFile, audioFile, visualResult,
                audioResult);
        session.updateStatus(finalStatus, finalStatus == DiagStatus.DONE ? "[Step 5/5] 진단 완료 및 저장 성공"
                : "[Step 5/5] 추가 정보 요청됨 (ACTION_REQUIRED)");
        diagSessionRepository.save(session);

        // [Step 5] 최종 완료
        sseEmitters.send(sessionId.toString(), "step5", "[Step 5/5] 최종 진단 리포트 생성 완료");

        // 최종 상태 SSE 전송 (폴링 대체: 프론트에서 즉시 분기 가능)
        DiagnosisResponseDto statusDto = getDiagnosisResult(sessionId);
        sseEmitters.send(sessionId.toString(), "status", statusDto);

        // 6. 알림 발송 (DTC/AUTO만)
        DiagTriggerType triggerType = session.getTriggerType();
        if (triggerType == DiagTriggerType.DTC || triggerType == DiagTriggerType.AUTO) {
            String responseMode = (String) finalResponse.getOrDefault("response_mode", "REPORT");
            sendDiagnosisNotification(requestDto.getVehicleId(), sessionId, responseMode);
        }
    }

    private void processReplyPhase(DiagnosisTaskMessage taskMessage, DiagSession session) throws Exception {
        UUID sessionId = session.getDiagSessionId();
        ReplyRequestDto replyDto = taskMessage.getReplyRequest();
        String imageFile = taskMessage.getImageUrl();
        String audioFile = taskMessage.getAudioUrl();

        session.updateStatus(DiagStatus.REPLY_PROCESSING, "[Chat] AI가 답변을 분석 중입니다...");
        diagSessionRepository.save(session);

        DiagResult existingResult = diagResultRepository.findByDiagSessionId(sessionId)
                .orElseThrow(() -> new RuntimeException("DiagResult not found for session: " + sessionId));

        // 1. 기존 대화 이력 파싱
        List<Map<String, Object>> conversation = new ArrayList<>();
        if (existingResult.getInteractiveJson() != null) {
            Map<String, Object> interactiveData = objectMapper.readValue(existingResult.getInteractiveJson(),
                    Map.class);
            @SuppressWarnings("unchecked")
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
            visualResult = aiClient.callVisualAnalysis(imageFile, session.getVehiclesId(), sessionId);
            saveEvidences(sessionId, imageFile, null, visualResult, null);
        }

        Map<String, Object> audioResult = null;
        if (audioFile != null) {
            audioResult = aiClient.callAudioAnalysis(audioFile, session.getVehiclesId(), sessionId);
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

        // DTC 모드일 경우 dtc_info 재사용
        if (session.getTriggerType() == DiagTriggerType.DTC) {
            Map<String, Object> dtcInfo = buildDtcInfoForSession(session);
            if (dtcInfo != null) {
                aiRequestBuilder.dtcInfo(dtcInfo);
                log.info("[DTC Mode Reply] Reusing dtc_info for session: {}", sessionId);
            }
        }

        // 필요 시 신규 분석 결과도 최상위에 포함
        if (visualResult != null)
            aiRequestBuilder.visualAnalysis(visualResult);
        if (audioResult != null)
            aiRequestBuilder.audioAnalysis(audioResult);

        Map<String, Object> replyLlmPayload = objectMapper.convertValue(aiRequestBuilder.build(), Map.class);
        logLlmRequest(replyLlmPayload, sessionId);
        Map<String, Object> openAiPayload = buildOpenAiPayload(replyLlmPayload);
        Map<String, Object> aiResponse = openAiDiagnosisService.generateReplyResponse(openAiPayload, conversation);

        // 5. 결과 저장 및 상태 업데이트
        long userTurnCount = conversation.stream().filter(t -> "user".equals(t.get("role"))).count();
        log.info("[Reply] User Turn Count: {}", userTurnCount);

        String effectiveMode = updateReplyResult(sessionId, aiResponse, conversation, userTurnCount, existingResult);

        DiagStatus finalStatus = "REPORT".equalsIgnoreCase(effectiveMode) ? DiagStatus.DONE
                : DiagStatus.ACTION_REQUIRED;
        session.updateStatus(finalStatus, finalStatus == DiagStatus.DONE ? "최종 진단 리포트가 생성되었습니다." : "추가 정보를 기다리고 있습니다.");
        diagSessionRepository.save(session);

        // 6. 알림 발송 (Reply 단계에서는 불필요 - 이미 대화 중)
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
        Double confidenceScore = parseConfidenceScore(aiResponse.get("confidence_score"));
        DiagResult.DiagResultBuilder resultBuilder = DiagResult.builder()
                .diagSessionId(sessionId)
                .responseMode(mode)
                .confidenceLevel((String) aiResponse.getOrDefault("confidence_level", "LOW"))
                .confidenceScore(confidenceScore)
                .summary((String) aiResponse.getOrDefault("summary", ""));

        DiagAction requestedAction = getRequestedActionForColumn(aiResponse);
        if (requestedAction != null) {
            resultBuilder.requestedAction(requestedAction);
        }

        if ("REPORT".equalsIgnoreCase(mode)) {
            // ... (기존 REPORT 저장 로직과 동일하거나 간소화)
            @SuppressWarnings("unchecked")
            Map<String, Object> reportData = (Map<String, Object>) aiResponse.get("report_data");
            resultBuilder
                    .finalReport(reportData != null ? (String) reportData.get("final_guide") : "원인 파악 중 오류가 발생했습니다.");
            resultBuilder.detectedIssues(objectMapper
                    .writeValueAsString(reportData != null ? reportData.get("suspected_causes") : List.of()));
            resultBuilder.riskLevel(DiagResult.RiskLevel.LOW);
        } else {
            @SuppressWarnings("unchecked")
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
                User user = userRepository.findById(vehicle.getUserId()).orElse(null);
                if (user == null) {
                    return;
                }
                boolean isInteractive = "INTERACTIVE".equalsIgnoreCase(responseMode);
                String title = isInteractive ? "[확인 필요] 차량 진단 추가 요청" : "차량 정밀 진단 완료";
                String body = isInteractive ? "정확한 분석을 위해 사진 촬영이나 소음 녹음이 필요합니다. 대화를 이어가보세요."
                        : "요청하신 차량의 AI 정밀 진단 분석이 완료되었습니다. 결과를 확인해보세요.";

                Map<String, String> data = new HashMap<>();
                data.put("type", isInteractive ? "DIAG_INTERACTIVE" : "DIAG_COMPLETE");
                data.put("sessionId", sessionId.toString());
                data.put("mode", responseMode);

                notificationService.sendNotification(user, title, body, Notification.NotificationType.DIAG_ALERT, data);
                log.info("Sent Diagnosis Notification (saved + push) [Vehicle: {}, Mode: {}]", vehicleId, responseMode);
            });
        } catch (Exception e) {
            log.error("Failed to send diagnosis notification", e);
        }
    }

    private void sendDiagnosisFailureNotification(UUID vehicleId, UUID sessionId, String failureMessage) {
        try {
            vehicleRepository.findById(vehicleId).ifPresent(vehicle -> {
                User user = userRepository.findById(vehicle.getUserId()).orElse(null);
                if (user == null) {
                    return;
                }
                String title = "차량 진단 실패";
                String body = "AI 진단 분석 중 오류가 발생했습니다. 다시 시도해 주세요.";

                Map<String, String> data = new HashMap<>();
                data.put("type", "DIAG_FAILED");
                data.put("sessionId", sessionId.toString());
                data.put("message", failureMessage != null ? failureMessage : "알 수 없는 오류");

                notificationService.sendNotification(user, title, body, Notification.NotificationType.DIAG_ALERT, data);
                log.info("Sent Diagnosis Failure Notification [Vehicle: {}, Session: {}]", vehicleId, sessionId);
            });
        } catch (Exception e) {
            log.error("Failed to send diagnosis failure notification [Vehicle: {}, Session: {}]", vehicleId, sessionId, e);
        }
    }

    private Map<String, Object> performAnomalyDetection(UnifiedDiagnosisRequestDto requestDto,
            DiagSession session, java.util.concurrent.Semaphore sessionSemaphore) {
        try {
            java.util.UUID sessionId = session.getDiagSessionId();
            DiagTriggerType triggerType = session.getTriggerType();
            UUID vehicleId = requestDto.getVehicleId();
            List<List<Map<String, Object>>> chunks = new ArrayList<>();

            // trip_id: 세션에 트립이 연결되어 있으면 사용, 없으면 session-{sessionId}
            UUID tripId = session.getTripId();

            // 타이어 압력: vehicles.cloud_linked == true 일 때만 최신 cloud_telemetry에서 채움. null 컬럼은
            // 제외
            final Map<String, Double> tirePressureForPayload = getTirePressureForVehicle(vehicleId);

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
                log.info("[Anomaly] {} 모드: 최근 3일 데이터 조회 및 청크화 (날짜 기준)", triggerType);
                java.time.ZoneOffset utc = java.time.ZoneOffset.UTC;
                java.time.LocalDate todayUtc = java.time.LocalDate.now(utc);
                // 3일 = 오늘 포함 과거 3일 (예: 2/9면 2/7, 2/8, 2/9) — 2/10 미포함
                java.time.OffsetDateTime rangeStart = todayUtc.minusDays(2).atStartOfDay(utc).toOffsetDateTime();
                java.time.OffsetDateTime rangeEnd = todayUtc.atTime(23, 59, 59, 999_999_999).atOffset(utc);
                List<ObdLog> allLogs = obdLogRepository.findByVehicleIdAndTimeBetweenOrderByTimeAsc(vehicleId,
                        rangeStart, rangeEnd);
                int totalLogs = allLogs.size();
                chunks = chunkByTripAndSubdivide(allLogs, 900);
                log.info("[Anomaly] 3일치 조회: {}건 ({} ~ {}), 트립 그룹 분할 후 청크 수: {} (15분 단위)",
                        totalLogs, rangeStart.toLocalDate(), rangeEnd.toLocalDate(), chunks.size());
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

                            Map<String, Object> payload = buildObdAnomalyRequestPayload(
                                    requestDto.getVehicleId().toString(),
                                    sessionId.toString(),
                                    chunk,
                                    tripId,
                                    tirePressureForPayload);

                            log.info(
                                    "[Anomaly-Parallel] 청크 전송 시작 ({}/{}) [Vehicle: {}, Session: {}]",
                                    chunkIndex, totalChunks, requestDto.getVehicleId(), sessionId);
                            logAnomalyRequest(payload);

                            Map<String, Object> response = aiClient.callAnomalyDetection(payload);
                            logAnomalyResponse(response, chunkIndex, totalChunks);
                            return response;
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

            // 3. 결과 취합: meta/domains/events/is_anomaly/anomaly_score만 사용 (window_results
            // 미사용)
            boolean isAnyAnomaly = results.stream()
                    .anyMatch(r -> r.get("is_anomaly") != null && (boolean) r.get("is_anomaly"));

            log.info("[Anomaly] 분석 완료. 이상 징후 발견 여부: {}", isAnyAnomaly);

            List<String> contributingFactors = collectContributingFactorsFromResults(results);

            Map<String, Object> aggregated = new HashMap<>();
            aggregated.put("is_anomaly", isAnyAnomaly);
            aggregated.put("detailed_results", results);
            aggregated.put("chunk_count", chunks.size());
            aggregated.put("contributing_factors", contributingFactors);
            return aggregated;

        } catch (Exception e) {
            log.error("Anomaly detection failed", e);
            // 상위 통합 진단 플로우에서 FAILED로 처리하도록 예외 전파
            throw new RuntimeException("Anomaly detection failed", e);
        }
    }

    /**
     * 청크별 응답 목록에서 이상(anomaly) 청크의 events를 바탕으로 contributing_factors 수집 (RAG 검색용).
     */
    private List<String> collectContributingFactorsFromResults(List<Map<String, Object>> results) {
        java.util.Set<String> factors = new java.util.LinkedHashSet<>();
        for (Map<String, Object> r : results) {
            if (!Boolean.TRUE.equals(r.get("is_anomaly"))) {
                continue;
            }
            Object eventsObj = r.get("events");
            if (!(eventsObj instanceof List)) {
                continue;
            }
            @SuppressWarnings("unchecked")
            List<Map<String, Object>> events = (List<Map<String, Object>>) eventsObj;
            for (Map<String, Object> ev : events) {
                addNonBlank(ev.get("feature"), factors);
                addNonBlank(ev.get("domain"), factors);
                addNonBlank(ev.get("message"), factors);
            }
        }
        return new ArrayList<>(factors);
    }

    private void addNonBlank(Object value, java.util.Set<String> out) {
        if (value != null) {
            String s = value.toString().trim();
            if (!s.isEmpty()) {
                out.add(s);
            }
        }
    }

    /**
     * cloud_linked == true 인 차량만 최신 cloud_telemetry에서 타이어 압력 조회. null 컬럼은 제외.
     */
    private Map<String, Double> getTirePressureForVehicle(UUID vehicleId) {
        return vehicleRepository.findById(vehicleId)
                .filter(v -> Boolean.TRUE.equals(v.getCloudLinked()))
                .flatMap(vehicle -> {
                    List<CloudTelemetry> list = cloudTelemetryRepository.findByVehicleOrderByLastSyncedAtDesc(vehicle);
                    if (list.isEmpty())
                        return Optional.<Map<String, Double>>empty();
                    CloudTelemetry ct = list.get(0);
                    Map<String, Double> map = new HashMap<>();
                    if (ct.getTirePressureFl() != null)
                        map.put("tire_pressure_fl_kpa", ct.getTirePressureFl());
                    if (ct.getTirePressureFr() != null)
                        map.put("tire_pressure_fr_kpa", ct.getTirePressureFr());
                    if (ct.getTirePressureRl() != null)
                        map.put("tire_pressure_rl_kpa", ct.getTirePressureRl());
                    if (ct.getTirePressureRr() != null)
                        map.put("tire_pressure_rr_kpa", ct.getTirePressureRr());
                    return map.isEmpty() ? Optional.<Map<String, Double>>empty() : Optional.of(map);
                })
                .orElse(null);
    }

    /**
     * ObdAnomalyRequest 스키마에 맞는 페이로드 생성.
     * tripId가 있으면 사용, 없으면 session-{sessionId}. cloud_linked 시 tirePressureKpa를 각 샘플
     * features에 넣음.
     */
    private Map<String, Object> buildObdAnomalyRequestPayload(String vehicleId, String sessionId,
            List<Map<String, Object>> chunk, UUID tripIdOrNull, Map<String, Double> tirePressureKpa) {
        List<Map<String, Object>> data = new ArrayList<>();
        int t = 0;
        for (Map<String, Object> row : chunk) {
            Map<String, Object> features = new HashMap<>();
            // Core7 스키마에 맞게 키 매핑
            putIfNumber(row, features, "rpm", "engine_rpm");
            putIfNumber(row, features, "speed", "vehicle_speed_kmh");
            putIfNumber(row, features, "coolant", "engine_coolant_temp_c");
            putIfNumber(row, features, "coolantTemp", "engine_coolant_temp_c");
            putIfNumber(row, features, "map", "imap_kpa");
            putIfNumber(row, features, "intakeTemp", "intake_air_temp_c");
            putIfNumber(row, features, "maf", "maf_gps");
            putIfNumber(row, features, "throttlePos", "throttle_pos_pct");
            putIfNumber(row, features, "voltage", "battery_voltage_v");
            if (tirePressureKpa != null && !tirePressureKpa.isEmpty()) {
                features.putAll(tirePressureKpa);
            }
            if (!features.isEmpty()) {
                data.add(Map.of("t", t, "features", features));
                t++;
            }
        }
        int durationSec = data.size();
        if (durationSec == 0) {
            durationSec = 1;
        }
        Map<String, Object> options = new HashMap<>();
        options.put("window_sec", 60);
        options.put("stride_sec", 60);

        String tripIdStr = (tripIdOrNull != null) ? tripIdOrNull.toString() : ("session-" + sessionId);

        Map<String, Object> payload = new HashMap<>();
        payload.put("vehicle_id", vehicleId);
        payload.put("trip_id", tripIdStr);
        payload.put("mode", "DRIVING");
        payload.put("duration_sec", durationSec);
        payload.put("sampling_hz", 1);
        payload.put("timestamp_unit", "s");
        payload.put("data", data);
        payload.put("options", options);
        return payload;
    }

    private void putIfNumber(Map<String, Object> source, Map<String, Object> target, String sourceKey,
            String targetKey) {
        Object v = source.get(sourceKey);
        if (v instanceof Number) {
            target.put(targetKey, v);
        }
    }

    private void logAnomalyRequest(Map<String, Object> payload) {
        try {
            Map<String, Object> forLog = new HashMap<>(payload);
            if (forLog.containsKey("data")) {
                Object data = forLog.get("data");
                int size = data instanceof List ? ((List<?>) data).size() : 0;
                forLog.put("data", "[size=" + size + "]");
            }
            log.info("[Anomaly] Request: {}", objectMapper.writeValueAsString(forLog));
        } catch (Exception e) {
            log.warn("[Anomaly] Request log failed: {}", e.getMessage());
        }
    }

    private void logAnomalyResponse(Map<String, Object> response, int chunkIndex, int totalChunks) {
        try {
            if (response == null) {
                log.info("[Anomaly] Response (chunk {}/{}): null", chunkIndex, totalChunks);
                return;
            }
            Map<String, Object> forLog = new HashMap<>(response);
            if (forLog.containsKey("window_results")) {
                Object wr = forLog.get("window_results");
                int size = wr instanceof List ? ((List<?>) wr).size() : 0;
                forLog.put("window_results", "[size=" + size + "]");
            }
            log.info("[Anomaly] Response (chunk {}/{}): {}", chunkIndex, totalChunks,
                    objectMapper.writeValueAsString(forLog));
        } catch (Exception e) {
            log.warn("[Anomaly] Response log failed: {}", e.getMessage());
        }
    }

    /**
     * 요약/통합 처리 후 LLM(Comprehensive Diagnosis)에 보내는 요청 payload 로깅.
     * knowledge_data, conversation_history는 길이만 [size=N]으로 표기.
     */
    /**
     * AiUnifiedRequestDto 기반 Map을 OpenAI 진단 입력 스펙으로 변환한다.
     * diagnosis_context는 보내지 않으며, vehicle_info, dtc_info, consumables_status,
     * analysis_results, rag_context만 포함.
     * consumables_status는 "관련 항목만" 필터: 주의 필요(잔여수명 이하) + DTC 시 엔진/배기 관련 + 핵심 항목 항상
     * 포함.
     */
    private Map<String, Object> buildOpenAiPayload(Map<String, Object> llmPayload) {
        Map<String, Object> analysisResults = new HashMap<>();
        analysisResults.put("sound", getOrNull(llmPayload, "audio_analysis", "audioAnalysis"));
        analysisResults.put("image", getOrNull(llmPayload, "visual_analysis", "visualAnalysis"));
        analysisResults.put("lstm", getOrNull(llmPayload, "anomaly_analysis", "anomalyAnalysis"));

        Object rawConsumables = getOrNull(llmPayload, "consumables_status", "consumablesStatus");
        Object dtcInfo = getOrNull(llmPayload, "dtc_info", "dtcInfo");
        List<Map<String, Object>> filteredConsumables = filterConsumablesForLlm(rawConsumables, dtcInfo != null);

        Map<String, Object> openAiPayload = new LinkedHashMap<>();
        putIfNotNull(openAiPayload, "vehicle_info", getOrNull(llmPayload, "vehicle_info", "vehicleInfo"));
        putIfNotNull(openAiPayload, "dtc_info", dtcInfo);
        if (!filteredConsumables.isEmpty()) {
            openAiPayload.put("consumables_status", filteredConsumables);
        }
        openAiPayload.put("analysis_results", analysisResults);
        putIfNotNull(openAiPayload, "rag_context", getOrNull(llmPayload, "knowledge_data", "knowledgeData"));
        return openAiPayload;
    }

    /**
     * LLM에 보낼 소모품만 필터: 주의 필요(remaining_life_pct <= 80) + DTC 시 엔진/배기 관련 + 항상 포함 핵심
     * 항목.
     */
    @SuppressWarnings("unchecked")
    private List<Map<String, Object>> filterConsumablesForLlm(Object consumablesStatus, boolean hasDtc) {
        if (consumablesStatus == null) {
            return Collections.emptyList();
        }
        if (!(consumablesStatus instanceof List)) {
            return Collections.emptyList();
        }
        List<Map<String, Object>> list = (List<Map<String, Object>>) consumablesStatus;
        Set<String> included = new HashSet<>();
        List<Map<String, Object>> result = new ArrayList<>();
        for (Map<String, Object> item : list) {
            Object codeObj = item.get("item");
            String code = codeObj != null ? codeObj.toString() : null;
            if (code == null || code.isBlank()) {
                continue;
            }
            double pct = parseRemainingLifePct(item.get("remaining_life_pct"));
            boolean needsAttention = pct <= CONSUMABLE_ATTENTION_THRESHOLD_PCT;
            boolean alwaysInclude = CONSUMABLE_CODES_ALWAYS.contains(code);
            boolean dtcRelated = hasDtc && CONSUMABLE_CODES_DTC_RELATED.contains(code);
            if (needsAttention || alwaysInclude || dtcRelated) {
                if (included.add(code)) {
                    result.add(new LinkedHashMap<>(item));
                }
            }
        }
        if (log.isDebugEnabled()) {
            log.debug("[Consumables] Filtered for LLM: {} items (hasDtc={})", result.size(), hasDtc);
        }
        return result;
    }

    private static double parseRemainingLifePct(Object value) {
        if (value == null) {
            return 100.0;
        }
        if (value instanceof Number) {
            return ((Number) value).doubleValue();
        }
        if (value instanceof String) {
            String s = ((String) value).trim();
            if (s.equalsIgnoreCase("NaN") || s.isEmpty()) {
                return 100.0;
            }
            try {
                return Double.parseDouble(s);
            } catch (NumberFormatException e) {
                return 100.0;
            }
        }
        return 100.0;
    }

    private static Object getOrNull(Map<String, Object> map, String... keys) {
        for (String key : keys) {
            if (map.containsKey(key) && map.get(key) != null) {
                return map.get(key);
            }
        }
        return null;
    }

    private static void putIfNotNull(Map<String, Object> target, String key, Object value) {
        if (value != null) {
            target.put(key, value);
        }
    }

    private void logLlmRequest(Map<String, Object> payload, UUID sessionId) {
        try {
            Map<String, Object> forLog = new HashMap<>(payload);
            if (forLog.containsKey("knowledge_data")) {
                Object v = forLog.get("knowledge_data");
                int size = v instanceof List ? ((List<?>) v).size() : 0;
                forLog.put("knowledge_data", "[size=" + size + "]");
            }
            if (forLog.containsKey("conversation_history")) {
                Object v = forLog.get("conversation_history");
                int size = v instanceof List ? ((List<?>) v).size() : 0;
                forLog.put("conversation_history", "[size=" + size + "]");
            }
            log.info("[LLM] Request (session={}): {}", sessionId, objectMapper.writeValueAsString(forLog));
        } catch (Exception e) {
            log.warn("[LLM] Request log failed: {}", e.getMessage());
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
                // OBD 로그에서 Core7 피처에 대응되는 값 추출
                p.put("rpm", l.getRpm());
                p.put("speed", l.getSpeed());
                p.put("coolant", l.getCoolantTemp());
                p.put("map", l.getMap());
                p.put("intakeTemp", l.getIntakeTemp());
                p.put("maf", l.getMaf());
                p.put("throttlePos", l.getThrottlePos());
                // 기타 참조용 피처는 그대로 유지
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
            // Upsert Logic: 기존 결과가 있으면 업데이트, 없으면 생성
            DiagResult existingResult = diagResultRepository.findByDiagSessionId(sessionId).orElse(null);

            String mode = (String) response.getOrDefault("response_mode", "REPORT");
            String confidence = (String) response.getOrDefault("confidence_level", "LOW");
            Double confidenceScore = parseConfidenceScore(response.get("confidence_score"));
            String summary = (String) response.getOrDefault("summary", "");

            DiagResult.DiagResultBuilder resultBuilder;
            if (existingResult != null) {
                // Update existing result using its ID
                resultBuilder = DiagResult.builder()
                        .diagResultId(existingResult.getDiagResultId())
                        .diagSessionId(sessionId);
            } else {
                // Create new result
                resultBuilder = DiagResult.builder()
                        .diagSessionId(sessionId);
            }

            resultBuilder.responseMode(mode)
                    .confidenceLevel(confidence)
                    .confidenceScore(confidenceScore)
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
                DiagAction requestedAction = getRequestedActionForColumn(response);
                if (requestedAction != null) {
                    resultBuilder.requestedAction(requestedAction);
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

    private static Double parseConfidenceScore(Object value) {
        if (value == null)
            return null;
        if (value instanceof Number)
            return ((Number) value).doubleValue();
        try {
            return Double.valueOf(value.toString());
        } catch (NumberFormatException e) {
            return null;
        }
    }

    /**
     * interactive_data.request_type (CAPTURE_PHOTO | RECORD_SOUND |
     * ANSWER_QUESTION) 또는
     * requested_actions/ follow_up_questions에서 추론해 DB requested_action 컬럼용
     * DiagAction 반환.
     */
    @SuppressWarnings("unchecked")
    private DiagAction getRequestedActionForColumn(Map<String, Object> response) {
        Map<String, Object> interactiveData = (Map<String, Object>) response.get("interactive_data");
        if (interactiveData != null) {
            Object rt = interactiveData.get("request_type");
            if (rt != null && rt.toString().trim().length() > 0) {
                String s = rt.toString().trim().toUpperCase();
                if ("CAPTURE_PHOTO".equals(s))
                    return DiagAction.CAPTURE_PHOTO;
                if ("RECORD_SOUND".equals(s))
                    return DiagAction.RECORD_AUDIO;
                if ("ANSWER_QUESTION".equals(s))
                    return DiagAction.ANSWER_TEXT;
            }
            Object ra = interactiveData.get("requested_actions");
            if (ra instanceof List && !((List<?>) ra).isEmpty()) {
                Object first = ((List<?>) ra).get(0);
                if (first instanceof Map) {
                    Object at = ((Map<?, ?>) first).get("action_type");
                    if (at != null) {
                        String s = at.toString().trim().toUpperCase();
                        if ("CAPTURE_PHOTO".equals(s))
                            return DiagAction.CAPTURE_PHOTO;
                        if ("RECORD_SOUND".equals(s))
                            return DiagAction.RECORD_AUDIO;
                        if ("ANSWER_QUESTION".equals(s))
                            return DiagAction.ANSWER_TEXT;
                    }
                }
            }
            if (interactiveData.get("follow_up_questions") instanceof List
                    && !((List<?>) interactiveData.get("follow_up_questions")).isEmpty()) {
                return DiagAction.ANSWER_TEXT;
            }
        }
        return null;
    }

    /**
     * requested_actions is inside interactive_data per prompt; fallback to root for
     * compatibility.
     */
    @SuppressWarnings("unchecked")
    private List<String> getRequestedActionsFromResponse(Map<String, Object> response) {
        Map<String, Object> interactiveData = (Map<String, Object>) response.get("interactive_data");
        if (interactiveData != null && interactiveData.get("requested_actions") != null) {
            Object raw = interactiveData.get("requested_actions");
            if (raw instanceof List)
                return (List<String>) raw;
        }
        if (response.get("requested_actions") != null && response.get("requested_actions") instanceof List) {
            return (List<String>) response.get("requested_actions");
        }
        return Collections.emptyList();
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
            String responseMode = result.getResponseMode();
            if (session.getStatus() == DiagStatus.ACTION_REQUIRED && !"INTERACTIVE".equalsIgnoreCase(responseMode)) {
                responseMode = "INTERACTIVE";
            }
            builder.responseMode(responseMode)
                    .confidenceLevel(result.getConfidenceLevel())
                    .confidenceScore(result.getConfidenceScore())
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
        } else if (session.getStatus() == DiagStatus.ACTION_REQUIRED) {
            builder.responseMode("INTERACTIVE");
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
            String responseMode = result != null ? result.getResponseMode() : null;
            if (session.getStatus() == DiagStatus.ACTION_REQUIRED && !"INTERACTIVE".equalsIgnoreCase(responseMode)) {
                responseMode = "INTERACTIVE";
            }

            return DiagnosisListItemDto.builder()
                    .sessionId(session.getDiagSessionId())
                    .status(session.getStatus().name())
                    .progressMessage(session.getProgressMessage())
                    .triggerType(session.getTriggerType().name())
                    .triggerTypeLabel(getTriggerTypeLabel(session.getTriggerType()))
                    .responseMode(responseMode)
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

    /**
     * DTC 모드 진단 트리거
     */
    private void triggerDtcDiagnosis(UUID vehicleId, List<DtcBatchRequest.DtcInfo> dtcs) {
        log.info("[DTC Trigger] Starting DTC diagnosis for vehicle: {}, DTCs: {}", vehicleId,
                dtcs.stream().map(DtcBatchRequest.DtcInfo::getCode).collect(Collectors.toList()));

        // 1. DTC 컨텍스트 JSON 생성
        List<Map<String, Object>> dtcList = new ArrayList<>();
        for (DtcBatchRequest.DtcInfo info : dtcs) {
            Optional<DtcCode> master = dtcCodeRepository.findByCodeGeneric(info.getCode());

            Map<String, Object> dtcItem = new HashMap<>();
            dtcItem.put("code", info.getCode());
            dtcItem.put("name_en", master.map(DtcCode::getDescriptionEn)
                    .filter(s -> s != null && !s.isBlank())
                    .orElse(master.map(DtcCode::getDescriptionKo).orElse("Unknown DTC")));
            dtcItem.put("status", info.getStatus() != null ? info.getStatus() : "ACTIVE");
            if (info.getType() != null) {
                dtcItem.put("type", info.getType());
            }
            dtcList.add(dtcItem);
        }

        Map<String, Object> dtcContext = new HashMap<>();
        dtcContext.put("dtc_list", dtcList);

        try {
            String dtcContextJson = objectMapper.writeValueAsString(dtcContext);

            // 2. DiagSession 생성 (또는 기존 PENDING/FAILED 재사용)
            DiagSession session = diagSessionRepository
                    .findFirstByVehiclesIdAndStatusOrderByCreatedAtDesc(vehicleId, DiagStatus.PENDING)
                    .orElseGet(() -> diagSessionRepository
                            .findFirstByVehiclesIdAndStatusOrderByCreatedAtDesc(vehicleId, DiagStatus.FAILED)
                            .orElse(null));

            if (session != null && session.getTriggerType() == DiagTriggerType.DTC) {
                log.info("[DTC Trigger] Reusing existing DTC session: {}", session.getDiagSessionId());
                session.setDtcContextJson(dtcContextJson);
                session.updateStatus(DiagStatus.PENDING, "DTC 진단 대기 중 (재요청)");
            } else {
                session = new DiagSession(vehicleId, null, DiagTriggerType.DTC);
                session.setDtcContextJson(dtcContextJson);
            }
            session = diagSessionRepository.save(session);

            // 3. UnifiedDiagnosisRequestDto 생성 및 진단 요청
            UnifiedDiagnosisRequestDto requestDto = UnifiedDiagnosisRequestDto.builder()
                    .vehicleId(vehicleId)
                    .build();

            DiagnosisTaskMessage message = DiagnosisTaskMessage.builder()
                    .sessionId(session.getDiagSessionId())
                    .requestDto(requestDto)
                    .messageType(DiagnosisTaskMessage.MessageType.INITIAL)
                    .build();

            // 4. RabbitMQ 발행 (Transaction Commit 후 실행)
            UUID finalSessionId = session.getDiagSessionId();
            org.springframework.transaction.support.TransactionSynchronizationManager.registerSynchronization(
                    new org.springframework.transaction.support.TransactionSynchronization() {
                        @Override
                        public void afterCommit() {
                            rabbitTemplate.convertAndSend(kr.co.himedia.config.RabbitConfig.EXCHANGE_NAME,
                                    kr.co.himedia.config.RabbitConfig.ROUTING_KEY, message);
                            log.info("[DTC Trigger] Diagnosis message published for session: {}", finalSessionId);
                        }
                    });

        } catch (Exception e) {
            log.error("[DTC Trigger] Failed to trigger diagnosis for vehicle: {}", vehicleId, e);
            throw new RuntimeException("DTC 진단 트리거 실패", e);
        }
    }

    /**
     * 세션에 저장된 DTC 정보를 Map으로 구성
     */
    private Map<String, Object> buildDtcInfoForSession(DiagSession session) {
        if (session.getDtcContextJson() == null || session.getDtcContextJson().isBlank()) {
            return null;
        }

        try {
            @SuppressWarnings("unchecked")
            Map<String, Object> dtcContext = objectMapper.readValue(session.getDtcContextJson(), Map.class);
            return dtcContext;
        } catch (Exception e) {
            log.error("[DTC Info] Failed to parse dtcContextJson for session: {}", session.getDiagSessionId(), e);
            return null;
        }
    }

    /**
     * DTC를 포함한 RAG 검색 쿼리 구성
     */
    private String buildSearchQueryWithDtc(Map<String, Object> visualResult, Map<String, Object> audioResult,
            Map<String, Object> anomalyResult, Map<String, Object> dtcInfo) {
        StringBuilder searchQuery = new StringBuilder();

        // 기존 이상탐지/이미지/소리 키워드
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
                searchQuery.append(String.join(" ", factors)).append(" 이상징후 ");
            }
        }

        // DTC 키워드 추가
        if (dtcInfo != null && dtcInfo.containsKey("dtc_list")) {
            @SuppressWarnings("unchecked")
            List<Map<String, Object>> dtcList = (List<Map<String, Object>>) dtcInfo.get("dtc_list");
            if (dtcList != null && !dtcList.isEmpty()) {
                for (Map<String, Object> dtc : dtcList) {
                    String code = (String) dtc.get("code");
                    String nameEn = (String) dtc.get("name_en");
                    if (code != null) {
                        searchQuery.append(code).append(" ");
                    }
                    if (nameEn != null) {
                        searchQuery.append(nameEn).append(" ");
                    }
                }
            }
        }

        return searchQuery.toString().trim();
    }

    /**
     * RAG 검색용 키워드만 수집·정제 (중복 제거, 순서 고정). 이 문자열을 임베딩해 벡터 검색에 사용한다.
     */
    private String buildSearchKeywordsForRag(Map<String, Object> visualResult, Map<String, Object> audioResult,
            Map<String, Object> anomalyResult, Map<String, Object> dtcInfo) {
        Set<String> tokens = new LinkedHashSet<>();
        if (visualResult != null && visualResult.containsKey("category")) {
            Object cat = visualResult.get("category");
            if (cat != null && !cat.toString().isBlank()) {
                tokens.add(cat.toString().trim());
            }
        }
        if (audioResult != null && audioResult.containsKey("status")) {
            Object status = audioResult.get("status");
            if (status != null && !status.toString().isBlank()) {
                tokens.add(status.toString().trim());
            }
        }
        if (anomalyResult != null && Boolean.TRUE.equals(anomalyResult.get("is_anomaly"))) {
            @SuppressWarnings("unchecked")
            List<String> factors = (List<String>) anomalyResult.get("contributing_factors");
            if (factors != null) {
                for (String f : factors) {
                    if (f != null && !f.isBlank()) {
                        tokens.add(f.trim());
                    }
                }
                if (!factors.isEmpty()) {
                    tokens.add("이상징후");
                }
            }
        }
        if (dtcInfo != null && dtcInfo.containsKey("dtc_list")) {
            @SuppressWarnings("unchecked")
            List<Map<String, Object>> dtcList = (List<Map<String, Object>>) dtcInfo.get("dtc_list");
            if (dtcList != null) {
                for (Map<String, Object> dtc : dtcList) {
                    String code = (String) dtc.get("code");
                    if (code != null && !code.isBlank()) {
                        tokens.add(code.trim());
                    }
                    String nameEn = (String) dtc.get("name_en");
                    if (nameEn != null && !nameEn.isBlank()) {
                        tokens.add(nameEn.trim());
                    }
                }
            }
        }
        return String.join(" ", tokens);
    }

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

        // 2. 미디어 파일 S3 업로드
        String imageFile;
        String audioFile;
        try {
            imageFile = (additionalImage != null && !additionalImage.isEmpty())
                    ? aiMediaService.uploadMedia(additionalImage, "reply_visual")
                    : null;
            audioFile = (additionalAudio != null && !additionalAudio.isEmpty())
                    ? aiMediaService.uploadMedia(additionalAudio, "reply_audio")
                    : null;
        } catch (Exception e) {
            log.error("Failed to upload reply media", e);
            throw new RuntimeException("답변 미디어 업로드 실패", e);
        }

        // 3. RabbitMQ 메시지 발행
        DiagnosisTaskMessage message = DiagnosisTaskMessage.builder()
                .sessionId(sessionId)
                .replyRequest(replyDto)
                .messageType(DiagnosisTaskMessage.MessageType.REPLY)
                .imageUrl(imageFile)
                .audioUrl(audioFile)
                .build();

        rabbitTemplate.convertAndSend(kr.co.himedia.config.RabbitConfig.EXCHANGE_NAME,
                kr.co.himedia.config.RabbitConfig.ROUTING_KEY, message);

        return Map.of(
                "message", "답변이 접수되었습니다. 분석 완료 후 결과가 업데이트됩니다.",
                "sessionId", sessionId,
                "status", "REPLY_ACCEPTED");
    }
}
