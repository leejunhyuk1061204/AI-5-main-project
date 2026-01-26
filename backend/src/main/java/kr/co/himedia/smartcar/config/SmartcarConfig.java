package kr.co.himedia.smartcar.config;

import com.smartcar.sdk.AuthClient;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class SmartcarConfig {

    @Value("${smartcar.client-id}")
    private String clientId;

    @Value("${smartcar.client-secret}")
    private String clientSecret;

    @Value("${smartcar.redirect-uri}")
    private String redirectUri;

    @Value("${smartcar.mode}")
    private String mode;

    @Bean
    public AuthClient authClient() {
        boolean testMode = "test".equalsIgnoreCase(mode);
        try {
            return new AuthClient.Builder()
                    .clientId(clientId)
                    .clientSecret(clientSecret)
                    .redirectUri(redirectUri)
                    .testMode(testMode)
                    .build();
        } catch (Exception e) {
            throw new RuntimeException("Failed to create Smartcar AuthClient", e);
        }
    }
}
