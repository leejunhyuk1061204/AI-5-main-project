package kr.co.himedia.service;

import com.google.firebase.messaging.FirebaseMessaging;
import com.google.firebase.messaging.Message;
import com.google.firebase.messaging.Notification;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.Map;

@Slf4j
@Service
public class FcmService {

    /**
     * FCM 메시지 전송
     * 
     * @param info     로그용 정보 (사용자ID 등)
     * @param fcmToken 대상 기기 토큰
     * @param title    알림 제목
     * @param body     알림 본문
     * @param data     추가 데이터 (JSON Map)
     */
    public void sendMessage(String info, String fcmToken, String title, String body, Map<String, String> data) {
        if (fcmToken == null || fcmToken.isEmpty()) {
            log.warn("[FCM] Token is empty for user: {}", info);
            return;
        }

        try {
            // Firebase initialized check (indirectly via try-catch or explicit check if
            // needed)
            // But FirebaseMessaging.getInstance() might throw if app not init.
            // We assume FirebaseConfig initialized it or logged warning.

            Notification notification = Notification.builder()
                    .setTitle(title)
                    .setBody(body)
                    .build();

            Message.Builder messageBuilder = Message.builder()
                    .setToken(fcmToken)
                    .setNotification(notification);

            if (data != null && !data.isEmpty()) {
                messageBuilder.putAllData(data);
            }

            String response = FirebaseMessaging.getInstance().send(messageBuilder.build());
            log.info("[FCM] Sent message to {}: {}, Response: {}", info, title, response);

        } catch (Exception e) {
            log.error("[FCM] Failed to send message to {}: {}", info, e.getMessage());
            // Don't rethrow to avoid breaking the consumer flow
        }
    }
}
