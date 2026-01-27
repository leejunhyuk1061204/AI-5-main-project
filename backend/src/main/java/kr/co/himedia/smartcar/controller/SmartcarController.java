package kr.co.himedia.smartcar.controller;

import com.smartcar.sdk.data.Auth;
import kr.co.himedia.smartcar.service.SmartcarService;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/smartcar")
public class SmartcarController {

    private final SmartcarService smartcarService;

    public SmartcarController(SmartcarService smartcarService) {
        this.smartcarService = smartcarService;
    }

    @GetMapping("/login")
    public ResponseEntity<?> getLoginUrl() {
        String authUrl = smartcarService.getAuthUrl();
        return ResponseEntity.status(HttpStatus.FOUND)
                .header("Location", authUrl)
                .build();
    }

    @GetMapping("/callback")
    public ResponseEntity<?> handleCallback(@RequestParam("code") String code) {
        try {
            Auth auth = smartcarService.exchangeCodeForToken(code);
            String accessToken = auth.getAccessToken();

            // Redirect back to the mobile app with the access token
            String redirectUrl = "exp+frontend://smartcar/callback?accessToken=" + accessToken;

            return ResponseEntity.status(HttpStatus.FOUND)
                    .header("Location", redirectUrl)
                    .build();
        } catch (Exception e) {
            e.printStackTrace(); // 서버 로그에 에러 출력
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body("SmartCar Callback Error: " + e.getMessage()); // 화면에 에러 표시
        }
    }

    @GetMapping("/vehicles")
    public ResponseEntity<?> getVehicles(@RequestParam("accessToken") String accessToken) {
        try {
            return ResponseEntity.ok(smartcarService.getVehicles(accessToken));
        } catch (Exception e) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body("Error fetching vehicles: " + e.getMessage());
        }
    }

    @GetMapping("/vehicles/{vehicleId}")
    public ResponseEntity<?> getVehicleAttributes(@PathVariable("vehicleId") String vehicleId,
            @RequestParam("accessToken") String accessToken) {
        try {
            return ResponseEntity.ok(smartcarService.getVehicleAttributes(vehicleId, accessToken));
        } catch (Exception e) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body("Error fetching vehicle attributes: " + e.getMessage());
        }
    }
}
