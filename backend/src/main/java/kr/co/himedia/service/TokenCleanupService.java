package kr.co.himedia.service;

import kr.co.himedia.repository.RefreshTokenRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;

@Slf4j
@Service
@RequiredArgsConstructor
public class TokenCleanupService {

    private final RefreshTokenRepository refreshTokenRepository;

    /**
     * 매일 새벽 3시에 만료된 리프레시 토큰을 정리합니다.
     */
    @Transactional
    @Scheduled(cron = "0 0 3 * * *")
    public void cleanupExpiredTokens() {
        log.info("Starting expired token cleanup...");
        // JpaRepository에서는 만료된 토큰을 일괄 삭제하는 로직을 직접 구현하거나
        // findAll 후 삭제할 수도 있지만 여기서는 쿼리 최적화 생략
        // 실제 운영 환경에서는 @Modifying @Query 등을 사용 권장
        refreshTokenRepository.findAll().stream()
                .filter(token -> token.getExpiryDate().isBefore(Instant.now()))
                .forEach(refreshTokenRepository::delete);
        log.info("Expired token cleanup finished.");
    }
}
