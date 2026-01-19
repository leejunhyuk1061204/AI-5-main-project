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
        // 1. DB에 알림 내역 저장
        kr.co.himedia.entity.Notification notification = kr.co.himedia.entity.Notification.builder()
                .user(user)
                .title(title)
                .body(body)
                .type(type)
                .isRead(false)
                .build();
        notificationRepository.save(notification);

        // 2. FCM 전송 (토큰이 있는 경우)
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
                // 푸시 전송 실패가 비즈니스 로직 전체 실패로 이어지지 않게 예외를 삼킴 (필요시 재시도 로직 추가)
            }
        } else {
            log.info("User {} has no FCM token. Notification saved to DB only.", user.getUserId());
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
