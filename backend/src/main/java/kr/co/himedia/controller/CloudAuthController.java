package kr.co.himedia.controller;

import kr.co.himedia.entity.CloudProvider;
import kr.co.himedia.service.CloudAuthService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.UUID;

@RestController
@RequestMapping("/auth/callback")
@RequiredArgsConstructor
public class CloudAuthController {

    private final CloudAuthService cloudAuthService;

    @GetMapping("/{provider}")
    public String oauthCallback(
            @PathVariable String provider,
            @RequestParam String code,
            @RequestParam(required = false) String state) {

        // state 파라미터에서 userId를 추출 (OAuth 요청 시 state에 userId를 담아서 전송)
        UUID userId;
        if (state != null && !state.isEmpty()) {
            try {
                userId = UUID.fromString(state);
            } catch (IllegalArgumentException e) {
                return "오류: 유효하지 않은 사용자 ID입니다.";
            }
        } else {
            return "오류: state 파라미터가 필요합니다.";
        }

        CloudProvider cloudProvider = CloudProvider.valueOf(provider.toUpperCase());
        cloudAuthService.exchangeCodeAndSave(userId, code, cloudProvider);

        return "연동이 완료되었습니다. 창을 닫으셔도 됩니다.";
    }

}
