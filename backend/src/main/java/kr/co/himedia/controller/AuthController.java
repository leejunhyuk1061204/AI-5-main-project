package kr.co.himedia.controller;

import jakarta.validation.Valid;
import kr.co.himedia.dto.auth.SignupRequest;
import kr.co.himedia.dto.auth.UserResponse;
import kr.co.himedia.dto.auth.LoginRequest;
import kr.co.himedia.dto.auth.TokenResponse;
import kr.co.himedia.common.ApiResponse;
import kr.co.himedia.service.UserService;
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
