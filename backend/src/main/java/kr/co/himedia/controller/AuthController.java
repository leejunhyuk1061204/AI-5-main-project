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

    @PostMapping("/signup")
    public ResponseEntity<ApiResponse<UserResponse>> signup(@Valid @RequestBody SignupRequest req) {
        UserResponse resp = userService.createUser(req);
        return ResponseEntity.status(HttpStatus.CREATED).body(ApiResponse.success(resp));
    }

    @PostMapping("/login")
    public ResponseEntity<ApiResponse<TokenResponse>> login(@Valid @RequestBody LoginRequest req) {
        TokenResponse token = userService.authenticate(req);
        return ResponseEntity.ok(ApiResponse.success(token));
    }

    @GetMapping("/me")
    public ResponseEntity<ApiResponse<UserResponse>> getProfile(Authentication auth) {
        UserResponse resp = userService.getProfile(UUID.fromString(auth.getName()));
        return ResponseEntity.ok(ApiResponse.success(resp));
    }

    @PatchMapping("/me")
    public ResponseEntity<ApiResponse<String>> updateProfile(Authentication auth,
            @Valid @RequestBody UserUpdateRequest req) {
        userService.updateProfile(UUID.fromString(auth.getName()), req);
        return ResponseEntity.ok(ApiResponse.success("Profile updated"));
    }

    @DeleteMapping("/me")
    public ResponseEntity<ApiResponse<String>> deleteUser(Authentication auth) {
        userService.deleteUser(UUID.fromString(auth.getName()));
        return ResponseEntity.ok(ApiResponse.success("User deleted (Soft delete)"));
    }

    @PostMapping("/me/image")
    public ResponseEntity<ApiResponse<String>> uploadProfileImage(Authentication auth,
            @RequestParam("file") MultipartFile file) {
        userService.updateProfileImage(UUID.fromString(auth.getName()), file);
        return ResponseEntity.ok(ApiResponse.success("Profile image updated"));
    }
}
