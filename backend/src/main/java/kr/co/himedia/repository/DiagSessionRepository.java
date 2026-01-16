package kr.co.himedia.repository;

import kr.co.himedia.entity.DiagSession;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.UUID;

@Repository
public interface DiagSessionRepository extends JpaRepository<DiagSession, UUID> {
}
