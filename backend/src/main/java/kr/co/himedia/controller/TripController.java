package kr.co.himedia.controller;

import kr.co.himedia.common.ApiResponse;
import kr.co.himedia.dto.trip.TripEndRequest;
import kr.co.himedia.dto.trip.TripStartRequest;
import kr.co.himedia.entity.TripSummary;
import kr.co.himedia.service.TripService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/trips")
@RequiredArgsConstructor
public class TripController {

    private final TripService tripService;

    /**
     * [BE-TD-005] 주행 이력 목록 조회
     * 특정 차량의 주행 기록 리스트를 반환합니다.
     */
    @GetMapping
    public ResponseEntity<ApiResponse<List<TripSummary>>> getTrips(@RequestParam("vehicleId") UUID vehicleId) {
        return ResponseEntity.ok(ApiResponse.success(tripService.getTripsByVehicle(vehicleId)));
    }

    /**
     * [BE-TD-005] 주행 이력 상세 조회
     * 특정 주행 기록의 상세 정보(경로, 통계 등)를 반환합니다.
     */
    @GetMapping("/{tripId}")
    public ResponseEntity<ApiResponse<TripSummary>> getTripDetail(@PathVariable("tripId") UUID tripId) {
        return ResponseEntity.ok(ApiResponse.success(tripService.getTripDetail(tripId)));
    }

    /**
     * [BE-TD-001] 주행 세션 개시
     * 새로운 주행 세션을 시작하고 Trip ID를 발급합니다.
     */
    @PostMapping("/start")
    public ResponseEntity<ApiResponse<TripSummary>> startTrip(@Valid @RequestBody TripStartRequest req) {
        return ResponseEntity.ok(ApiResponse.success(tripService.startTrip(req.getVehicleId())));
    }

    /**
     * [BE-TD-004] 주행 세션 종료 & 요약
     * 주행 세션을 종료하고 최종 통계(점수, 거리 등)를 확정합니다.
     */
    @PostMapping("/end")
    public ResponseEntity<ApiResponse<TripSummary>> endTrip(@Valid @RequestBody TripEndRequest req) {
        return ResponseEntity.ok(ApiResponse.success(tripService.endTrip(req.getTripId())));
    }
}
