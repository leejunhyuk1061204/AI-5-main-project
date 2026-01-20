package kr.co.himedia.repository;

import kr.co.himedia.entity.TripSummary;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Repository
public interface TripSummaryRepository extends JpaRepository<TripSummary, TripSummary.TripSummaryId> {

    Optional<TripSummary> findByTripId(UUID tripId);

    List<TripSummary> findByVehicleIdOrderByStartTimeDesc(UUID vehicleId);

    @Query("SELECT t FROM TripSummary t WHERE t.vehicleId = :vehicleId AND t.endTime IS NULL ORDER BY t.startTime DESC LIMIT 1")
    Optional<TripSummary> findActiveTripByVehicleId(@Param("vehicleId") UUID vehicleId);

    @Query("SELECT t FROM TripSummary t WHERE t.vehicleId = :vehicleId ORDER BY t.endTime DESC LIMIT 1")
    Optional<TripSummary> findLatestTripByVehicleId(@Param("vehicleId") UUID vehicleId);

    // [BE-TD-005] 유효 주행 거리(0.1km) 이상인 주행 기록만 조회 (사용자 노출용)
    @Query("SELECT t FROM TripSummary t WHERE t.vehicleId = :vehicleId AND t.distance >= :minDistance ORDER BY t.startTime DESC")
    List<TripSummary> findValidTripsByVehicleId(@Param("vehicleId") UUID vehicleId,
            @Param("minDistance") double minDistance);
}
