package kr.co.himedia.backend.Service.auth;

import kr.co.himedia.backend.DTO.auth.SignupRequest;
import kr.co.himedia.backend.DTO.auth.UserResponse;
import kr.co.himedia.backend.DTO.auth.LoginRequest;
import kr.co.himedia.backend.DTO.auth.TokenResponse;
import kr.co.himedia.backend.domain.user.User;
import kr.co.himedia.backend.Repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.util.UUID;
import kr.co.himedia.backend.global.security.JwtTokenProvider;

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

        String token = jwtTokenProvider.createToken(user.getEmail());
        return new TokenResponse(token);
    }
}
