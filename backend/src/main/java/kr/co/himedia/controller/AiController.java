package kr.co.himedia.controller;

import kr.co.himedia.common.ApiResponse;

import kr.co.himedia.dto.ai.DtcDto;
import kr.co.himedia.dto.ai.UnifiedDiagnosisRequestDto;
import kr.co.himedia.service.AiDiagnosisService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

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
     * 통합 진단 요청 (BE-AI-005)
     * 소리, 사진, LSTM 분석 결과를 통합하여 최종 진단 요청
     * Trigger 2: 수동 진단 (파일 업로드 지원)
     */
    @PostMapping(value = "/diagnose/unified", consumes = org.springframework.http.MediaType.MULTIPART_FORM_DATA_VALUE)
    public ApiResponse<Object> requestUnifiedDiagnosis(
            @RequestPart(value = "image", required = false) org.springframework.web.multipart.MultipartFile image,
            @RequestPart(value = "audio", required = false) org.springframework.web.multipart.MultipartFile audio,
            @RequestPart(value = "data") UnifiedDiagnosisRequestDto requestDto) {
        Object result = aiDiagnosisService.requestUnifiedDiagnosis(requestDto, image, audio);
        return ApiResponse.success(result);
    }
}
