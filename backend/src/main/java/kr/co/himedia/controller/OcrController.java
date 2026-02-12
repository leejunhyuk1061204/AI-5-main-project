package kr.co.himedia.controller;

import kr.co.himedia.common.ApiResponse;
import kr.co.himedia.dto.maintenance.MaintenanceHistoryResponse;
import kr.co.himedia.dto.maintenance.OcrAnalysisResponse;
import kr.co.himedia.service.MaintenanceService;
import kr.co.himedia.service.ReceiptAnalyzerService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.UUID;

@RestController
@RequestMapping("/api/v1/ocr")
@RequiredArgsConstructor
public class OcrController {

    private final ReceiptAnalyzerService receiptAnalyzerService;
    private final MaintenanceService maintenanceService;

    /**
     * [BE-OCR-001] 영수증 지능형 분석
     * 사진을 업로드하면 Naver OCR과 OpenAI를 통해 정비 정보를 추출합니다.
     */
    @PostMapping("/analyze")
    public ApiResponse<OcrAnalysisResponse> analyzeReceipt(@RequestParam("file") MultipartFile file) {
        OcrAnalysisResponse response = receiptAnalyzerService.analyze(file);
        return ApiResponse.success(response);
    }

    /**
     * [BE-OCR-002] OCR 분석 + 정비 이력 저장 (원스톱)
     * 영수증 이미지를 분석하여 정비 이력을 저장하고, 소모품 상태를 자동으로 갱신합니다.
     * - 날짜가 없으면 오늘 날짜로 저장
     * - 주행거리가 없으면 차량의 현재 주행거리로 저장
     */
    @PostMapping("/{vehicleId}/analyze-save")
    public ApiResponse<MaintenanceHistoryResponse> analyzeAndSave(
            @PathVariable("vehicleId") UUID vehicleId,
            @RequestParam("file") MultipartFile file,
            @RequestParam(value = "manualData", required = false) String manualDataJson) {
        MaintenanceHistoryResponse response = maintenanceService.analyzeAndSave(vehicleId, file, manualDataJson);
        return ApiResponse.success(response);
    }
}
