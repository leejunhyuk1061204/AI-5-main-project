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

    /**
     * [BE-VH-003] 모델 목록 조회
     * 특정 제조사의 차량 모델 및 연식 정보를 반환합니다.
     */
    @GetMapping("/models")
    public ResponseEntity<ApiResponse<List<CarModelDto>>> getModels(
            @RequestParam("manufacturer") String manufacturer) {
        List<CarModelDto> models = masterDataService.getModelsByManufacturer(manufacturer);
        return ResponseEntity.ok(ApiResponse.success(models));
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
