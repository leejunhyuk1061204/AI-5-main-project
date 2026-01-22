package kr.co.himedia.repository;

import kr.co.himedia.entity.DiagResult;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.UUID;

@Repository
public interface DiagResultRepository extends JpaRepository<DiagResult, UUID> {
    java.util.Optional<DiagResult> findByDiagSessionId(UUID sessionId);
}
