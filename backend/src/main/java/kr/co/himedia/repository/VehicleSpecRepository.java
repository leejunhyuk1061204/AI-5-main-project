package kr.co.himedia.repository;

import kr.co.himedia.entity.Vehicle;
import kr.co.himedia.entity.VehicleSpec;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;
import java.util.UUID;

@Repository
public interface VehicleSpecRepository extends JpaRepository<VehicleSpec, UUID> {
    Optional<VehicleSpec> findByVehicle(Vehicle vehicle);
}
