package kr.co.himedia.repository;

import kr.co.himedia.entity.Vehicle;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface VehicleRepository extends JpaRepository<Vehicle, UUID> {
    List<Vehicle> findByUserIdAndDeletedAtIsNullOrderByCreatedAtAsc(UUID userId);

    Optional<Vehicle> findByVehicleIdAndDeletedAtIsNull(UUID vehicleId);

    Optional<Vehicle> findByUserIdAndIsPrimaryTrueAndDeletedAtIsNull(UUID userId);

    boolean existsByVinAndDeletedAtIsNull(String vin);

    List<Vehicle> findByCloudLinkedTrueAndDeletedAtIsNull();
}
