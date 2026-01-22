package kr.co.himedia.repository;

import kr.co.himedia.entity.DiagSession;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.UUID;

import kr.co.himedia.entity.DiagSession.DiagStatus;
import kr.co.himedia.entity.DiagSession.DiagTriggerType;
import java.util.Optional;

@Repository
public interface DiagSessionRepository extends JpaRepository<DiagSession, UUID> {

    /** 차량의 특정 상태+트리거 타입 세션 조회 (UPDATE용) */
    Optional<DiagSession> findFirstByVehiclesIdAndTriggerTypeAndStatusOrderByCreatedAtDesc(
            UUID vehiclesId, DiagTriggerType triggerType, DiagStatus status);

    /** 차량별 진단 세션 목록 조회 (최신순) */
    java.util.List<DiagSession> findByVehiclesIdOrderByCreatedAtDesc(UUID vehiclesId);
}
