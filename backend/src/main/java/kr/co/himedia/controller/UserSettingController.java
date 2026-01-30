package kr.co.himedia.controller;

import kr.co.himedia.common.ApiResponse;
import kr.co.himedia.dto.user.UserSettingRequest;
import kr.co.himedia.dto.user.UserSettingResponse;
import kr.co.himedia.security.CustomUserDetails;
import kr.co.himedia.service.UserSettingService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

@Slf4j
@RestController
@RequestMapping("/user/settings")
@RequiredArgsConstructor
public class UserSettingController {

    private final UserSettingService userSettingService;

    @GetMapping
    public ApiResponse<UserSettingResponse> getMySettings(@AuthenticationPrincipal CustomUserDetails userDetails) {
        UserSettingResponse response = userSettingService.getMySettings(userDetails.getUserId());
        return ApiResponse.success(response);
    }

    @PutMapping
    public ApiResponse<UserSettingResponse> updateMySettings(
            @AuthenticationPrincipal CustomUserDetails userDetails,
            @RequestBody UserSettingRequest request) {
        UserSettingResponse response = userSettingService.updateMySettings(userDetails.getUserId(), request);
        return ApiResponse.success(response);
    }
}
