package kr.co.himedia.service.file;

import org.springframework.web.multipart.MultipartFile;
import java.io.IOException;

/**
 * 파일 저장소 서비스를 위한 인터페이스
 * Local 또는 S3 등 다양한 저장소 전략을 추상화
 */
public interface FileStorageService {
    /**
     * 파일을 업로드하고 접근 가능한 URL을 반환
     * 
     * @param file 업로드할 파일
     * @return 접근 가능한 파일 URL
     * @throws IOException 입출력 예외 발생 시
     */
    String uploadFile(MultipartFile file) throws IOException;
}
