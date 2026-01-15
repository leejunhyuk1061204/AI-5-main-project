package kr.co.himedia.repository;

import kr.co.himedia.entity.ObdLog;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface ObdLogRepository extends JpaRepository<ObdLog, ObdLog.ObdLogId> {
    void deleteByTimeBefore(java.time.OffsetDateTime time);
}
