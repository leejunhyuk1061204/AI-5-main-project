package kr.co.himedia.dto.auth;

import jakarta.validation.constraints.NotBlank;
import lombok.AccessLevel;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;

@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
@Builder
public class SocialLoginRequest {

    @NotBlank(message = "Provider is required")
    private String provider; // google, kakao, etc.

    @NotBlank(message = "Token is required")
    private String token; // ID Token or Access Token
}
