package kr.co.himedia.service;

import kr.co.himedia.common.ApiResponse;
import kr.co.himedia.dto.auth.*;
import kr.co.himedia.entity.RefreshToken;
import kr.co.himedia.entity.User;
import kr.co.himedia.repository.RefreshTokenRepository;
import kr.co.himedia.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import kr.co.himedia.security.JwtTokenProvider;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.time.LocalDateTime;
import java.util.Base64;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class UserService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtTokenProvider jwtTokenProvider;
    private final RefreshTokenRepository refreshTokenRepository;

    public UserResponse createUser(SignupRequest req) {
        userRepository.findByEmail(req.getEmail()).ifPresent(u -> {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Email already exists");
        });

        User user = User.builder()
                .userId(UUID.randomUUID())
                .email(req.getEmail())
                .passwordHash(passwordEncoder.encode(req.getPassword()))
                .nickname(req.getNickname())
                .build();

        User saved = userRepository.save(user);

        return UserResponse.builder()
                .userId(saved.getUserId())
                .email(saved.getEmail())
                .nickname(saved.getNickname())
                .build();
    }

    public TokenResponse authenticate(LoginRequest req) {
        User user = userRepository.findByEmail(req.getEmail())
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Invalid credentials"));

        if (!passwordEncoder.matches(req.getPassword(), user.getPasswordHash())) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Invalid credentials");
        }

        String accessToken = jwtTokenProvider.createAccessToken(user.getUserId().toString());
        String refreshToken = jwtTokenProvider.createRefreshToken(user.getUserId().toString());

        // 기존 리프레시 토큰이 있다면 삭제 (또는 중복 로그인 허용 시 업데이트 로직)
        refreshTokenRepository.deleteByUser(user);

        refreshTokenRepository.save(RefreshToken.builder()
                .user(user)
                .token(refreshToken)
                .expiryDate(java.time.Instant.now().plusMillis(604800000)) // 7일
                .build());

        user.setLastLoginAt(LocalDateTime.now());
        userRepository.save(user);

        return TokenResponse.builder()
                .accessToken(accessToken)
                .refreshToken(refreshToken)
                .build();
    }

    public TokenResponse refresh(TokenRefreshRequest req) {
        RefreshToken refreshToken = refreshTokenRepository.findByToken(req.getRefreshToken())
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Invalid refresh token"));

        if (refreshToken.getExpiryDate().isBefore(java.time.Instant.now())) {
            refreshTokenRepository.delete(refreshToken);
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Refresh token expired");
        }

        User user = refreshToken.getUser();

        // Token Rotation: 기존 토큰 삭제 후 새 토큰 발급
        refreshTokenRepository.delete(refreshToken);

        String newAccessToken = jwtTokenProvider.createAccessToken(user.getUserId().toString());
        String newRefreshToken = jwtTokenProvider.createRefreshToken(user.getUserId().toString());

        refreshTokenRepository.save(RefreshToken.builder()
                .user(user)
                .token(newRefreshToken)
                .expiryDate(java.time.Instant.now().plusMillis(604800000))
                .build());

        return TokenResponse.builder()
                .accessToken(newAccessToken)
                .refreshToken(newRefreshToken)
                .build();
    }

    public UserResponse getProfile(UUID userId) {
        User user = userRepository.findById(userId)
                .filter(u -> u.getDeletedAt() == null)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "User not found"));

        return UserResponse.builder()
                .userId(user.getUserId())
                .email(user.getEmail())
                .nickname(user.getNickname())
                .profileImageBase64(
                        user.getProfileImage() != null ? Base64.getEncoder().encodeToString(user.getProfileImage())
                                : null)
                .build();
    }

    public void updateProfile(UUID userId, UserUpdateRequest req) {
        User user = userRepository.findById(userId)
                .filter(u -> u.getDeletedAt() == null)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "User not found"));

        if (req.getNickname() != null)
            user.setNickname(req.getNickname());
        if (req.getFcmToken() != null)
            user.setFcmToken(req.getFcmToken());

        userRepository.save(user);
    }

    public void deleteUser(UUID userId) {
        User user = userRepository.findById(userId)
                .filter(u -> u.getDeletedAt() == null)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "User not found"));

        user.setDeletedAt(LocalDateTime.now());
        userRepository.save(user);
    }

    public void updateProfileImage(UUID userId, MultipartFile file) {
        User user = userRepository.findById(userId)
                .filter(u -> u.getDeletedAt() == null)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "User not found"));

        try {
            user.setProfileImage(file.getBytes());
            userRepository.save(user);
        } catch (IOException e) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR, "Failed to upload image");
        }
    }
}
