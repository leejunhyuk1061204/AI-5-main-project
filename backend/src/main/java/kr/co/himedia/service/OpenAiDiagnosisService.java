package kr.co.himedia.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.io.ClassPathResource;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import javax.annotation.PostConstruct;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Scanner;

/**
 * 진단 종합 리포트 생성을 위해 OpenAI Chat Completions를 직접 호출하는 서비스.
 * .env의 OPENAI_API_KEY를 사용하며, 기본 모델은 gpt-4o. OPENAI_DIAGNOSIS_MODEL로 변경 가능(예: gpt-5).
 */
@Slf4j
@Service
public class OpenAiDiagnosisService {

    private static final String OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions";
    private static final String PROMPT_RESOURCE = "prompts/diagnosis-system.txt";
    private static final int MAX_TOKENS = 2000;
    /** gpt-5 uses reasoning tokens first; need extra room so actual output is not truncated. */
    private static final int MAX_TOKENS_GPT5 = 20_000;
    private static final int TIMEOUT_MS = 180_000;

    @Value("${app.openai.api-key:}")
    private String apiKey;

    @Value("${app.openai.diagnosis.model:gpt-4o}")
    private String model;

    private final ObjectMapper objectMapper = new ObjectMapper();
    private final RestTemplate restTemplate;

    private String systemPrompt;

    public OpenAiDiagnosisService() {
        org.springframework.http.client.SimpleClientHttpRequestFactory factory =
                new org.springframework.http.client.SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(10_000);
        factory.setReadTimeout(TIMEOUT_MS);
        this.restTemplate = new RestTemplate(factory);
    }

    @PostConstruct
    public void loadPrompt() {
        try {
            ClassPathResource resource = new ClassPathResource(PROMPT_RESOURCE);
            try (InputStream is = resource.getInputStream();
                 Scanner s = new Scanner(is, StandardCharsets.UTF_8.name()).useDelimiter("\\A")) {
                systemPrompt = s.hasNext() ? s.next() : "";
            }
            if (systemPrompt == null || systemPrompt.isBlank()) {
                log.warn("[OpenAiDiagnosis] Prompt file empty: {}", PROMPT_RESOURCE);
                systemPrompt = "You are a vehicle diagnosis assistant. Respond only with valid JSON.";
            }
        } catch (Exception e) {
            log.error("[OpenAiDiagnosis] Failed to load prompt from {}", PROMPT_RESOURCE, e);
            systemPrompt = "You are a vehicle diagnosis assistant. Respond only with valid JSON.";
        }
    }

