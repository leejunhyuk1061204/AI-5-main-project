package kr.co.himedia.repository;

import kr.co.himedia.entity.CarModelMaster;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

import java.util.List;

public interface CarModelMasterRepository extends JpaRepository<CarModelMaster, Long> {

    @Query("SELECT DISTINCT c.manufacturer FROM CarModelMaster c ORDER BY c.manufacturer")
    List<String> findDistinctManufacturers();

    @Query("SELECT DISTINCT c.modelName FROM CarModelMaster c WHERE c.manufacturer = :manufacturer ORDER BY c.modelName")
    List<String> findDistinctModelNamesByManufacturer(String manufacturer);

    @Query("SELECT DISTINCT c.modelYear FROM CarModelMaster c WHERE c.manufacturer = :manufacturer AND c.modelName = :modelName ORDER BY c.modelYear DESC")
    List<Integer> findDistinctModelYears(String manufacturer, String modelName);

    @Query("SELECT DISTINCT c.fuelType FROM CarModelMaster c WHERE c.manufacturer = :manufacturer AND c.modelName = :modelName AND c.modelYear = :modelYear ORDER BY c.fuelType")
    List<String> findDistinctFuelTypes(String manufacturer, String modelName, Integer modelYear);

    List<CarModelMaster> findByManufacturerOrderByModelNameAscModelYearDesc(String manufacturer);
}
