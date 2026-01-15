package kr.co.himedia.repository;

import kr.co.himedia.entity.MaintenanceHistory;
import kr.co.himedia.entity.Vehicle;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface MaintenanceHistoryRepository extends JpaRepository<MaintenanceHistory, Long> {
    List<MaintenanceHistory> findByVehicleOrderByMaintenanceDateDesc(Vehicle vehicle);
}
