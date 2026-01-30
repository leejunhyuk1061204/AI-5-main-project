package kr.co.himedia.controller;

import kr.co.himedia.entity.Notification;
import kr.co.himedia.entity.User;
import kr.co.himedia.repository.UserRepository;
import kr.co.himedia.service.NotificationService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/notifications")
@RequiredArgsConstructor
public class NotificationController {

    private final NotificationService notificationService;
    private final UserRepository userRepository;

    @PostMapping("/send")
    public ResponseEntity<String> sendNotification(@RequestBody Map<String, Object> request) {
        String userIdStr = (String) request.get("userId");
        String title = (String) request.get("title");
        String body = (String) request.get("body");
        String typeStr = (String) request.get("type"); // MAINTENANCE_ALERT, SYSTEM_ALERT, etc.

        if (userIdStr == null || title == null || body == null) {
            return ResponseEntity.badRequest().body("Missing required fields: userId, title, body");
        }

        UUID userId = UUID.fromString(userIdStr);
        User user = userRepository.findById(userId).orElse(null);
        if (user == null) {
            return ResponseEntity.badRequest().body("User not found");
        }

        Notification.NotificationType type;
        try {
            type = Notification.NotificationType.valueOf(typeStr);
        } catch (IllegalArgumentException | NullPointerException e) {
            type = Notification.NotificationType.SYSTEM_ALERT; // Default
        }

        notificationService.sendNotification(user, title, body, type);
        return ResponseEntity.ok("Notification sent successfully");
    }
}