    /**
     * OpenAI에 진단 페이로드를 보내고, 명세에 맞는 JSON 응답을 파싱해 반환한다.
     * vehicle_info, dtc_info, consumables_status, analysis_results, rag_context 등 (diagnosis_context 없음).
     * API 키가 없거나 호출 실패 시 fallback 응답을 반환한다.
     */
    @SuppressWarnings("unchecked")
    public Map<String, Object> generateDiagnosisReport(Map<String, Object> payload) {
        String key = apiKey != null ? apiKey.trim() : "";
        if (key.isEmpty()) {
            log.warn("[OpenAiDiagnosis] OPENAI_API_KEY not set, returning fallback");
            return fallbackResponse("REPORT", "OpenAI API 키가 설정되지 않아 진단을 생성하지 못했습니다.");
        }

        try {
            String userContent = objectMapper.writeValueAsString(payload);
            log.info("[OpenAiDiagnosis] Request payload (full): {}", userContent);

            Map<String, Object> messages = Map.of(
                    "role", "system",
                    "content", systemPrompt
            );
            Map<String, Object> userMessage = Map.of(
                    "role", "user",
                    "content", userContent
            );

            Map<String, Object> requestBody = new HashMap<>(Map.of(
                    "model", model,
                    "messages", java.util.List.of(messages, userMessage),
                    "response_format", Map.of("type", "json_object")
            ));
            int maxCompletion = isModelGpt5(model) ? MAX_TOKENS_GPT5 : MAX_TOKENS;
            requestBody.put("max_completion_tokens", maxCompletion);
            if (!isModelTemperatureFixed(model)) {
                requestBody.put("temperature", 0.3);
            }

            String requestJson = objectMapper.writeValueAsString(requestBody);
            log.info("[OpenAiDiagnosis] Request JSON (to OpenAI): {}", requestJson);

            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);
            headers.setBearerAuth(key);

            HttpEntity<String> requestEntity = new HttpEntity<>(requestJson, headers);
            ResponseEntity<String> response = restTemplate.postForEntity(OPENAI_CHAT_URL, requestEntity, String.class);

            if (response.getStatusCode().is2xxSuccessful() && response.getBody() != null) {
                String rawResponseBody = response.getBody();
                log.info("[OpenAiDiagnosis] Response raw (full): {}", rawResponseBody);

                JsonNode root = objectMapper.readTree(rawResponseBody);
                JsonNode usage = root.path("usage");
                if (!usage.isMissingNode()) {
                    int promptTokens = usage.path("prompt_tokens").asInt(0);
                    int completionTokens = usage.path("completion_tokens").asInt(0);
                    int total = usage.path("total_tokens").asInt(0);
                    int reasoning = usage.path("completion_tokens_details").path("reasoning_tokens").asInt(0);
                    log.info("[OpenAiDiagnosis] Token usage: prompt={}, completion={}, total={}, reasoning={}",
                            promptTokens, completionTokens, total, reasoning);
                }
                String content = root.path("choices").path(0).path("message").path("content").asText("");
                if (content.isBlank()) {
                    return fallbackResponse("REPORT", "AI 응답이 비어 있습니다.");
                }
                String trimmed = content.trim();
                if (trimmed.startsWith("```json")) {
                    trimmed = trimmed.replaceFirst("^```json\\s*", "").replaceFirst("\\s*```$", "").trim();
                } else if (trimmed.startsWith("```")) {
                    trimmed = trimmed.replaceFirst("^```\\w*\\s*", "").replaceFirst("\\s*```$", "").trim();
                }
                Map<String, Object> parsed = objectMapper.readValue(trimmed, Map.class);
                log.info("[OpenAiDiagnosis] Response parsed (full): {}", objectMapper.writeValueAsString(parsed));
                return parsed;
            }
        } catch (Exception e) {
            log.error("[OpenAiDiagnosis] OpenAI call failed", e);
        }
        return fallbackResponse("REPORT", "진단 생성 중 일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.");
    }

    /**
     * Reply(대화 이어하기)용 OpenAI 호출. 동일 모델(.env의 app.openai.diagnosis.model) 사용.
     * 메시지 구성: system, user(초기 컨텍스트 JSON), 이어서 대화 턴(assistant/user) 순서.
     */
    @SuppressWarnings("unchecked")
    public Map<String, Object> generateReplyResponse(Map<String, Object> initialContext,
            List<Map<String, Object>> conversation) {
        String key = apiKey != null ? apiKey.trim() : "";
        if (key.isEmpty()) {
            log.warn("[OpenAiDiagnosis] OPENAI_API_KEY not set, returning fallback");
            return fallbackResponse("REPORT", "OpenAI API 키가 설정되지 않아 답변을 생성하지 못했습니다.");
        }

        try {
            List<Map<String, Object>> messages = new ArrayList<>();
            messages.add(Map.of("role", "system", "content", systemPrompt));
            String initialJson = objectMapper.writeValueAsString(initialContext);
            messages.add(Map.of("role", "user", "content", initialJson));

            for (Map<String, Object> turn : conversation) {
                String role = (String) turn.get("role");
                if (role == null) continue;
                String openAiRole = "ai".equalsIgnoreCase(role) ? "assistant" : "user";
                Object contentObj = turn.get("content");
                String content = contentObj != null ? contentObj.toString() : "";
                if ("user".equals(openAiRole) && turn.containsKey("media_refs")) {
                    content = content + "\n[첨부: 이미지/소리 분석 결과가 포함되었습니다.]";
                }
                messages.add(Map.of("role", openAiRole, "content", content));
            }

            Map<String, Object> requestBody = new HashMap<>(Map.of(
                    "model", model,
                    "messages", messages,
                    "response_format", Map.of("type", "json_object")
            ));
            int maxCompletion = isModelGpt5(model) ? MAX_TOKENS_GPT5 : MAX_TOKENS;
            requestBody.put("max_completion_tokens", maxCompletion);
            if (!isModelTemperatureFixed(model)) {
                requestBody.put("temperature", 0.3);
            }

            String requestJson = objectMapper.writeValueAsString(requestBody);
            log.info("[OpenAiDiagnosis] Reply Request JSON (to OpenAI): {}", requestJson);

            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);
            headers.setBearerAuth(key);

            HttpEntity<String> requestEntity = new HttpEntity<>(requestJson, headers);
            ResponseEntity<String> response = restTemplate.postForEntity(OPENAI_CHAT_URL, requestEntity, String.class);

            if (response.getStatusCode().is2xxSuccessful() && response.getBody() != null) {
                String rawResponseBody = response.getBody();
                log.info("[OpenAiDiagnosis] Reply Response raw (full): {}", rawResponseBody);

                JsonNode root = objectMapper.readTree(rawResponseBody);
                JsonNode usage = root.path("usage");
                if (!usage.isMissingNode()) {
                    int promptTokens = usage.path("prompt_tokens").asInt(0);
                    int completionTokens = usage.path("completion_tokens").asInt(0);
                    int total = usage.path("total_tokens").asInt(0);
                    int reasoning = usage.path("completion_tokens_details").path("reasoning_tokens").asInt(0);
                    log.info("[OpenAiDiagnosis] Reply Token usage: prompt={}, completion={}, total={}, reasoning={}",
                            promptTokens, completionTokens, total, reasoning);
                }
                String content = root.path("choices").path(0).path("message").path("content").asText("");
                if (content.isBlank()) {
                    return fallbackResponse("REPORT", "AI 응답이 비어 있습니다.");
                }
                String trimmed = content.trim();
                if (trimmed.startsWith("```json")) {
                    trimmed = trimmed.replaceFirst("^```json\\s*", "").replaceFirst("\\s*```$", "").trim();
                } else if (trimmed.startsWith("```")) {
                    trimmed = trimmed.replaceFirst("^```\\w*\\s*", "").replaceFirst("\\s*```$", "").trim();
                }
                Map<String, Object> parsed = objectMapper.readValue(trimmed, Map.class);
                log.info("[OpenAiDiagnosis] Reply Response parsed (full): {}", objectMapper.writeValueAsString(parsed));
                return parsed;
            }
        } catch (Exception e) {
            log.error("[OpenAiDiagnosis] Reply OpenAI call failed", e);
        }
        return fallbackResponse("REPORT", "답변 생성 중 일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.");
    }

    /** gpt-5 등 temperature를 지정할 수 없는 모델은 true. */
    private boolean isModelTemperatureFixed(String modelName) {
        if (modelName == null) return false;
        String m = modelName.toLowerCase();
        return m.startsWith("gpt-5") || m.contains("gpt-5");
    }

    private boolean isModelGpt5(String modelName) {
        if (modelName == null) return false;
        String m = modelName.toLowerCase();
        return m.startsWith("gpt-5") || m.contains("gpt-5");
    }

    private Map<String, Object> fallbackResponse(String responseMode, String summary) {
        Map<String, Object> map = new HashMap<>();
        map.put("response_mode", responseMode != null ? responseMode : "REPORT");
        map.put("confidence_level", "LOW");
        map.put("confidence_score", 0.0);
        map.put("summary", summary != null ? summary : "진단 생성 중 일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.");
        map.put("report_data", Map.of(
                "suspected_causes", java.util.List.of(),
                "final_guide", "가까운 정비소 방문을 권장합니다."
        ));
        map.put("interactive_data", null);
        map.put("disclaimer", "본 진단은 참고용이며, 정확한 상태는 전문가의 점검이 필요합니다.");
        return map;
    }
}
