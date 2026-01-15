package kr.co.himedia.controller;

import kr.co.himedia.common.ApiResponse;
import kr.co.himedia.service.AiMediaService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import java.io.IOException;
import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/media")
@RequiredArgsConstructor
public class MediaController {

    private final AiMediaService aiMediaService;

    /**
     * 미디어 파일 업로드 (BE-AI-003)
     * 앱에서 이미지/오디오를 업로드하면 저장 후 URL 반환
     */
    @PostMapping("/upload")
    public ApiResponse<Map<String, String>> uploadMedia(@RequestParam("file") MultipartFile file) throws IOException {
        String mediaUrl = aiMediaService.uploadMedia(file);

        Map<String, String> data = new HashMap<>();
        data.put("mediaUrl", mediaUrl);
        data.put("fileType", file.getContentType());

        return ApiResponse.success(data);
    }
}
