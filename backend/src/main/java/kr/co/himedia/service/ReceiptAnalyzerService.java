package kr.co.himedia.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import kr.co.himedia.dto.maintenance.MaintenanceLineItemDto;
import kr.co.himedia.dto.maintenance.OcrAnalysisResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.multipart.MultipartFile;

@Slf4j
@Service
@RequiredArgsConstructor
public class ReceiptAnalyzerService {

    @Value("${ocr.naver.invoke-url}")
    private String naverInvokeUrl;

    @Value("${ocr.naver.secret-key}")
    private String naverSecretKey;

    @Value("${ocr.openai.api-key}")
    private String openAiApiKey;

    private final RestTemplate restTemplate = new RestTemplate();
    private final ObjectMapper objectMapper;
    private final MasterDataService masterDataService;

    /**
     * 영수증 분석 통합 메서드
     */
    public OcrAnalysisResponse analyze(MultipartFile file) {
        log.info("Starting receipt analysis for file: {}", file.getOriginalFilename());
        log.info("Config Check - URL: {}, Key: {}", naverInvokeUrl,
                (naverSecretKey != null && !naverSecretKey.isEmpty() ? "PRESENT" : "MISSING"));

        // 1. Naver OCR 호출 (텍스트 추출)
        String rawText = extractText(file);
        log.info("[OCR output] length={} chars, text={}", rawText.length(),
                rawText.length() > 500 ? rawText.substring(0, 500) + "..." : rawText);
        if (rawText.isEmpty()) {
            return OcrAnalysisResponse.builder()
                    .ocrText("텍스트 추출 실패")
                    .build();
        }

        // 2. OpenAI 호출 (데이터 파싱)
        OcrAnalysisResponse response = parseWithAi(rawText);
        response.setOcrText(rawText);

        // 3. 소모품 이름 매핑 및 카테고리 분류 (DB 기반)
        if (response.getReceiptType() == null) {
            response.setReceiptType("MAINTENANCE"); // 기본값
        }

        if (response.getConsumableItemCode() != null && !"UNKNOWN".equals(response.getConsumableItemCode())) {
            kr.co.himedia.dto.master.ConsumableItemDto item = masterDataService
                    .getConsumableByCode(response.getConsumableItemCode());
            if (item != null) {
                response.setConsumableItemName(item.getName());
                response.setReceiptType("MAINTENANCE");
            }
        }

        // 주유 정보가 있으면 FUELING으로 분류
        if (response.getFuelType() != null || response.getFuelAmount() != null) {
            response.setReceiptType("FUELING");
        }

        // 4. ocrData에 원본 텍스트 포함 (JSON 구조)
        try {
            java.util.Map<String, String> ocrDataMap = new java.util.HashMap<>();
            ocrDataMap.put("text", rawText); // 원본 텍스트 저장
            response.setOcrData(objectMapper.writeValueAsString(ocrDataMap));
        } catch (Exception e) {
            log.error("Failed to serialize ocrData", e);
            response.setOcrData("{\"text\": \"" + rawText.replace("\"", "\\\"").replace("\n", "\\n") + "\"}");
        }

        return response;
    }

    private String extractText(MultipartFile file) {
        if (naverInvokeUrl == null || naverInvokeUrl.isEmpty() || naverSecretKey == null || naverSecretKey.isEmpty()) {
            log.error("Naver OCR configuration is missing");
            return "";
        }

        try {
            // Naver OCR API는 application/json으로 Base64 이미지를 전송해야 함
            org.springframework.http.HttpHeaders headers = new org.springframework.http.HttpHeaders();
            headers.setContentType(org.springframework.http.MediaType.APPLICATION_JSON);
            headers.set("X-OCR-SECRET", naverSecretKey.trim());
            log.info("OCR Request - Header: X-OCR-SECRET, KeyPrefix: {}",
                    naverSecretKey.substring(0, Math.min(naverSecretKey.length(), 5)));

            // 이미지를 Base64로 인코딩
            String base64Image = java.util.Base64.getEncoder().encodeToString(file.getBytes());

            // 파일 포맷 추출
            String filename = file.getOriginalFilename();
            String format = "jpg";
            if (filename != null && filename.contains(".")) {
                format = filename.substring(filename.lastIndexOf(".") + 1).toLowerCase();
            }

            // Request Body JSON 구성
            java.util.Map<String, Object> requestBody = new java.util.HashMap<>();
            requestBody.put("version", "V2");
            requestBody.put("requestId", java.util.UUID.randomUUID().toString());
            requestBody.put("timestamp", System.currentTimeMillis());

            java.util.Map<String, Object> imageMap = new java.util.HashMap<>();
            imageMap.put("format", format);
            imageMap.put("name", "receipt");
            imageMap.put("data", base64Image); // Base64 이미지 데이터
            requestBody.put("images", java.util.Collections.singletonList(imageMap));

            String requestJson = objectMapper.writeValueAsString(requestBody);
            log.info("OCR Request Body size: {} bytes", requestJson.length());

            org.springframework.http.HttpEntity<String> requestEntity = new org.springframework.http.HttpEntity<>(
                    requestJson, headers);

            org.springframework.http.ResponseEntity<String> response = restTemplate.exchange(
                    naverInvokeUrl, org.springframework.http.HttpMethod.POST, requestEntity, String.class);
            log.info("Naver OCR Response Status: {}", response.getStatusCode());
            log.info("Naver OCR Response Body: {}", response.getBody());

            if (response.getStatusCode() == org.springframework.http.HttpStatus.OK) {
                com.fasterxml.jackson.databind.JsonNode root = objectMapper.readTree(response.getBody());
                StringBuilder sb = new StringBuilder();
                com.fasterxml.jackson.databind.JsonNode images = root.path("images");
                if (images.isArray()) {
                    for (com.fasterxml.jackson.databind.JsonNode image : images) {
                        com.fasterxml.jackson.databind.JsonNode fields = image.path("fields");
                        if (fields.isArray()) {
                            for (com.fasterxml.jackson.databind.JsonNode field : fields) {
                                sb.append(field.path("inferText").asText()).append(" ");
                            }
                        }
                    }
                }
                String result = sb.toString().trim();
                return result;
            } else {
                log.error("Naver OCR API returned error status: {}", response.getStatusCode());
                return "";
            }

        } catch (Exception e) {
            log.error("Failed to call Naver OCR API", e);
        }
        return "";
    }

