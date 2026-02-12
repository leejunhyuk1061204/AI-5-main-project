package kr.co.himedia.smartcar.controller;

import com.smartcar.sdk.SmartcarException;
import com.smartcar.sdk.data.Auth;
import com.smartcar.sdk.data.VehicleAttributes;
import com.smartcar.sdk.data.VehicleIds;
import kr.co.himedia.smartcar.service.SmartcarService;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import kr.co.himedia.security.CustomUserDetails;
import kr.co.himedia.smartcar.dto.SmartcarSyncResponse;
import org.springframework.security.core.annotation.AuthenticationPrincipal;

import java.util.List;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
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
    public ResponseEntity<?> getLoginUrl(@RequestParam(value = "vehicleId", required = false) String vehicleId) {
        // vehicleId가 있으면 state 파라미터로 전달하여 콜백에서 다시 돌려받음
        String state = (vehicleId != null && !vehicleId.isEmpty()) ? vehicleId : "";
        String authUrl = smartcarService.getAuthUrl(state);
        return ResponseEntity.status(HttpStatus.FOUND)
                .header("Location", authUrl)
                .build();
    }

    @GetMapping("/callback")
    public ResponseEntity<?> handleCallback(@RequestParam("code") String code,
            @RequestParam(value = "state", required = false) String state) {
        try {
            Auth auth = smartcarService.exchangeCodeForToken(code);
            String accessToken = auth.getAccessToken();

            // Redirect back to the mobile app with the access token and vehicleId(from
            // state)
            String redirectUrl = "frontend://smartcar/callback?accessToken=" + accessToken
                    + (state != null && !state.isEmpty() ? "&vehicleId=" + state : "");

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

    /**
     * 사용자의 Smartcar 계정과 연동된 차량들을 동기화(매칭 또는 신규 등록)합니다.
     * vehicleId가 제공되면 해당 차량에 대해서만 특정하여 연동(Targeted Linking)을 수행합니다.
     */
    @PostMapping("/sync")
    public ResponseEntity<?> syncVehicles(@AuthenticationPrincipal CustomUserDetails userDetails,
            @RequestParam("accessToken") String accessToken,
            @RequestParam(value = "vehicleId", required = false) String vehicleId) {
        try {
            // vehicleId가 있으면 UUID로 변환, 없으면 null
            java.util.UUID targetVehicleId = (vehicleId != null && !vehicleId.isEmpty())
                    ? java.util.UUID.fromString(vehicleId)
                    : null;

            List<SmartcarSyncResponse.VehicleSyncResult> results = smartcarService.syncVehicles(userDetails.getUserId(),
                    accessToken, targetVehicleId);

            SmartcarSyncResponse response = SmartcarSyncResponse.builder()
                    .totalCount(results.size())
                    .results(results)
                    .build();

            return ResponseEntity.ok(response);
        } catch (Exception e) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body("Error syncing vehicles: " + e.getMessage());
        }
    }

    // --- Vehicle Control Endpoints ---

    @PostMapping("/vehicles/{vehicleId}/lock")
    public ResponseEntity<?> lockVehicle(@PathVariable("vehicleId") String vehicleId,
            @RequestParam("accessToken") String accessToken) {
        try {
            smartcarService.lockVehicle(vehicleId, accessToken);
            return ResponseEntity.ok("Vehicle locked successfully");
        } catch (Exception e) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body("Error locking vehicle: " + e.getMessage());
        }
    }

    @PostMapping("/vehicles/{vehicleId}/unlock")
    public ResponseEntity<?> unlockVehicle(@PathVariable("vehicleId") String vehicleId,
            @RequestParam("accessToken") String accessToken) {
        try {
            smartcarService.unlockVehicle(vehicleId, accessToken);
            return ResponseEntity.ok("Vehicle unlocked successfully");
        } catch (Exception e) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body("Error unlocking vehicle: " + e.getMessage());
        }
    }

    @PostMapping("/vehicles/{vehicleId}/charge/start")
    public ResponseEntity<?> startCharging(@PathVariable("vehicleId") String vehicleId,
            @RequestParam("accessToken") String accessToken) {
        try {
            smartcarService.startCharging(vehicleId, accessToken);
            return ResponseEntity.ok("Charging started successfully");
        } catch (Exception e) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body("Error starting charge: " + e.getMessage());
        }
    }

    @PostMapping("/vehicles/{vehicleId}/charge/stop")
    public ResponseEntity<?> stopCharging(@PathVariable("vehicleId") String vehicleId,
            @RequestParam("accessToken") String accessToken) {
        try {
            smartcarService.stopCharging(vehicleId, accessToken);
            return ResponseEntity.ok("Charging stopped successfully");
        } catch (Exception e) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body("Error stopping charge: " + e.getMessage());
        }
    }
}
