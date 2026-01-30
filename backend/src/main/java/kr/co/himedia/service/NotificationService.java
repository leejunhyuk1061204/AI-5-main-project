package kr.co.himedia.service;

import com.google.firebase.messaging.FirebaseMessaging;
import com.google.firebase.messaging.Message;
import com.google.firebase.messaging.Notification;
import kr.co.himedia.entity.User;
import kr.co.himedia.repository.NotificationRepository;
import kr.co.himedia.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;

@Service
@RequiredArgsConstructor
@Slf4j
public class NotificationService {

    private final NotificationRepository notificationRepository;
    private final UserRepository userRepository;
    private final kr.co.himedia.repository.UserSettingRepository userSettingRepository;

    /**
     * 알림 전송 및 저장
     *
     * @param user  수신자
     * @param title 알림 제목
     * @param body  알림 내용
     * @param type  알림 유형
     */
    @Transactional
    public void sendNotification(User user, String title, String body,
            kr.co.himedia.entity.Notification.NotificationType type) {
        // 1. DB에 알림 내역 저장 (항상 저장)
        kr.co.himedia.entity.Notification notification = kr.co.himedia.entity.Notification.builder()
                .user(user)
                .title(title)
                .body(body)
                .type(type)
                .isRead(false)
                .build();
        notificationRepository.save(notification);

        // 2. 푸시 발송 여부 판단 (설정 기반 필터링)
        if (!shouldSendPush(user, type)) {
            log.info("Push notification skipped due to user settings. User: {}, Type: {}", user.getUserId(), type);
            return;
        }

        // 3. FCM 전송 (토큰이 있는 경우)
        if (user.getFcmToken() != null && !user.getFcmToken().isEmpty()) {
            try {
                Message message = Message.builder()
                        .setToken(user.getFcmToken())
                        .setNotification(Notification.builder()
                                .setTitle(title)
                                .setBody(body)
                                .build())
                        .putData("type", type.name())
                        .putData("notificationId", notification.getId().toString())
                        .build();

                String response = FirebaseMessaging.getInstance().send(message);
                log.info("FCM Sent successfully: " + response);
            } catch (Exception e) {
                log.error("FCM Send failed: " + e.getMessage());
            }
        } else {
            log.info("User {} has no FCM token. Notification saved to DB only.", user.getUserId());
        }
    }

    private boolean shouldSendPush(User user, kr.co.himedia.entity.Notification.NotificationType type) {
        // 사용자 설정 조회 (없으면 기본값 사용/생성 없이 로직상 True 처리도 가능하지만, 정합성을 위해 조회)
        // 여기서는 Repository를 직접 조회하여 성능 최적화 (Entity Graph 등 고려 가능하나 단순 조회)
        kr.co.himedia.entity.UserSetting setting = userSettingRepository.findById(user.getUserId())
                .orElse(null);

        // 설정이 아예 없으면 기본 정책을 따름 (기본적으로 중요 알림은 발송)
        if (setting == null) {
            return true;
        }

        // 1. 야간 에티켓 (21:00 ~ 08:00) 체크
        // SYSTEM_ALERT(시스템/긴급)는 시간 무시하고 발송
        if (type != kr.co.himedia.entity.Notification.NotificationType.SYSTEM_ALERT) {
            LocalDateTime now = LocalDateTime.now();
            int hour = now.getHour();
            boolean isNight = hour >= 21 || hour < 8;
            if (isNight && !setting.getNightPushAllowed()) {
                log.info("Push skipped: Night time ({}h) and night push disabled.", hour);
                return false;
            }
        }

        // 2. 카테고리별 수신 여부 체크
        switch (type) {
            case MAINTENANCE_ALERT:
                return setting.getNotiMaintenance();
            case COMMUNITY_ALERT: // 마케팅으로 간주
                return setting.getNotiMarketing();
            case SYSTEM_ALERT:
                return true; // 시스템 필수 공지는 설정 무시하고 발송 (또는 notiRecall 등을 사용할 수 있음)
            default:
                return true;
        }
    }

    // 내 알림 목록 조회
    @Transactional(readOnly = true)
    public List<kr.co.himedia.entity.Notification> getMyNotifications(User user) {
        return notificationRepository.findByUserOrderByCreatedAtDesc(user);
    }

    // 알림 읽음 처리
    @Transactional
    public void markAsRead(Long notificationId) {
        notificationRepository.findById(notificationId).ifPresent(notification -> {
            notification.setIsRead(true);
        });
    }
}