    private OcrAnalysisResponse parseWithAi(String rawText) {
        if (openAiApiKey == null || openAiApiKey.isEmpty()) {
            log.error("OpenAI API key is missing");
            return OcrAnalysisResponse.builder().consumableItemCode("UNKNOWN").build();
        }

        try {
            String apiUrl = "https://api.openai.com/v1/chat/completions";

            org.springframework.http.HttpHeaders headers = new org.springframework.http.HttpHeaders();
            headers.setContentType(org.springframework.http.MediaType.APPLICATION_JSON);
            headers.setBearerAuth(openAiApiKey);

            // DB에서 소모품 목록 가져오기 (Prompt 동적화)
            String itemsList = masterDataService.getAllConsumables().stream()
                    .map(item -> item.getCode())
                    .collect(java.util.stream.Collectors.joining(", "));

            String prompt = "You are a professional receipt parser. Analyze the provided Korean receipt text and return ONLY a single JSON object.\n\n"
                    + "First, determine if this is a 'MAINTENANCE' receipt or a 'FUELING' receipt.\n"
                    + "- receiptType: string ('MAINTENANCE' or 'FUELING')\n\n"
                    + "Common Fields (always include):\n"
                    + "- shopName: string (Business name; look for 상호, 가맹점, 정비소 등)\n"
                    + "- maintenanceDate: string (ISO YYYY-MM-DD; look for 거래일시, 정비일, 결제일 등)\n"
                    + "- cost: number (Total amount only, integer; look for 총합계, 거래금액, 최종 결제 금액, 총 합 계 등)\n"
                    + "- mileageAtMaintenance: number (Odometer if present, otherwise null)\n\n"
                    + "For MAINTENANCE receipts:\n"
                    + "- items: array of objects. Each object: { consumableItemCode, quantity, amount, description }.\n"
                    + "  - consumableItemCode: string. Use one of: " + itemsList + ", or OTHER for unmapped items (수리비, 부품가, 판금도색, 몰딩, 범퍼, 휀더 등).\n"
                    + "  - quantity: number (1 if not stated).\n"
                    + "  - amount: number (line total in KRW, or null if not available).\n"
                    + "  - description: string (original line text, optional).\n"
                    + "  Receipt formats to handle:\n"
                    + "  (1) Table with columns 상품명/단가/수량/금액: one item per data row. Skip discount-only rows (e.g. 포인트사용 with amount 0) or set amount 0.\n"
                    + "  (2) Sectioned (수리비, 부품가): one item per line under each section (e.g. 뒤 범퍼 판금도색, 몰딩교환 → map to OTHER).\n"
                    + "  If there is only one main item, still return items as an array with one element. If no line items are found, return items: [] and set consumableItemCode/quantity from the receipt as fallback.\n"
                    + "- consumableItemCode: string (single primary item code when items is empty or for backward compatibility; same allowed values as above)\n"
                    + "- quantity: number (for single-item fallback)\n\n"
                    + "For FUELING receipts (Gas station, EV charging):\n"
                    + "- fuelType: string ('GASOLINE', 'DIESEL', 'EV', 'LPG', 'premium_gasoline')\n"
                    + "- unitPrice: number (Price per unit)\n"
                    + "- fuelAmount: number (Amount of fuel/charge in liters, e.g., 30.30)\n\n"
                    + "If a value is missing, use null. Do not guess. Ignore non-receipt text (URLs, other UI).\n\n"
                    + "Text: \n" + rawText;

            log.info("[LLM input] promptLength={} chars, promptPreview={}", prompt.length(),
                    prompt.length() > 600 ? prompt.substring(0, 600) + "..." : prompt);

            java.util.Map<String, Object> requestBody = new java.util.HashMap<>();
            requestBody.put("model", "gpt-4o-mini");
            requestBody.put("messages", java.util.Collections.singletonList(
                    java.util.Map.of("role", "user", "content", prompt)));
            requestBody.put("temperature", 0);

            org.springframework.http.HttpEntity<String> requestEntity = new org.springframework.http.HttpEntity<>(
                    objectMapper.writeValueAsString(requestBody), headers);

            org.springframework.http.ResponseEntity<String> response = restTemplate.postForEntity(apiUrl, requestEntity,
                    String.class);

            if (response.getStatusCode() == org.springframework.http.HttpStatus.OK) {
                com.fasterxml.jackson.databind.JsonNode root = objectMapper.readTree(response.getBody());
                String content = root.path("choices").path(0).path("message").path("content").asText();
                log.info("[LLM output] contentLength={} chars, content={}", content.length(),
                        content.length() > 500 ? content.substring(0, 500) + "..." : content);

                // Markdown block 제거
                if (content.contains("```json")) {
                    content = content.substring(content.indexOf("```json") + 7);
                    content = content.substring(0, content.lastIndexOf("```"));
                } else if (content.contains("```")) {
                    content = content.substring(content.indexOf("```") + 3);
                    content = content.substring(0, content.lastIndexOf("```"));
                }

                com.fasterxml.jackson.databind.JsonNode parsedJson = objectMapper.readTree(content.trim());

                String singleCode = parsedJson.path("consumableItemCode").asText("UNKNOWN");
                Integer singleQty = parsedJson.has("quantity") && !parsedJson.path("quantity").isNull()
                        ? parsedJson.path("quantity").asInt(1)
                        : null;

                java.util.List<MaintenanceLineItemDto> parsedItems = null;
                com.fasterxml.jackson.databind.JsonNode itemsNode = parsedJson.path("items");
                if (itemsNode.isArray() && itemsNode.size() > 0) {
                    parsedItems = new java.util.ArrayList<>();
                    for (com.fasterxml.jackson.databind.JsonNode node : itemsNode) {
                        String code = node.path("consumableItemCode").asText("OTHER");
                        if ("UNKNOWN".equals(code)) {
                            code = "OTHER";
                        }
                        int qty = node.has("quantity") && !node.path("quantity").isNull() ? node.path("quantity").asInt(1) : 1;
                        Integer amt = node.has("amount") && !node.path("amount").isNull() ? node.path("amount").asInt() : null;
                        String desc = node.has("description") && !node.path("description").isNull() ? node.path("description").asText(null) : null;
                        kr.co.himedia.dto.master.ConsumableItemDto master = masterDataService.getConsumableByCode(code);
                        String name = master != null ? master.getName() : "기타 정비";
                        parsedItems.add(MaintenanceLineItemDto.builder()
                                .consumableItemCode(code)
                                .consumableItemName(name)
                                .quantity(qty)
                                .amount(amt)
                                .description(desc)
                                .build());
                    }
                    singleCode = parsedItems.get(0).getConsumableItemCode();
                    singleQty = parsedItems.get(0).getQuantity();
                }

                return OcrAnalysisResponse.builder()
                        .shopName(parsedJson.path("shopName").asText(null))
                        .maintenanceDate(
                                parsedJson.has("maintenanceDate") && !parsedJson.path("maintenanceDate").isNull()
                                        ? java.time.LocalDate.parse(parsedJson.path("maintenanceDate").asText())
                                        : null)
                        .cost(parsedJson.path("cost").asInt(0))
                        .mileageAtMaintenance(parsedJson.has("mileageAtMaintenance")
                                && !parsedJson.path("mileageAtMaintenance").isNull()
                                        ? parsedJson.path("mileageAtMaintenance").asDouble()
                                        : null)
                        .consumableItemCode(singleCode)
                        .quantity(singleQty)
                        .consumableItemName(parsedItems != null && !parsedItems.isEmpty()
                                ? parsedItems.get(0).getConsumableItemName()
                                : (masterDataService.getConsumableByCode(singleCode) != null ? masterDataService.getConsumableByCode(singleCode).getName() : null))
                        .items(parsedItems)
                        .receiptType(parsedJson.path("receiptType").asText("MAINTENANCE"))
                        .fuelType(parsedJson.path("fuelType").asText(null))
                        .unitPrice(parsedJson.has("unitPrice") && !parsedJson.path("unitPrice").isNull()
                                ? parsedJson.path("unitPrice").asInt()
                                : null)
                        .fuelAmount(parsedJson.has("fuelAmount") && !parsedJson.path("fuelAmount").isNull()
                                ? parsedJson.path("fuelAmount").asDouble()
                                : null)
                        .ocrData(response.getBody())
                        .build();
            }
        } catch (Exception e) {
            log.error("OpenAI Parsing Error", e);
        }
        return OcrAnalysisResponse.builder().consumableItemCode("UNKNOWN").build();
    }
}
