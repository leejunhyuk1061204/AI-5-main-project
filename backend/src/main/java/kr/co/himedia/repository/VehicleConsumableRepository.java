package kr.co.himedia.repository;

import kr.co.himedia.entity.ConsumableItem;
import kr.co.himedia.entity.Vehicle;
import kr.co.himedia.entity.VehicleConsumable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface VehicleConsumableRepository extends JpaRepository<VehicleConsumable, Long> {
    Optional<VehicleConsumable> findByVehicleAndConsumableItem(Vehicle vehicle, ConsumableItem consumableItem);

    List<VehicleConsumable> findByVehicle(Vehicle vehicle);
}
