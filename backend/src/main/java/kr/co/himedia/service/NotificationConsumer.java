package kr.co.himedia.service;

import kr.co.himedia.config.RabbitConfig;
import kr.co.himedia.dto.notification.NotificationTaskMessage;
import kr.co.himedia.entity.User;
import kr.co.himedia.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Slf4j
@Service
@RequiredArgsConstructor
public class NotificationConsumer {

    private final FcmService fcmService;
    private final UserRepository userRepository;

    @RabbitListener(queues = RabbitConfig.NOTIFICATION_QUEUE_NAME)
    @Transactional
    public void receiveNotificationTask(NotificationTaskMessage task) {
        log.info("[NotificationConsumer] Received task for User: {}, Type: {}", task.getUserId(), task.getType());

        try {
            // 1. 사용자 조회 (FCM 토큰 확인)
            // task.getUserId()는 UUID 문자열임
            java.util.UUID userId = java.util.UUID.fromString(task.getUserId());
            User user = userRepository.findById(userId).orElse(null);

            if (user == null) {
                log.warn("[NotificationConsumer] User not found: {}", task.getUserId());
                return;
            }

            String fcmToken = user.getFcmToken();
            if (fcmToken == null || fcmToken.isEmpty()) {
                log.info("[NotificationConsumer] No FCM Token for user: {}. Skip.", task.getUserId());
                return;
            }

            // 2. FCM 발송
            // info 인자는 로그용
            String info = "User-" + user.getUserId();
            fcmService.sendMessage(info, fcmToken, task.getTitle(), task.getBody(), task.getData());

            log.info("[NotificationConsumer] FCM Sent Successfully. NotiID: {}", task.getNotificationId());

        } catch (Exception e) {
            log.error("[NotificationConsumer] Failed to process notification task", e);
            // 필요 시 DLQ로 보내거나 재시도 로직 (RabbitListener 기본 리트라이 사용)
            throw new RuntimeException("Notification processing failed", e);
        }
    }
}
