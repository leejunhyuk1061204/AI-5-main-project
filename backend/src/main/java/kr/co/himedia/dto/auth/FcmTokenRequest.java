package kr.co.himedia.dto.auth;

import jakarta.validation.constraints.NotBlank;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@NoArgsConstructor
public class FcmTokenRequest {

    @NotBlank(message = "FCM token is required")
    private String fcmToken;
}
