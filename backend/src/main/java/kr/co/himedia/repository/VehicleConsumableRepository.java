package kr.co.himedia.repository;

import kr.co.himedia.entity.Vehicle;
import kr.co.himedia.entity.VehicleConsumable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Repository
public interface VehicleConsumableRepository extends JpaRepository<VehicleConsumable, UUID> {

    // ConsumableItem의 Code로 조회 (예: ENGINE_OIL)
    Optional<VehicleConsumable> findByVehicleAndConsumableItem_Code(Vehicle vehicle, String code);

    List<VehicleConsumable> findByVehicle(Vehicle vehicle);
}
