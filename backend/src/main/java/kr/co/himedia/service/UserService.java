package kr.co.himedia.service;

import kr.co.himedia.common.ApiResponse;
import kr.co.himedia.dto.auth.*;
import kr.co.himedia.entity.User;
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

        String token = jwtTokenProvider.createToken(user.getUserId().toString());
        user.setLastLoginAt(LocalDateTime.now());
        userRepository.save(user);
        return new TokenResponse(token);
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
