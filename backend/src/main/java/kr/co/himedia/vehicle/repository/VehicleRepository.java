package kr.co.himedia.vehicle.repository;

import kr.co.himedia.vehicle.entity.Vehicle;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface VehicleRepository extends JpaRepository<Vehicle, UUID> {
    List<Vehicle> findByUserIdAndDeletedAtIsNull(UUID userId);

    Optional<Vehicle> findByVehicleIdAndDeletedAtIsNull(UUID vehicleId);

    Optional<Vehicle> findByUserIdAndIsPrimaryTrueAndDeletedAtIsNull(UUID userId);
}
