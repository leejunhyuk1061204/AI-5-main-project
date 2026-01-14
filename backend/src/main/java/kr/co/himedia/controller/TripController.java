package kr.co.himedia.controller;

import kr.co.himedia.common.ApiResponse;
import kr.co.himedia.entity.TripSummary;
import kr.co.himedia.service.TripService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import org.springframework.http.ResponseEntity;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/trips")
@RequiredArgsConstructor
public class TripController {

    private final TripService tripService;

    @GetMapping
    public ResponseEntity<ApiResponse<List<TripSummary>>> getTrips(@RequestParam("vehicleId") UUID vehicleId) {
        return ResponseEntity.ok(ApiResponse.success(tripService.getTripsByVehicle(vehicleId)));
    }

    @GetMapping("/{tripId}")
    public ResponseEntity<ApiResponse<TripSummary>> getTripDetail(@PathVariable("tripId") UUID tripId) {
        return ResponseEntity.ok(ApiResponse.success(tripService.getTripDetail(tripId)));
    }
}
