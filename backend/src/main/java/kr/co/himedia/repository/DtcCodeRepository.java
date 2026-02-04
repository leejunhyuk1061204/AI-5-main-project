package kr.co.himedia.repository;

import kr.co.himedia.entity.DtcCode;
import kr.co.himedia.entity.DtcCodeId;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;

@Repository
public interface DtcCodeRepository extends JpaRepository<DtcCode, DtcCodeId> {

    // 특정 제조사 코드로 조회
    Optional<DtcCode> findByCodeAndManufacturer(String code, String manufacturer);

    // 제조사별 코드가 없을 경우 GENERIC(공용) 코드 조회용
    default Optional<DtcCode> findByCodeGeneric(String code) {
        return findByCodeAndManufacturer(code, "GENERIC");
    }
}
