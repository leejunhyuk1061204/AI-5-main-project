package kr.co.himedia.service;

import kr.co.himedia.common.util.EncryptionUtils;
import kr.co.himedia.entity.CloudProvider;
import kr.co.himedia.entity.User;
import kr.co.himedia.repository.CloudAccountRepository;
import kr.co.himedia.repository.UserRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.web.client.RestTemplate;

import java.util.Optional;
import java.util.UUID;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class CloudAuthServiceTest {

    @Mock
    private CloudAccountRepository cloudAccountRepository;
    @Mock
    private UserRepository userRepository;
    @Mock
    private EncryptionUtils encryptionUtils;
    @Mock
    private RestTemplate restTemplate;

    @InjectMocks
    private CloudAuthService cloudAuthService;

    @BeforeEach
    void setUp() {
        ReflectionTestUtils.setField(cloudAuthService, "smartcarClientId", "test-client-id");
        ReflectionTestUtils.setField(cloudAuthService, "smartcarClientSecret", "test-client-secret");
        ReflectionTestUtils.setField(cloudAuthService, "smartcarTokenUri", "https://auth.smartcar.com/oauth/token");
        ReflectionTestUtils.setField(cloudAuthService, "hmClientId", "test-hm-id");
        ReflectionTestUtils.setField(cloudAuthService, "hmClientSecret", "test-hm-secret");
        ReflectionTestUtils.setField(cloudAuthService, "hmRedirectUri", "http://localhost/callback-hm");
        ReflectionTestUtils.setField(cloudAuthService, "hmTokenUri",
                "https://sandbox.api.high-mobility.com/v1/access_tokens");
    }

    @Test
    @DisplayName("인가 코드를 받으면 스마트카 API를 호출하고 암호화된 토큰을 저장한다.")
    void exchangeCodeAndSave_shouldEncryptAndSaveTokens() {
        // given
        UUID userId = UUID.randomUUID();
        User user = User.builder().userId(userId).build();
        String code = "valid-auth-code";

        kr.co.himedia.dto.cloud.TokenExchangeResponse mockResponse = new kr.co.himedia.dto.cloud.TokenExchangeResponse();
        mockResponse.setAccess_token("plain-access-token");
        mockResponse.setRefresh_token("plain-refresh-token");
        mockResponse.setExpires_in(3600);

        given(userRepository.findById(userId)).willReturn(Optional.of(user));
        given(restTemplate.postForObject(anyString(), any(), any())).willReturn(mockResponse);
        given(encryptionUtils.encrypt(anyString())).willAnswer(invocation -> "encrypted-" + invocation.getArgument(0));
        given(cloudAccountRepository.findByUserAndProvider(any(), any())).willReturn(Optional.empty());

        // when
        cloudAuthService.exchangeCodeAndSave(userId, code, CloudProvider.SMARTCAR);

        // then
        verify(encryptionUtils, times(2)).encrypt(anyString()); // access & refresh
        verify(cloudAccountRepository, times(1))
                .save(argThat(account -> account.getAccessToken().equals("encrypted-plain-access-token") &&
                        account.getRefreshToken().equals("encrypted-plain-refresh-token") &&
                        account.getProvider() == CloudProvider.SMARTCAR));
    }

    @Test
    @DisplayName("인가 코드를 받으면 하이모빌리티 API를 호출하고 암호화된 토큰을 저장한다.")
    void exchangeCodeAndSave_shouldHandleHighMobility() {
        // given
        UUID userId = UUID.randomUUID();
        User user = User.builder().userId(userId).build();
        String code = "hm-auth-code";

        kr.co.himedia.dto.cloud.TokenExchangeResponse mockResponse = new kr.co.himedia.dto.cloud.TokenExchangeResponse();
        mockResponse.setAccess_token("hm-plain-access");
        mockResponse.setRefresh_token("hm-plain-refresh");
        mockResponse.setExpires_in(7200);

        given(userRepository.findById(userId)).willReturn(Optional.of(user));
        given(restTemplate.postForObject(eq("https://sandbox.api.high-mobility.com/v1/access_tokens"), any(), any()))
                .willReturn(mockResponse);
        given(encryptionUtils.encrypt(anyString())).willAnswer(invocation -> "encrypted-" + invocation.getArgument(0));

        // when
        cloudAuthService.exchangeCodeAndSave(userId, code, CloudProvider.HIGH_MOBILITY);

        // then
        verify(cloudAccountRepository)
                .save(argThat(account -> account.getAccessToken().equals("encrypted-hm-plain-access")
                        && account.getProvider() == CloudProvider.HIGH_MOBILITY));
    }
}
