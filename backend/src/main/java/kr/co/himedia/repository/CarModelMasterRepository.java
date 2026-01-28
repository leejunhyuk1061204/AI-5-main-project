package kr.co.himedia.repository;

import kr.co.himedia.entity.CarModelMaster;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

import org.springframework.data.repository.query.Param;

import java.util.List;

public interface CarModelMasterRepository extends JpaRepository<CarModelMaster, Long> {

    @Query("SELECT DISTINCT c.manufacturer FROM CarModelMaster c ORDER BY c.manufacturer")
    List<String> findDistinctManufacturers();

    @Query("SELECT DISTINCT c.modelName FROM CarModelMaster c WHERE c.manufacturer = :manufacturer ORDER BY c.modelName")
    List<String> findDistinctModelNamesByManufacturer(@Param("manufacturer") String manufacturer);

    @Query("SELECT DISTINCT c.modelYear FROM CarModelMaster c WHERE c.manufacturer = :manufacturer AND c.modelName = :modelName ORDER BY c.modelYear DESC")
    List<Integer> findDistinctModelYears(@Param("manufacturer") String manufacturer,
            @Param("modelName") String modelName);

    @Query("SELECT DISTINCT c.fuelType FROM CarModelMaster c WHERE c.manufacturer = :manufacturer AND c.modelName = :modelName AND c.modelYear = :modelYear ORDER BY c.fuelType")
    List<String> findDistinctFuelTypes(@Param("manufacturer") String manufacturer, @Param("modelName") String modelName,
            @Param("modelYear") Integer modelYear);

    List<CarModelMaster> findByManufacturerOrderByModelNameAscModelYearDesc(String manufacturer);
}
