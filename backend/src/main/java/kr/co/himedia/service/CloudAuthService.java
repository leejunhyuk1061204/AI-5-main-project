package kr.co.himedia.service;

import kr.co.himedia.common.util.EncryptionUtils;
import kr.co.himedia.dto.cloud.TokenExchangeResponse;
import kr.co.himedia.entity.CloudAccount;
import kr.co.himedia.entity.CloudProvider;
import kr.co.himedia.entity.User;
import kr.co.himedia.repository.CloudAccountRepository;
import kr.co.himedia.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestTemplate;

import java.time.LocalDateTime;
import java.util.UUID;

@Slf4j
@Service
@RequiredArgsConstructor
public class CloudAuthService {

    private final CloudAccountRepository cloudAccountRepository;
    private final UserRepository userRepository;
    private final EncryptionUtils encryptionUtils;
    private final RestTemplate restTemplate;

    @Value("${smartcar.client-id}")
    private String smartcarClientId;

    @Value("${smartcar.client-secret}")
    private String smartcarClientSecret;

    @Value("${smartcar.redirect-uri}")
    private String smartcarRedirectUri;

    @Value("${smartcar.token-uri}")
    private String smartcarTokenUri;

    @Value("${high-mobility.client-id}")
    private String hmClientId;

    @Value("${high-mobility.client-secret}")
    private String hmClientSecret;

    @Value("${high-mobility.redirect-uri}")
    private String hmRedirectUri;

    @Value("${high-mobility.token-uri}")
    private String hmTokenUri;

    public void exchangeCodeAndSave(UUID userId, String code, CloudProvider provider) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new RuntimeException("User not found"));

        TokenExchangeResponse response;
        if (provider == CloudProvider.SMARTCAR) {
            response = exchangeSmartcarCode(code);
        } else if (provider == CloudProvider.HIGH_MOBILITY) {
            response = exchangeHighMobilityCode(code);
        } else {
            throw new UnsupportedOperationException("Unknown provider: " + provider);
        }

        CloudAccount account = cloudAccountRepository.findByUserAndProvider(user, provider)
                .orElse(CloudAccount.builder().user(user).provider(provider).build());

        account.setAccessToken(encryptionUtils.encrypt(response.getAccess_token()));
        if (response.getRefresh_token() != null) {
            account.setRefreshToken(encryptionUtils.encrypt(response.getRefresh_token()));
        }
        account.setExpiresAt(LocalDateTime.now().plusSeconds(response.getExpires_in()));

        cloudAccountRepository.save(account);
        log.info("Successfully saved cloud account for user: {}, provider: {}", userId, provider);
    }

    private TokenExchangeResponse exchangeSmartcarCode(String code) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_FORM_URLENCODED);
        headers.setBasicAuth(smartcarClientId, smartcarClientSecret);

        MultiValueMap<String, String> body = new LinkedMultiValueMap<>();
        body.add("grant_type", "authorization_code");
        body.add("code", code);
        body.add("redirect_uri", smartcarRedirectUri);

        HttpEntity<MultiValueMap<String, String>> request = new HttpEntity<>(body, headers);

        return restTemplate.postForObject(smartcarTokenUri, request, TokenExchangeResponse.class);
    }

    private TokenExchangeResponse exchangeHighMobilityCode(String code) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_FORM_URLENCODED);

        MultiValueMap<String, String> body = new LinkedMultiValueMap<>();
        body.add("grant_type", "authorization_code");
        body.add("code", code);
        body.add("client_id", hmClientId);
        body.add("client_secret", hmClientSecret);
        body.add("redirect_uri", hmRedirectUri);

        HttpEntity<MultiValueMap<String, String>> request = new HttpEntity<>(body, headers);

        return restTemplate.postForObject(hmTokenUri, request, TokenExchangeResponse.class);
    }
}
