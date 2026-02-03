package kr.co.himedia.dto.notification;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import java.util.Map;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class NotificationTaskMessage {
    private String userId; // 사용자 ID (String format of UUID)
    private Long notificationId; // DB에 저장된 알림 ID
    private String title; // 알림 제목
    private String body; // 알림 본문
    private String type; // 알림 타입 (NotificationType name)
    private Map<String, String> data; // FCM 전송용 추가 데이터 (Deep Link 등)
}
