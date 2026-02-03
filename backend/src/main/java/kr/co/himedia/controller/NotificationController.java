package kr.co.himedia.controller;

import kr.co.himedia.common.ApiResponse;
import kr.co.himedia.entity.Notification;
import kr.co.himedia.entity.User;
import kr.co.himedia.repository.UserRepository;
import kr.co.himedia.service.NotificationService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/notifications")
@RequiredArgsConstructor
public class NotificationController {

    private final NotificationService notificationService;
    private final UserRepository userRepository;

    /**
     * [BE-NO-001] 내 알림 목록 조회
     */
    @GetMapping
    public ResponseEntity<ApiResponse<List<kr.co.himedia.dto.notification.NotificationResponse>>> getMyNotifications(
            @AuthenticationPrincipal kr.co.himedia.security.CustomUserDetails userDetails) {

        List<kr.co.himedia.entity.Notification> notifications = notificationService
                .getMyNotifications(userDetails.getUser());

        List<kr.co.himedia.dto.notification.NotificationResponse> response = notifications.stream()
                .map(n -> kr.co.himedia.dto.notification.NotificationResponse.builder()
                        .id(n.getId())
                        .title(n.getTitle())
                        .body(n.getBody())
                        .type(n.getType().name())
                        .isRead(n.getIsRead())
                        .createdAt(n.getCreatedAt())
                        .build())
                .toList();

        return ResponseEntity.ok(ApiResponse.success(response));
    }

    /**
     * [BE-NO-002] 알림 읽음 처리
     */
    @PatchMapping("/{id}/read")
    public ResponseEntity<ApiResponse<Void>> markAsRead(@PathVariable("id") Long id) {
        notificationService.markAsRead(id);
        return ResponseEntity.ok(ApiResponse.success(null));
    }

    /**
     * [TEST] 알림 수동 발송 (테스트용)
     */
    @PostMapping("/send")
    public ResponseEntity<ApiResponse<?>> sendNotification(@RequestBody Map<String, Object> request) {
        String userIdStr = (String) request.get("userId");
        String title = (String) request.get("title");
        String body = (String) request.get("body");
        String typeStr = (String) request.get("type"); // MAINTENANCE_ALERT, SYSTEM_ALERT, etc.

        if (userIdStr == null || title == null || body == null) {
            return ResponseEntity.badRequest()
                    .body(ApiResponse.fail("COMMON_001", "Missing required fields: userId, title, body"));
        }

        UUID userId = UUID.fromString(userIdStr);
        User user = userRepository.findById(userId).orElse(null);
        if (user == null) {
            return ResponseEntity.badRequest().body(ApiResponse.fail("COMMON_002", "User not found"));
        }

        Notification.NotificationType type;
        try {
            type = Notification.NotificationType.valueOf(typeStr);
        } catch (IllegalArgumentException | NullPointerException e) {
            type = Notification.NotificationType.SYSTEM_ALERT; // Default
        }

        notificationService.sendNotification(user, title, body, type);
        return ResponseEntity.ok(ApiResponse.success("Notification sent successfully"));
    }
}
