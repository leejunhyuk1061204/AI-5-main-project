package kr.co.himedia.repository;

import kr.co.himedia.entity.ObdDeviceVehicleHistory;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Repository
public interface ObdDeviceVehicleHistoryRepository extends JpaRepository<ObdDeviceVehicleHistory, UUID> {

    @Query("SELECT h FROM ObdDeviceVehicleHistory h WHERE h.obdDeviceId = :deviceId ORDER BY h.lastConnectedAt DESC")
    List<ObdDeviceVehicleHistory> findByObdDeviceIdOrderByLastConnectedAtDesc(@Param("deviceId") UUID deviceId);

    Optional<ObdDeviceVehicleHistory> findTopByObdDeviceIdOrderByLastConnectedAtDesc(UUID deviceId);

    Optional<ObdDeviceVehicleHistory> findByObdDeviceIdAndCalidAndCvn(UUID obdDeviceId, String calid, String cvn);

    Optional<ObdDeviceVehicleHistory> findByObdDeviceIdAndVehiclesId(UUID obdDeviceId, UUID vehiclesId);

    @Query("SELECT h FROM ObdDeviceVehicleHistory h WHERE h.obdDeviceId = :deviceId AND h.calid IS NOT NULL AND h.calid = :calid ORDER BY h.lastConnectedAt DESC")
    List<ObdDeviceVehicleHistory> findAllByObdDeviceIdAndCalid(@Param("deviceId") UUID deviceId, @Param("calid") String calid);

    @Query("SELECT h FROM ObdDeviceVehicleHistory h WHERE h.obdDeviceId = :deviceId AND h.cvn IS NOT NULL AND h.cvn = :cvn ORDER BY h.lastConnectedAt DESC")
    List<ObdDeviceVehicleHistory> findAllByObdDeviceIdAndCvn(@Param("deviceId") UUID deviceId, @Param("cvn") String cvn);
}
