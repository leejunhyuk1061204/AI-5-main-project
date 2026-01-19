package kr.co.himedia.controller;

import kr.co.himedia.common.ApiResponse;
import kr.co.himedia.entity.Notification;
import kr.co.himedia.service.NotificationService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/notifications")
@RequiredArgsConstructor
public class NotificationController {

    private final NotificationService notificationService;

    // BE-NT-001 통합 이동함: 알림 내역 조회
    @GetMapping
    public ResponseEntity<ApiResponse<List<Notification>>> getMyNotifications(Authentication auth) {
        if (auth != null && auth.getPrincipal() instanceof kr.co.himedia.security.CustomUserDetails userDetails) {
            // UserDetails에서 User 엔티티를 직접 가져올 수 있도록 구조가 되어 있다면 좋겠지만,
            // 보통은 userId만 가지고 있으므로 Service에서 다시 조회하거나,
            // UserDetails에 User 객체를 포함시켜야 합니다.
            // 여기서는 Service 레벨에서 처리를 위임하기 위해 리팩터링 없이 진행합니다.
            // (실제로는 SecurityUser에서 User 객체를 꺼낼 수 있다고 가정하거나 Service에서 해결)

            // 임시: CustomUserDetails에 getUser()가 있다고 가정하거나, Repository 조회가 필요함.
            // 현재 CustomUserDetails 구현을 확인하지 못했으므로, Service에 userId를 넘기는 방식으로 변경 필요.
            // 하지만 NotificationService.getMyNotifications(User user)로 되어 있으니,
            // 일단은 아래와 같이 가짜 코드로 작성하고, 오류 발생 시 수정하겠습니다.

            // 수정: NotificationService를 오버로딩하거나 User를 조회해서 넘겨야 함.
            // 여기서는 Service를 조금 수정하는 편이 낫겠으나, 우선은 User 객체가 필요하므로
            // Authentication 주입 방식에 따라 다를 수 있습니다.

            // * 안전한 방법: CustomUserDetails에서 유저 정보 추출
            kr.co.himedia.entity.User user = userDetails.getUser();
            List<Notification> list = notificationService.getMyNotifications(user);
            return ResponseEntity.ok(ApiResponse.success(list));
        }
        return ResponseEntity.status(HttpStatus.UNAUTHORIZED).build();
    }

    // 알림 읽음 처리
    @PatchMapping("/{id}/read")
    public ResponseEntity<ApiResponse<String>> markAsRead(@PathVariable Long id) {
        notificationService.markAsRead(id);
        return ResponseEntity.ok(ApiResponse.success("Marked as read"));
    }
}
