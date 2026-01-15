package kr.co.himedia.service;

import kr.co.himedia.dto.ai.DiagnosisRequestDto;
import kr.co.himedia.dto.ai.DtcDto;
import kr.co.himedia.entity.DtcHistory;
import kr.co.himedia.repository.DtcHistoryRepository;
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
import java.util.Map;
import java.util.UUID;

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

    @Autowired
    public AiDiagnosisService(DtcHistoryRepository dtcHistoryRepository, RabbitTemplate rabbitTemplate) {
        this.dtcHistoryRepository = dtcHistoryRepository;
        this.rabbitTemplate = rabbitTemplate;

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
                .status(DtcHistory.DtcStatus.valueOf(dtcDto.getStatus())) // Enum 변환
                .build();
        dtcHistoryRepository.save(history);

        // RabbitMQ 이벤트 발행
        rabbitTemplate.convertAndSend("car-sentry.exchange", "ai.diagnosis.dtc", dtcDto);
        log.info("Published DTC event to RabbitMQ: {}", dtcDto.getDtcCode());
    }

    /**
     * AI 진단 요청 (동기/비동기 혼합 가능)
     * 현재는 동기적으로 AI 서버 호출 후 결과 반환 (데모용)
     */
    public Object requestDiagnosis(DiagnosisRequestDto requestDto) {
        if ("local".equalsIgnoreCase(storageType)) {
            // Local Mode: Multipart File 전송 -> AI 서버의 /test/predict/... 경로 호출
            String targetUrl = "VISION".equalsIgnoreCase(requestDto.getType())
                    ? "http://localhost:8000/api/v1/test/predict/visual"
                    : "http://localhost:8000/api/v1/test/predict/audio";
            return sendLocalFileRequest(targetUrl, requestDto.getMediaUrl());
        } else {
            // S3 Mode: JSON URL 전송 (Prod Router)
            String targetUrl = "VISION".equalsIgnoreCase(requestDto.getType()) ? aiServerVisualUrl : aiServerAudioUrl;
            return sendS3UrlRequest(targetUrl, requestDto.getMediaUrl(), requestDto.getType());
        }
    }

    private Object sendLocalFileRequest(String url, String localFileUrl) {
        try {
            // localFileUrl 예: http://localhost:8080/uploads/uuid_file.jpg
            // 실제 파일 경로로 변환 필요 (uploads/uuid_file.jpg)
            // 간단히 파일명만 추출하여 uploads 폴더에서 찾음
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

            log.info("Sending Multipart Request to AI Server (Local): {}", url);
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

            log.info("Sending JSON Request to AI Server (S3): {}", url);
            return restTemplate.postForObject(url, body, Map.class);
        } catch (Exception e) {
            log.error("Failed to send S3 URL request", e);
            throw new RuntimeException("AI Server Request Failed (S3)", e);
        }
    }
}
