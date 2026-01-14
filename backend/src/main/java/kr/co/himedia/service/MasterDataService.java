package kr.co.himedia.service;

import kr.co.himedia.dto.master.CarModelDto;
import kr.co.himedia.entity.CarModelMaster;
import kr.co.himedia.repository.CarModelMasterRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class MasterDataService {

    private final CarModelMasterRepository carModelMasterRepository;

    public List<String> getManufacturers() {
        return carModelMasterRepository.findDistinctManufacturers();
    }

    public List<CarModelDto> getModelsByManufacturer(String manufacturer) {
        List<CarModelMaster> models = carModelMasterRepository
                .findByManufacturerOrderByModelNameAscModelYearDesc(manufacturer);

        return models.stream()
                .map(m -> new CarModelDto(m.getModelName(), m.getModelYear(), m.getFuelType()))
                .collect(Collectors.toList());
    }
}
