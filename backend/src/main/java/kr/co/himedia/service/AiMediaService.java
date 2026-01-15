package kr.co.himedia.service;

import kr.co.himedia.service.file.FileStorageService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;
import java.io.IOException;

/**
 * 미디어 처리 서비스
 * FileStorageService 전략(Local/S3)에 따라 파일 업로드를 수행
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AiMediaService {

    private final FileStorageService fileStorageService;

    /**
     * 미디어 파일 업로드 및 URL 반환
     */
    public String uploadMedia(MultipartFile file) throws IOException {
        String fileUrl = fileStorageService.uploadFile(file);
        log.info("Media uploaded successfully: {}", fileUrl);
        return fileUrl;
    }
}
