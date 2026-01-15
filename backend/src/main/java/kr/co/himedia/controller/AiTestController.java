package kr.co.himedia.controller;

import kr.co.himedia.common.ApiResponse;
import kr.co.himedia.service.KnowledgeService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * AI 기능 수동 테스트를 위한 컨트롤러 (임시)
 */
@RestController
@RequestMapping("/ai/test")
@RequiredArgsConstructor
public class AiTestController {

    private final KnowledgeService knowledgeService;

    /**
     * RAG 검색 테스트 (BE-AI-005 기반)
     * query 파라미터를 받아 벡터 변환 후 DB 유사도 검색 결과를 반환합니다.
     */
    @GetMapping("/knowledge/search")
    public ApiResponse<List<String>> testSearch(@RequestParam String query) {
        List<String> results = knowledgeService.searchKnowledge(query, 3);
        return ApiResponse.success(results);
    }
}
