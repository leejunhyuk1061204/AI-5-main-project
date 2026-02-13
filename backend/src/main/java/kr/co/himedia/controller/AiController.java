package kr.co.himedia.controller;

import kr.co.himedia.common.ApiResponse;

import kr.co.himedia.dto.ai.DtcDto;
import kr.co.himedia.dto.ai.DtcBatchRequest;
import kr.co.himedia.dto.ai.UnifiedDiagnosisRequestDto;
import kr.co.himedia.dto.ai.DiagnosisResponseDto;
import kr.co.himedia.service.AiDiagnosisService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import java.util.UUID;

@Slf4j
@RestController
@RequestMapping("/api/v1/ai")
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
     * 통합 DTC 배치 수신
     * Mode 03(DTC) + Mode 02(Freeze Frame) 통합 처리
     */
    @PostMapping("/dtc/batch")
    public ApiResponse<Void> receiveDtcBatch(@RequestBody DtcBatchRequest request) {
        log.info("[DTC Batch] 수신 - 차량: {}, 코드 수: {}", request.getVehicleId(), request.getDtcs().size());
        aiDiagnosisService.processDtcBatch(request);
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
            @RequestPart(value = "data") UnifiedDiagnosisRequestDto requestDto,
            @RequestParam(value = "diagType", defaultValue = "DATA") String diagTypeStr) {

        kr.co.himedia.entity.DiagSession.DiagTriggerType diagType;
        try {
            diagType = kr.co.himedia.entity.DiagSession.DiagTriggerType.valueOf(diagTypeStr.toUpperCase());
        } catch (IllegalArgumentException e) {
            diagType = kr.co.himedia.entity.DiagSession.DiagTriggerType.DATA;
        }

        Object result = aiDiagnosisService.requestUnifiedDiagnosis(requestDto, image, audio, diagType);
        return ApiResponse.success(result);
    }

    /**
     * 진단 결과 조회 (BE-AI-006)
     */
    @GetMapping("/diagnose/session/{sessionId}")
    public ApiResponse<DiagnosisResponseDto> getDiagnosisResult(@PathVariable("sessionId") UUID sessionId) {
        return ApiResponse.success(aiDiagnosisService.getDiagnosisResult(sessionId));
    }

    /**
     * 차량별 진단 목록 조회 (BE-AI-007)
     */
    @GetMapping("/diagnose/list")
    public ApiResponse<java.util.List<kr.co.himedia.dto.ai.DiagnosisListItemDto>> getDiagnosisList(
            @RequestParam("vehicleId") UUID vehicleId) {
        return ApiResponse.success(aiDiagnosisService.getDiagnosisList(vehicleId));
    }

    /**
     * INTERACTIVE 모드 사용자 답변 전송 (BE-AI-008)
     * 데이터 부족 시 AI와 대화형으로 추가 정보를 수집하기 위한 엔드포인트
     */
    @PostMapping(value = "/diagnose/session/{sessionId}/reply", consumes = org.springframework.http.MediaType.MULTIPART_FORM_DATA_VALUE)
    public ApiResponse<Object> replyToSession(
            @PathVariable("sessionId") UUID sessionId,
            @RequestPart(value = "image", required = false) org.springframework.web.multipart.MultipartFile image,
            @RequestPart(value = "audio", required = false) org.springframework.web.multipart.MultipartFile audio,
            @RequestPart(value = "data", required = false) kr.co.himedia.dto.ai.ReplyRequestDto replyDto) {
        return ApiResponse.success(aiDiagnosisService.replyToSession(sessionId, replyDto, image, audio));
    }

    /**
     * 진단 진행상황 SSE 구독 (BE-AI-009)
     */
    @GetMapping(value = "/diagnose/session/{sessionId}/sse", produces = org.springframework.http.MediaType.TEXT_EVENT_STREAM_VALUE)
    public org.springframework.web.servlet.mvc.method.annotation.SseEmitter subscribe(
            @PathVariable("sessionId") UUID sessionId) {
        return aiDiagnosisService.subscribe(sessionId);
    }
}
