package kr.co.himedia.dto.auth;

import jakarta.validation.constraints.Size;
import lombok.*;

@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class UserUpdateRequest {
    @Size(max = 50, message = "닉네임은 50자 이내여야 합니다.")
    private String nickname;
    private String fcmToken;
    private String password;
}
