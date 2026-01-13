package kr.co.himedia.auth.controller;

import jakarta.validation.Valid;
import kr.co.himedia.auth.dto.SignupRequest;
import kr.co.himedia.auth.dto.UserResponse;
import kr.co.himedia.auth.dto.LoginRequest;
import kr.co.himedia.auth.dto.TokenResponse;
import kr.co.himedia.global.common.ApiResponse;
import kr.co.himedia.auth.service.UserService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

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
}
