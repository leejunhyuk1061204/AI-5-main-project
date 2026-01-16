package kr.co.himedia.service.ai;

import kr.co.himedia.dto.maintenance.ai.AiWearFactorRequest;
import kr.co.himedia.dto.maintenance.ai.AiWearFactorResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

@Component
@RequiredArgsConstructor
public class AiClient {

    private final RestTemplate restTemplate;

    @Value("${ai.server.url:http://localhost:8000}")
    private String aiServerUrl;

    public AiWearFactorResponse getWearFactor(AiWearFactorRequest request) {
        // 테스트용 Mock 엔드포인트 사용 (실제 XGBoost 모델 연동 전)
        String url = aiServerUrl + "/api/v1/test/predict/wear-factor";
        return restTemplate.postForObject(url, request, AiWearFactorResponse.class);
    }
}
