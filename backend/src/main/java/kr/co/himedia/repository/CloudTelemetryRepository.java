package kr.co.himedia.repository;

import kr.co.himedia.entity.CloudTelemetry;
import kr.co.himedia.entity.Vehicle;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.UUID;

@Repository
public interface CloudTelemetryRepository extends JpaRepository<CloudTelemetry, UUID> {
    List<CloudTelemetry> findByVehicleOrderByLastSyncedAtDesc(Vehicle vehicle);
}
