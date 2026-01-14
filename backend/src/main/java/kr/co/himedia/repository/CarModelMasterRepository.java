package kr.co.himedia.repository;

import kr.co.himedia.entity.CarModelMaster;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

import java.util.List;

public interface CarModelMasterRepository extends JpaRepository<CarModelMaster, Long> {

    @Query("SELECT DISTINCT c.manufacturer FROM CarModelMaster c ORDER BY c.manufacturer")
    List<String> findDistinctManufacturers();

    List<CarModelMaster> findByManufacturerOrderByModelNameAscModelYearDesc(String manufacturer);
}
