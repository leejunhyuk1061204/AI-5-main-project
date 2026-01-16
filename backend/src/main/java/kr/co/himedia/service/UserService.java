package kr.co.himedia.service;

import kr.co.himedia.common.exception.BaseException;
import kr.co.himedia.common.exception.ErrorCode;
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

    // 사용자 회원가입
    public UserResponse createUser(SignupRequest req) {
        userRepository.findByEmail(req.getEmail()).ifPresent(u -> {
            throw new BaseException(ErrorCode.EMAIL_ALREADY_EXISTS);
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

    // 사용자 로그인 및 토큰 발급
    public TokenResponse authenticate(LoginRequest req) {
        User user = userRepository.findByEmail(req.getEmail())
                .orElseThrow(() -> new BaseException(ErrorCode.INVALID_CREDENTIALS));

        if (!passwordEncoder.matches(req.getPassword(), user.getPasswordHash())) {
            throw new BaseException(ErrorCode.INVALID_CREDENTIALS);
        }

        if (user.getDeletedAt() != null) {
            throw new BaseException(ErrorCode.INVALID_CREDENTIALS);
        }

        String accessToken = jwtTokenProvider.createAccessToken(user.getUserId().toString());
        String refreshToken = jwtTokenProvider.createRefreshToken(user.getUserId().toString());

        // 기존 리프레시 토큰이 있다면 삭제
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
                .orElseThrow(() -> new BaseException(ErrorCode.INVALID_REFRESH_TOKEN));

        if (refreshToken.getExpiryDate().isBefore(java.time.Instant.now())) {
            refreshTokenRepository.delete(refreshToken);
            throw new BaseException(ErrorCode.REFRESH_TOKEN_EXPIRED);
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

    // 사용자 프로필 조회
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

    // 사용자 프로필 정보 수정
    public void updateProfile(UUID userId, UserUpdateRequest req) {
        User user = userRepository.findById(userId)
                .filter(u -> u.getDeletedAt() == null)
                .orElseThrow(() -> new BaseException(ErrorCode.USER_NOT_FOUND));

        if (req.getNickname() != null)
            user.setNickname(req.getNickname());
        if (req.getFcmToken() != null)
            user.setFcmToken(req.getFcmToken());
        if (req.getPassword() != null && !req.getPassword().isEmpty()) {
            user.setPasswordHash(passwordEncoder.encode(req.getPassword()));
        }

        userRepository.save(user);
    }

    // FCM 토큰 전용 업데이트
    public void updateFcmToken(UUID userId, String fcmToken) {
        User user = userRepository.findById(userId)
                .filter(u -> u.getDeletedAt() == null)
                .orElseThrow(() -> new BaseException(ErrorCode.USER_NOT_FOUND));

        user.setFcmToken(fcmToken);
        userRepository.save(user);
    }

    // 사용자 회원 탈퇴 (Soft Delete)
    public void deleteUser(UUID userId) {
        User user = userRepository.findById(userId)
                .filter(u -> u.getDeletedAt() == null)
                .orElseThrow(() -> new BaseException(ErrorCode.USER_NOT_FOUND));

        user.setDeletedAt(LocalDateTime.now());
        userRepository.save(user);
    }

    // 사용자 프로필 이미지 업로드
    public void updateProfileImage(UUID userId, MultipartFile file) {
        User user = userRepository.findById(userId)
                .filter(u -> u.getDeletedAt() == null)
                .orElseThrow(() -> new BaseException(ErrorCode.USER_NOT_FOUND));

        try {
            user.setProfileImage(file.getBytes());
            userRepository.save(user);
        } catch (IOException e) {
            throw new BaseException(ErrorCode.INTERNAL_SERVER_ERROR, "이미지 업로드에 실패했습니다.");
        }
    }
}
