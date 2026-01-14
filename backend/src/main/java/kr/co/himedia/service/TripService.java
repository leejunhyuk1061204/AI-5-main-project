package kr.co.himedia.service;

import kr.co.himedia.entity.TripSummary;
import kr.co.himedia.repository.TripSummaryRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class TripService {

    private final TripSummaryRepository tripSummaryRepository;

    @Transactional(readOnly = true)
    public List<TripSummary> getTripsByVehicle(UUID vehicleId) {
        // In a real app, you might want to add pagination or date filters
        return tripSummaryRepository.findAll().stream()
                .filter(t -> t.getVehicleId().equals(vehicleId))
                .toList();
    }

    @Transactional(readOnly = true)
    public TripSummary getTripDetail(UUID tripId) {
        return tripSummaryRepository.findAll().stream()
                .filter(t -> t.getTripId().equals(tripId))
                .findFirst()
                .orElseThrow(() -> new IllegalArgumentException("Trip not found: " + tripId));
    }
}
