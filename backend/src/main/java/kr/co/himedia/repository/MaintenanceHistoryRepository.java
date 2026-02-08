package kr.co.himedia.repository;

import kr.co.himedia.entity.MaintenanceHistory;
import kr.co.himedia.entity.Vehicle;
import java.time.LocalDate;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.UUID;
import java.util.Optional;

import kr.co.himedia.entity.ConsumableItem;

@Repository
public interface MaintenanceHistoryRepository extends JpaRepository<MaintenanceHistory, UUID> {
    List<MaintenanceHistory> findByVehicleOrderByMaintenanceDateDesc(Vehicle vehicle);

    List<MaintenanceHistory> findByVehicleAndMaintenanceDateBetweenOrderByMaintenanceDateDesc(
            Vehicle vehicle, LocalDate startDate, LocalDate endDate);

    List<MaintenanceHistory> findByVehicleAndConsumableItem_CodeOrderByMaintenanceDateDesc(
            Vehicle vehicle, String consumableItemCode);

    List<MaintenanceHistory> findByVehicleAndConsumableItem_CodeAndMaintenanceDateBetweenOrderByMaintenanceDateDesc(
            Vehicle vehicle, String consumableItemCode, LocalDate startDate, LocalDate endDate);

    Optional<MaintenanceHistory> findTopByVehicleAndConsumableItemOrderByMaintenanceDateDesc(Vehicle vehicle,
            ConsumableItem consumableItem);
}
