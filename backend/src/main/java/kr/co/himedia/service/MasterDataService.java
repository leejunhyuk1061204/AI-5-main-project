package kr.co.himedia.service;

import kr.co.himedia.dto.master.CarModelDto;
import kr.co.himedia.dto.master.ConsumableItemDto;
import kr.co.himedia.entity.CarModelMaster;
import kr.co.himedia.repository.CarModelMasterRepository;
import kr.co.himedia.repository.ConsumableItemRepository;
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
    private final ConsumableItemRepository consumableItemRepository;

    // 모든 소모품 목록 조회
    public List<ConsumableItemDto> getAllConsumables() {
        return consumableItemRepository.findAll().stream()
                .map(item -> new ConsumableItemDto(
                        item.getId(),
                        item.getCode(),
                        item.getName(),
                        item.getDescription(),
                        item.getDefaultIntervalMileage(),
                        item.getDefaultIntervalMonths()))
                .collect(Collectors.toList());
    }

    // 제조사 목록 조회 (중복 제거)
    public List<String> getManufacturers() {
        return carModelMasterRepository.findDistinctManufacturers();
    }

    // 제조사별 차량 모델 목록 조회 (연식 내림차순 정렬)
    public List<CarModelDto> getModelsByManufacturer(String manufacturer) {
        List<CarModelMaster> models = carModelMasterRepository
                .findByManufacturerOrderByModelNameAscModelYearDesc(manufacturer);

        return models.stream()
                .map(m -> new CarModelDto(m.getModelName(), m.getModelYear(), m.getFuelType()))
                .collect(Collectors.toList());
    }
}
