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
    String uploadFile(MultipartFile file, String folder) throws IOException;

    /**
     * 파일을 지정된 이름으로 업로드하고 접근 가능한 URL을 반환
     *
     * @param file     업로드할 파일
     * @param folder   저장할 폴더
     * @param filename 저장할 파일 이름 (확장자 포함)
     * @return 접근 가능한 파일 URL
     * @throws IOException 입출력 예외 발생 시
     */
    String storeFile(MultipartFile file, String folder, String filename) throws IOException;

    /**
     * 파일을 다운로드하여 바이트 배열로 반환
     *
     * @param folder   파일이 저장된 폴더
     * @param filename 다운로드할 파일 이름
     * @return 파일의 바이트 배열
     * @throws IOException 입출력 예외 발생 시
     */
    byte[] downloadFile(String folder, String filename) throws IOException;
}
