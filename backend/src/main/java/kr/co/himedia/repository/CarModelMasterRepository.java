package kr.co.himedia.repository;

import kr.co.himedia.entity.CarModelMaster;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.Optional;

public interface CarModelMasterRepository extends JpaRepository<CarModelMaster, Long> {

        @Query("SELECT DISTINCT c.manufacturerKo FROM CarModelMaster c ORDER BY c.manufacturerKo")
        List<String> findDistinctManufacturers();

        @Query("SELECT DISTINCT c.modelNameKo FROM CarModelMaster c WHERE c.manufacturerKo = :manufacturer ORDER BY c.modelNameKo")
        List<String> findDistinctModelNamesByManufacturer(@Param("manufacturer") String manufacturer);

        @Query("SELECT DISTINCT c.modelYear FROM CarModelMaster c WHERE c.manufacturerKo = :manufacturer AND c.modelNameKo = :modelName ORDER BY c.modelYear DESC")
        List<Integer> findDistinctModelYears(@Param("manufacturer") String manufacturer,
                        @Param("modelName") String modelName);

        @Query("SELECT DISTINCT c.fuelType FROM CarModelMaster c WHERE c.manufacturerKo = :manufacturer AND c.modelNameKo = :modelName AND c.modelYear = :modelYear ORDER BY c.fuelType")
        List<String> findDistinctFuelTypes(@Param("manufacturer") String manufacturer,
                        @Param("modelName") String modelName,
                        @Param("modelYear") Integer modelYear);

        List<CarModelMaster> findByManufacturerKoOrderByModelNameKoAscModelYearDesc(String manufacturer);

        Optional<CarModelMaster> findOneByManufacturerKoAndModelNameKoAndModelYearAndFuelType(
                        String manufacturerKo, String modelNameKo, Integer modelYear, String fuelType);
}
