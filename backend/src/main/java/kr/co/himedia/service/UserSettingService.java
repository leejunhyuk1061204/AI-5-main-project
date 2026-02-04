package kr.co.himedia.service;

import kr.co.himedia.dto.user.UserSettingRequest;
import kr.co.himedia.dto.user.UserSettingResponse;
import kr.co.himedia.entity.User;
import kr.co.himedia.entity.UserSetting;
import kr.co.himedia.repository.UserRepository;
import kr.co.himedia.repository.UserSettingRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.UUID;

@Slf4j
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class UserSettingService {

    private final UserSettingRepository userSettingRepository;
    private final UserRepository userRepository;

    /**
     * 사용자 알림 설정 조회
     * 설정이 없으면 기본값으로 생성 후 반환 (Lazy Loading 전략)
     */
    @Transactional
    public UserSettingResponse getMySettings(UUID userId) {
        UserSetting setting = userSettingRepository.findById(userId)
                .orElseGet(() -> createDefaultSetting(userId));

        return UserSettingResponse.from(setting);
    }

    /**
     * 사용자 알림 설정 수정
     */
    @Transactional
    public UserSettingResponse updateMySettings(UUID userId, UserSettingRequest request) {
        UserSetting setting = userSettingRepository.findById(userId)
                .orElseGet(() -> createDefaultSetting(userId));

        if (request.getNotiMaintenance() != null)
            setting.setNotiMaintenance(request.getNotiMaintenance());
        if (request.getNotiAnomaly() != null)
            setting.setNotiAnomaly(request.getNotiAnomaly());
        if (request.getNotiDtcTts() != null)
            setting.setNotiDtcTts(request.getNotiDtcTts());
        if (request.getNotiMarketing() != null)
            setting.setNotiMarketing(request.getNotiMarketing());
        if (request.getNightPushAllowed() != null)
            setting.setNightPushAllowed(request.getNightPushAllowed());

        log.info("User settings updated for user: {}", userId);
        return UserSettingResponse.from(setting);
    }

    private UserSetting createDefaultSetting(UUID userId) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new IllegalArgumentException("User not found: " + userId));

        UserSetting newSetting = UserSetting.builder()
                .user(user)
                .build(); // Default values are applied by @Builder.Default

        return userSettingRepository.save(newSetting);
    }
}
