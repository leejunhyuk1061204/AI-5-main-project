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

    // 제조사별 고유 모델명 목록 조회 (오름차순 정렬)
    public List<String> getModelNamesByManufacturer(String manufacturer) {
        return carModelMasterRepository.findDistinctModelNamesByManufacturer(manufacturer);
    }

    // 특정 모델의 고유 연식 목록 조회 (내림차순 정렬)
    public List<Integer> getModelYears(String manufacturer, String modelName) {
        return carModelMasterRepository.findDistinctModelYears(manufacturer, modelName);
    }

    // 특정 차량 모델/연식의 가용한 연료 타입 목록 조회
    public List<String> getFuelTypes(String manufacturer, String modelName, Integer modelYear) {
        return carModelMasterRepository.findDistinctFuelTypes(manufacturer, modelName, modelYear);
    }

    // 제조사별 차량 모델 상세 목록 조회 (연식 내림차순 정렬)
    public List<CarModelDto> getModelsByManufacturer(String manufacturer) {
        List<CarModelMaster> models = carModelMasterRepository
                .findByManufacturerOrderByModelNameAscModelYearDesc(manufacturer);

        return models.stream()
                .map(m -> new CarModelDto(m.getModelName(), m.getModelYear(), m.getFuelType()))
                .collect(Collectors.toList());
    }
}
