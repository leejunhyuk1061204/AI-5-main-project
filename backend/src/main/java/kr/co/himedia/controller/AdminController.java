package kr.co.himedia.controller;

import kr.co.himedia.entity.ObdLog;
import kr.co.himedia.repository.ObdLogRepository;
import kr.co.himedia.scheduler.TripScheduler;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.UUID;

@RestController
@RequestMapping("/admin/test")
@RequiredArgsConstructor
public class AdminController {

    private final TripScheduler tripScheduler;
    private final ObdLogRepository obdLogRepository;
    private final kr.co.himedia.repository.VehicleRepository vehicleRepository;

    // 테스트용: 4일 전 과거 데이터 강제 주입
    @PostMapping("/insert-old-logs")
    public ResponseEntity<String> insertOldLogs() {
        OffsetDateTime oldTime = OffsetDateTime.now(ZoneOffset.UTC).minusDays(4);

        // 실제 존재하는 차량 ID 조회
        java.util.List<kr.co.himedia.entity.Vehicle> vehicles = vehicleRepository.findAll();
        if (vehicles.isEmpty()) {
            return ResponseEntity.badRequest().body("No vehicles found. Please register a vehicle first.");
        }
        UUID realVehicleId = vehicles.get(0).getVehicleId();

        ObdLog log = ObdLog.builder()
                .time(oldTime)
                .vehicleId(realVehicleId)
                .rpm(0.0)
                .speed(0.0)
                .voltage(0.0)
                .coolantTemp(0.0)
                .engineLoad(0.0)
                .fuelTrimShort(0.0)
                .fuelTrimLong(0.0)
                .intakeTemp(0.0)
                .map(0.0)
                .maf(0.0)
                .throttlePos(0.0)
                .engineRuntime(0)
                .jsonExtra(null)
                .build();
        obdLogRepository.save(log);

        return ResponseEntity.ok("Inserted an old log at: " + oldTime + " for Vehicle ID: " + realVehicleId);
    }

    // 테스트용: 데이터 리텐션 스케줄러 강제 실행
    @PostMapping("/trigger-cleanup")
    public ResponseEntity<String> triggerCleanup() {
        tripScheduler.cleanupOldLogs();
        return ResponseEntity.ok("Triggered cleanupOldLogs manually.");
    }

}
