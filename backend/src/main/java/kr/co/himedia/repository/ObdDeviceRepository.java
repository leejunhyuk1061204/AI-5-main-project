package kr.co.himedia.repository;

import kr.co.himedia.entity.ObdDevice;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Repository
public interface ObdDeviceRepository extends JpaRepository<ObdDevice, UUID> {

    List<ObdDevice> findByUserIdOrderByUpdatedAtDesc(UUID userId);

    Optional<ObdDevice> findByUserIdAndDeviceId(UUID userId, String deviceId);

    boolean existsByUserIdAndDeviceId(UUID userId, String deviceId);
}
