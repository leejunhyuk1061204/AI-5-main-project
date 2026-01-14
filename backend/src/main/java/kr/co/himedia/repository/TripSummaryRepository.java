package kr.co.himedia.repository;

import kr.co.himedia.entity.TripSummary;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.Optional;
import java.util.UUID;

@Repository
public interface TripSummaryRepository extends JpaRepository<TripSummary, TripSummary.TripSummaryId> {

    @Query("SELECT t FROM TripSummary t WHERE t.vehicleId = :vehicleId AND t.endTime IS NULL ORDER BY t.startTime DESC LIMIT 1")
    Optional<TripSummary> findActiveTripByVehicleId(@Param("vehicleId") UUID vehicleId);

    @Query("SELECT t FROM TripSummary t WHERE t.vehicleId = :vehicleId ORDER BY t.endTime DESC LIMIT 1")
    Optional<TripSummary> findLatestTripByVehicleId(@Param("vehicleId") UUID vehicleId);
}
