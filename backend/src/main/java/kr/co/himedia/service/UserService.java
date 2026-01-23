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
import org.springframework.transaction.annotation.Transactional;
import kr.co.himedia.security.JwtTokenProvider;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.time.LocalDateTime;
import java.util.Base64;
import java.util.UUID;
import com.google.firebase.auth.FirebaseAuth;
import com.google.firebase.auth.FirebaseToken;
import com.google.api.client.googleapis.auth.oauth2.GoogleIdToken;
import com.google.api.client.googleapis.auth.oauth2.GoogleIdTokenVerifier;
import com.google.api.client.http.javanet.NetHttpTransport;
import com.google.api.client.json.gson.GsonFactory;
import java.util.Collections;

@Service
@RequiredArgsConstructor
@Transactional
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

        // Create refresh token (Upsert: Update if exists, else Insert)
        RefreshToken refreshTokenEntity = refreshTokenRepository.findByUser(user)
                .orElse(RefreshToken.builder()
                        .user(user)
                        .build());

        refreshTokenEntity.setToken(refreshToken);
        refreshTokenEntity.setExpiryDate(java.time.Instant.now().plusMillis(604800000)); // 7 days

        refreshTokenRepository.save(refreshTokenEntity);
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

        // Token Rotation: Update existing token
        String newAccessToken = jwtTokenProvider.createAccessToken(user.getUserId().toString());
        String newRefreshToken = jwtTokenProvider.createRefreshToken(user.getUserId().toString());

        refreshToken.setToken(newRefreshToken);
        refreshToken.setExpiryDate(java.time.Instant.now().plusMillis(604800000));

        refreshTokenRepository.save(refreshToken);

        return TokenResponse.builder()
                .accessToken(newAccessToken)
                .refreshToken(newRefreshToken)
                .build();
    }

    // 소셜 로그인 (Google)
    public TokenResponse socialLogin(SocialLoginRequest req) {
        String email = "";
        String nickname = "";

        // 1. 소셜 제공자에 따른 토큰 검증
        try {
            if ("google".equalsIgnoreCase(req.getProvider())) {
                // Google ID Token 검증 (Frontend가 Firebase Auth를 사용하지 않으므로 직접 검증)
                GoogleIdToken.Payload payload = verifyGoogleIdToken(req.getToken());
                email = payload.getEmail();
                nickname = (String) payload.get("name");

                if (nickname == null) {
                    nickname = "Google User";
                }
            } else if ("kakao".equalsIgnoreCase(req.getProvider())) {
                // 카카오 검증 로직 (여기서는 생략, 추후 구현)
                throw new BaseException(ErrorCode.INTERNAL_SERVER_ERROR,
                        "Kakao login not fully implemented on backend yet.");
            } else {
                throw new BaseException(ErrorCode.INVALID_INPUT_VALUE, "Unsupported provider: " + req.getProvider());
            }
        } catch (Exception e) {
            // 검증 실패 시 예외 처리
            e.printStackTrace();
            throw new BaseException(ErrorCode.INVALID_CREDENTIALS,
                    "Token Verification Failed: " + (e.getMessage() != null ? e.getMessage() : e.toString()));
        }

        try {
            // 2. 이메일로 사용자 조회 또는 자동 회원가입
            String finalEmail = email;
            String finalNickname = nickname;

            User user = userRepository.findByEmail(email).orElseGet(() -> {
                // 신규 회원이면 자동 가입 처리
                User newUser = User.builder()
                        .userId(UUID.randomUUID())
                        .email(finalEmail)
                        .passwordHash(passwordEncoder.encode(UUID.randomUUID().toString())) // 임의의 비밀번호 생성
                        .nickname(finalNickname)
                        .build();
                return userRepository.save(newUser);
            });

            if (user.getDeletedAt() != null) {
                throw new BaseException(ErrorCode.INVALID_CREDENTIALS, "User is deleted.");
            }

            // 3. 토큰 발급 (로그인 처리)
            String accessToken = jwtTokenProvider.createAccessToken(user.getUserId().toString());
            String refreshToken = jwtTokenProvider.createRefreshToken(user.getUserId().toString());

            RefreshToken refreshTokenEntity = refreshTokenRepository.findByUser(user)
                    .orElse(RefreshToken.builder()
                            .user(user)
                            .build());

            refreshTokenEntity.setToken(refreshToken);
            refreshTokenEntity.setExpiryDate(java.time.Instant.now().plusMillis(604800000)); // 7 days

            refreshTokenRepository.save(refreshTokenEntity);
            user.setLastLoginAt(LocalDateTime.now());
            userRepository.save(user);

            return TokenResponse.builder()
                    .accessToken(accessToken)
                    .refreshToken(refreshToken)
                    .build();

        } catch (Exception e) {
            e.printStackTrace();
            throw new BaseException(ErrorCode.INTERNAL_SERVER_ERROR,
                    "Social Login Failed: " + (e.getMessage() != null ? e.getMessage() : e.toString()));
        }
    }

    // 사용자 프로필 조회
    public UserResponse getProfile(UUID userId) {
        User user = userRepository.findById(userId)
                .filter(u -> u.getDeletedAt() == null)
                .orElseThrow(() -> new BaseException(ErrorCode.USER_NOT_FOUND));

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

    // FCM 토큰 조회 (내부 서비스용)
    @Transactional(readOnly = true)
    public String getFcmToken(UUID userId) {
        return userRepository.findById(userId)
                .map(User::getFcmToken)
                .orElse(null);
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

    // Google ID Token 검증 (Frontend에서 Firebase Auth 미사용 시)
    private GoogleIdToken.Payload verifyGoogleIdToken(String tokenString) {
        // Web Client ID (from frontend/sign/Login.tsx or google-services.json)
        final String CLIENT_ID = "415824813180-to8ea5houck16m7as32t9cavi7aq87e5.apps.googleusercontent.com";

        GoogleIdTokenVerifier verifier = new GoogleIdTokenVerifier.Builder(new NetHttpTransport(), new GsonFactory())
                .setAudience(Collections.singletonList(CLIENT_ID))
                .build();

        try {
            GoogleIdToken idToken = verifier.verify(tokenString);
            if (idToken != null) {
                return idToken.getPayload();
            } else {
                throw new BaseException(ErrorCode.INVALID_CREDENTIALS, "Invalid Google ID Token.");
            }
        } catch (Exception e) {
            throw new BaseException(ErrorCode.INVALID_CREDENTIALS,
                    "Google Token Verification Error: " + e.getMessage());
        }
    }
}
