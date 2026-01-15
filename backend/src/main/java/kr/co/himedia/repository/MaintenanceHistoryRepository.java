package kr.co.himedia.repository;

import kr.co.himedia.entity.MaintenanceHistory;
import kr.co.himedia.entity.Vehicle;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.UUID;

@Repository
public interface MaintenanceHistoryRepository extends JpaRepository<MaintenanceHistory, UUID> {
    List<MaintenanceHistory> findByVehicleOrderByMaintenanceDateDesc(Vehicle vehicle);
}
