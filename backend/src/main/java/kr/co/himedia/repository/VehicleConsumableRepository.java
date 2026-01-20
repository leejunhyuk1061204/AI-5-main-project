package kr.co.himedia.repository;

import kr.co.himedia.entity.Vehicle;
import kr.co.himedia.entity.VehicleConsumable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Repository
public interface VehicleConsumableRepository extends JpaRepository<VehicleConsumable, UUID> {

    // ConsumableItem의 Code로 조회 (예: ENGINE_OIL)
    Optional<VehicleConsumable> findByVehicleAndConsumableItem_Code(Vehicle vehicle, String code);

    // ConsumableItem의 PK(ID)로 조회
    Optional<VehicleConsumable> findByVehicleAndConsumableItem_Id(Vehicle vehicle, Long consumableItemId);

    List<VehicleConsumable> findByVehicle(Vehicle vehicle);

    // AI 진단 시 LazyInitException 방지용 (ConsumableItem 함께 조회)
    @Query("SELECT vc FROM VehicleConsumable vc JOIN FETCH vc.consumableItem WHERE vc.vehicle = :vehicle")
    List<VehicleConsumable> findByVehicleWithItem(@Param("vehicle") Vehicle vehicle);
}
