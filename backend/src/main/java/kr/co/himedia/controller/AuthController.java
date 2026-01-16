package kr.co.himedia.controller;

import jakarta.validation.Valid;
import kr.co.himedia.common.ApiResponse;
import kr.co.himedia.dto.auth.*;
import kr.co.himedia.service.UserService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.UUID;

@RestController
@RequestMapping("/auth")
@RequiredArgsConstructor
public class AuthController {

    private final UserService userService;

    // BE-AU-001 회원가입
    @PostMapping("/signup")
    public ResponseEntity<ApiResponse<UserResponse>> signup(@Valid @RequestBody SignupRequest req) {
        UserResponse resp = userService.createUser(req);
        return ResponseEntity.status(HttpStatus.CREATED).body(ApiResponse.success(resp));
    }

    // BE-AU-002 로그인
    @PostMapping("/login")
    public ResponseEntity<ApiResponse<TokenResponse>> login(@Valid @RequestBody LoginRequest req) {
        TokenResponse token = userService.authenticate(req);
        return ResponseEntity.ok(ApiResponse.success(token));
    }

    @PostMapping("/refresh")
    public ResponseEntity<ApiResponse<TokenResponse>> refresh(@Valid @RequestBody TokenRefreshRequest req) {
        TokenResponse token = userService.refresh(req);
        return ResponseEntity.ok(ApiResponse.success(token));
    }

    // BE-AU-003 내 정보 조회
    @GetMapping("/me")
    public ResponseEntity<ApiResponse<UserResponse>> getProfile(Authentication auth) {
        if (auth != null && auth.getPrincipal() instanceof kr.co.himedia.security.CustomUserDetails userDetails) {
            UserResponse resp = userService.getProfile(userDetails.getUserId());
            return ResponseEntity.ok(ApiResponse.success(resp));
        }
        return ResponseEntity.status(HttpStatus.UNAUTHORIZED).build();
    }

    // BE-AU-004 정보 수정
    @PatchMapping("/me")
    public ResponseEntity<ApiResponse<String>> updateProfile(Authentication auth,
            @Valid @RequestBody UserUpdateRequest req) {
        if (auth != null && auth.getPrincipal() instanceof kr.co.himedia.security.CustomUserDetails userDetails) {
            userService.updateProfile(userDetails.getUserId(), req);
            return ResponseEntity.ok(ApiResponse.success("Profile updated"));
        }
        return ResponseEntity.status(HttpStatus.UNAUTHORIZED).build();
    }

    // FCM 토큰 전용 갱신
    @PatchMapping("/fcm-token")
    public ResponseEntity<ApiResponse<String>> updateFcmToken(Authentication auth,
            @Valid @RequestBody FcmTokenRequest req) {
        if (auth != null && auth.getPrincipal() instanceof kr.co.himedia.security.CustomUserDetails userDetails) {
            userService.updateFcmToken(userDetails.getUserId(), req.getFcmToken());
            return ResponseEntity.ok(ApiResponse.success("FCM token updated"));
        }
        return ResponseEntity.status(HttpStatus.UNAUTHORIZED).build();
    }

    // BE-AU-007 회원 탈퇴
    @DeleteMapping("/me")
    public ResponseEntity<ApiResponse<String>> deleteUser(Authentication auth) {
        if (auth != null && auth.getPrincipal() instanceof kr.co.himedia.security.CustomUserDetails userDetails) {
            userService.deleteUser(userDetails.getUserId());
            return ResponseEntity.ok(ApiResponse.success("User deleted (Soft delete)"));
        }
        return ResponseEntity.status(HttpStatus.UNAUTHORIZED).build();
    }

    // BE-AU-004 프로필 이미지 수정
    @PostMapping("/me/image")
    public ResponseEntity<ApiResponse<String>> uploadProfileImage(Authentication auth,
            @RequestParam("file") MultipartFile file) {
        if (auth != null && auth.getPrincipal() instanceof kr.co.himedia.security.CustomUserDetails userDetails) {
            userService.updateProfileImage(userDetails.getUserId(), file);
            return ResponseEntity.ok(ApiResponse.success("Profile image updated"));
        }
        return ResponseEntity.status(HttpStatus.UNAUTHORIZED).build();
    }
}
