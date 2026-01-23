package kr.co.himedia.service;

import kr.co.himedia.common.util.EncryptionUtils;
import lombok.Getter;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.time.LocalDateTime;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

@Slf4j
@Service
@RequiredArgsConstructor
public class HighMobilityService {

    private final RestTemplate restTemplate = new RestTemplate();
    private final EncryptionUtils encryptionUtils;

    @Value("${HM_CLIENT_ID}")
    private String clientId;

    @Value("${HM_CLIENT_SECRET}")
    private String clientSecret;

    private static final String BASE_URL = "https://sandbox.api.high-mobility.com/v1";

    // 인메모리 토큰 캐시
    private final Map<String, TokenCache> tokenCache = new ConcurrentHashMap<>();

    @Getter
    @RequiredArgsConstructor
    private static class TokenCache {
        private final String accessToken;
        private final LocalDateTime expiresAt;

        public boolean isExpired() {
            return LocalDateTime.now().isAfter(expiresAt.minusMinutes(1)); // 1분 여유
        }
    }

    /**
     * 하이모빌리티 Access Token을 발급받거나 캐시된 토큰을 반환합니다.
     */
    public String getAccessToken() {
        TokenCache cached = tokenCache.get("HM_TOKEN");
        if (cached != null && !cached.isExpired()) {
            return cached.getAccessToken();
        }

        log.info("[HighMobility] Access Token 갱신 요청");

        Map<String, String> request = new HashMap<>();
        request.put("client_id", clientId);
        request.put("client_secret", clientSecret);
        request.put("grant_type", "client_credentials");
        request.put("scope", "fleet:clearance vehicle:data vehicle:static-data");

        ResponseEntity<Map> response = restTemplate.postForEntity(BASE_URL + "/access_tokens", request, Map.class);

        if (response.getStatusCode() == HttpStatus.OK && response.getBody() != null) {
            String token = (String) response.getBody().get("access_token");
            Integer expiresIn = (Integer) response.getBody().get("expires_in");

            tokenCache.put("HM_TOKEN", new TokenCache(token, LocalDateTime.now().plusSeconds(expiresIn)));
            log.info("[HighMobility] Access Token 갱신 성공 (만료: {}초)", expiresIn);
            log.info("[DEBUG] Access Token: {}", token); // Insomnia 테스트용 토큰 출력
            return token;
        }

        throw new RuntimeException("High Mobility 토큰 발급 실패");
    }

    /**
     * 차량을 Fleet Clearance에 등록합니다 (Pending 상태가 됨).
     */
    public Map<String, Object> registerVehicle(String vin) {
        log.info("[HighMobility] 차량 등록 요청 - VIN: {}", vin);

        String token = getAccessToken();

        HttpHeaders headers = new HttpHeaders();
        headers.setBearerAuth(token);
        headers.setContentType(MediaType.APPLICATION_JSON);

        Map<String, Object> vehicle = new HashMap<>();
        vehicle.put("vin", vin);
        vehicle.put("brand", "sandbox");

        Map<String, Object> body = new HashMap<>();
        body.put("vehicles", Collections.singletonList(vehicle));

        HttpEntity<Map<String, Object>> entity = new HttpEntity<>(body, headers);

        ResponseEntity<Map> response = restTemplate.exchange(BASE_URL + "/fleets/vehicles", HttpMethod.POST, entity,
                Map.class);
        return response.getBody();
    }

    /**
     * 차량의 Clearance 승인 상태를 조회합니다.
     */
    public Map<String, Object> getClearanceStatus(String vin) {
        log.info("[HighMobility] 승인 상태 조회 - VIN: {}", vin);

        String token = getAccessToken();

        HttpHeaders headers = new HttpHeaders();
        headers.setBearerAuth(token);

        HttpEntity<Void> entity = new HttpEntity<>(headers);

        ResponseEntity<Map> response = restTemplate.exchange(BASE_URL + "/fleets/vehicles/" + vin, HttpMethod.GET,
                entity, Map.class);
        return response.getBody();
    }

    /**
     * 차량의 동적 데이터 (Odometer 등)를 조회합니다 (AutoAPI-13).
     */
    public Map<String, Object> getVehicleData(String vin) {
        log.info("[HighMobility] 차량 동적 데이터(Odometer) 조회 - VIN: {}", vin);

        String token = getAccessToken();

        HttpHeaders headers = new HttpHeaders();
        headers.setBearerAuth(token);

        HttpEntity<Void> entity = new HttpEntity<>(headers);

        ResponseEntity<Map> response = restTemplate.exchange(BASE_URL + "/vehicle-data/autoapi-13/" + vin,
                HttpMethod.GET, entity, Map.class);
        return response.getBody();
    }

    /**
     * 차량의 정적 데이터 (제원)를 조회합니다.
     */
    public Map<String, Object> getStaticData(String vin) {
        log.info("[HighMobility] 차량 정적 데이터(제원) 조회 - VIN: {}", vin);

        String token = getAccessToken();

        HttpHeaders headers = new HttpHeaders();
        headers.setBearerAuth(token);

        HttpEntity<Void> entity = new HttpEntity<>(headers);

        ResponseEntity<Map> response = restTemplate.exchange(BASE_URL + "/vehicle-static-data/" + vin, HttpMethod.GET,
                entity, Map.class);
        return response.getBody();
    }

    /**
     * Fleet에서 차량을 삭제합니다 (권한 취소).
     */
    public Map<String, Object> deleteVehicle(String vin) {
        log.info("[HighMobility] Fleet 차량 삭제 요청 - VIN: {}", vin);

        String token = getAccessToken();

        HttpHeaders headers = new HttpHeaders();
        headers.setBearerAuth(token);

        HttpEntity<Void> entity = new HttpEntity<>(headers);

        ResponseEntity<Map> response = restTemplate.exchange(BASE_URL + "/fleets/vehicles/" + vin, HttpMethod.DELETE,
                entity, Map.class);
        return response.getBody();
    }
}
