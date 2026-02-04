package kr.co.himedia.dto.auth;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.UUID;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class UserResponse {
    private UUID id;
    private String email;
    private String nickname;
    private String membership;
    private java.time.LocalDateTime membershipExpiry;
    private String profileImageBase64;
}
