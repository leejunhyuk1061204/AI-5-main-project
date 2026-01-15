package kr.co.himedia.controller;

import kr.co.himedia.common.ApiResponse;
import kr.co.himedia.dto.ai.DiagnosisRequestDto;
import kr.co.himedia.dto.ai.DtcDto;
import kr.co.himedia.service.AiDiagnosisService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/ai")
@RequiredArgsConstructor
public class AiController {

    private final AiDiagnosisService aiDiagnosisService;

    /**
     * DTC(고장 코드) 수신 및 처리 (BE-AI-002)
     */
    @PostMapping("/dtc")
    public ApiResponse<Void> receiveDtc(@RequestBody DtcDto dtcDto) {
        aiDiagnosisService.processDtc(dtcDto);
        return ApiResponse.success(null);
    }

    /**
     * AI 진단 요청 (BE-AI-001)
     * Vision (이미지) 또는 Audio (소리) 진단
     */
    @PostMapping("/diagnose")
    public ApiResponse<Object> requestDiagnosis(
            @RequestBody DiagnosisRequestDto requestDto) {
        Object result = aiDiagnosisService.requestDiagnosis(requestDto);
        return ApiResponse.success(result);
    }
}
