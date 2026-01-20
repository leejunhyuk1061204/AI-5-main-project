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

        // In a real scenario, the userId should be retrieved from the session/state
        // For demonstration/setup, we are using a temporary hardcoded or mock UUID
        // (This should be refined with actual Security context later)
        UUID mockUserId = UUID.fromString("00000000-0000-0000-0000-000000000000"); // Placeholder

        CloudProvider cloudProvider = CloudProvider.valueOf(provider.toUpperCase());
        cloudAuthService.exchangeCodeAndSave(mockUserId, code, cloudProvider);

        return "연동이 완료되었습니다. 창을 닫으셔도 됩니다.";
    }
}
