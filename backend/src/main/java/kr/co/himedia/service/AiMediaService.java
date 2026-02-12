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
    public String uploadMedia(MultipartFile file, String folder) throws IOException {
        // null 또는 빈 파일이면 null 반환
        if (file == null || file.isEmpty()) {
            log.debug("No file provided for folder: {}", folder);
            return null;
        }

        String fileUrl = fileStorageService.uploadFile(file, folder);
        log.info("Media uploaded successfully [Folder: {}]: {}", folder, fileUrl);
        return fileUrl;
    }

    /**
     * 지정된 파일명으로 미디어 저장
     */
    public String storeMedia(MultipartFile file, String folder, String filename) throws IOException {
        if (file == null || file.isEmpty()) {
            return null;
        }
        String fileUrl = fileStorageService.storeFile(file, folder, filename);
        log.info("Media stored successfully [Folder: {}, Filename: {}]: {}", folder, filename, fileUrl);
        return fileUrl;
    }
}
