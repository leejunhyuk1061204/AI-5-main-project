package kr.co.himedia.repository;

import kr.co.himedia.entity.DtcHistory;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.UUID;

public interface DtcHistoryRepository extends JpaRepository<DtcHistory, UUID> {
}
