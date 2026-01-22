package kr.co.himedia.repository;

import kr.co.himedia.entity.AiEvidence;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.UUID;

@Repository
public interface AiEvidenceRepository extends JpaRepository<AiEvidence, UUID> {
    List<AiEvidence> findByDiagSessionId(UUID diagSessionId);
}
