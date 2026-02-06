package kr.co.himedia.repository;

import kr.co.himedia.entity.DtcFreezeFrame;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.UUID;

public interface DtcFreezeFrameRepository extends JpaRepository<DtcFreezeFrame, UUID> {
}
