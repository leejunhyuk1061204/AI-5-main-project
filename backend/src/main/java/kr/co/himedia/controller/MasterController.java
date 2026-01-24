package kr.co.himedia.controller;

import kr.co.himedia.common.ApiResponse;
import kr.co.himedia.dto.master.CarModelDto;
import kr.co.himedia.dto.master.ConsumableItemDto;
import kr.co.himedia.service.MasterDataService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/master")
@RequiredArgsConstructor
public class MasterController {

    private final MasterDataService masterDataService;

    /**
     * [BE-VH-003] 제조사 목록 조회
     * 시스템에 등록된 모든 차량 제조사 목록을 반환합니다.
     */
    @GetMapping("/manufacturers")
    public ResponseEntity<ApiResponse<List<String>>> getManufacturers() {
        List<String> manufacturers = masterDataService.getManufacturers();
        return ResponseEntity.ok(ApiResponse.success(manufacturers));
    }

    @GetMapping("/models")
    public ResponseEntity<ApiResponse<List<CarModelDto>>> getModels(
            @RequestParam("manufacturer") String manufacturer) {
        List<CarModelDto> models = masterDataService.getModelsByManufacturer(manufacturer);
        return ResponseEntity.ok(ApiResponse.success(models));
    }

    /**
     * [BE-VH-003] 고유 모델명 목록 조회
     * 특정 제조사의 중복 없는 모델명 목록을 반환합니다.
     */
    @GetMapping("/models/names")
    public ResponseEntity<ApiResponse<List<String>>> getModelNames(
            @RequestParam("manufacturer") String manufacturer) {
        List<String> names = masterDataService.getModelNamesByManufacturer(manufacturer);
        return ResponseEntity.ok(ApiResponse.success(names));
    }

    /**
     * [BE-VH-003] 모델별 연식 목록 조회
     * 특정 제조사 및 모델명의 중복 없는 연식 목록을 반환합니다.
     */
    @GetMapping("/models/years")
    public ResponseEntity<ApiResponse<List<Integer>>> getModelYears(
            @RequestParam("manufacturer") String manufacturer,
            @RequestParam("modelName") String modelName) {
        List<Integer> years = masterDataService.getModelYears(manufacturer, modelName);
        return ResponseEntity.ok(ApiResponse.success(years));
    }

    /**
     * [BE-VH-003] 모델별 연료 타입 목록 조회
     * 특정 제조사, 모델명, 연식에 따른 가용한 연료 타입 목록을 반환합니다.
     */
    @GetMapping("/models/fuels")
    public ResponseEntity<ApiResponse<List<String>>> getFuelTypes(
            @RequestParam("manufacturer") String manufacturer,
            @RequestParam("modelName") String modelName,
            @RequestParam("modelYear") Integer modelYear) {
        List<String> fuels = masterDataService.getFuelTypes(manufacturer, modelName, modelYear);
        return ResponseEntity.ok(ApiResponse.success(fuels));
    }

    /**
     * [BE-VH-003] 소모품 목록 조회
     * 시스템에 등록된 모든 소모품 마스터 정보를 반환합니다.
     */
    @GetMapping("/consumables")
    public ResponseEntity<ApiResponse<List<ConsumableItemDto>>> getConsumables() {
        List<ConsumableItemDto> consumables = masterDataService.getAllConsumables();
        return ResponseEntity.ok(ApiResponse.success(consumables));
    }
}
