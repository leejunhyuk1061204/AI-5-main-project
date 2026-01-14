package kr.co.himedia.controller;

import kr.co.himedia.common.ApiResponse;
import kr.co.himedia.dto.master.CarModelDto;
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
}
