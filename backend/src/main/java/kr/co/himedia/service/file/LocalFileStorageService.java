package kr.co.himedia.service.file;

import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.servlet.support.ServletUriComponentsBuilder;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;
import java.util.UUID;

/**
 * 로컬 파일 시스템을 사용하는 저장소 구현체
 * FileStorageService의 기본 구현체
 */
@Slf4j
@Service
public class LocalFileStorageService implements FileStorageService {

    private final Path fileStorageLocation;

    public LocalFileStorageService() {
        this.fileStorageLocation = Paths.get("uploads").toAbsolutePath().normalize();
        try {
            Files.createDirectories(this.fileStorageLocation);
        } catch (Exception ex) {
            throw new RuntimeException("Could not create the directory where the uploaded files will be stored.", ex);
        }
    }

    @Override
    public String uploadFile(MultipartFile file, String folder) throws IOException {
        String fileName = UUID.randomUUID().toString() + "_" + file.getOriginalFilename();
        try {
            Path folderPath = this.fileStorageLocation.resolve(folder);
            Files.createDirectories(folderPath);
            Path targetLocation = folderPath.resolve(fileName);

            Files.copy(file.getInputStream(), targetLocation, StandardCopyOption.REPLACE_EXISTING);

            String fileDownloadUri = ServletUriComponentsBuilder.fromCurrentContextPath()
                    .path("/api/v1/uploads/") // WebConfig의 매핑과 일치시켜야 함
                    .path(folder + "/")
                    .path(fileName)
                    .toUriString();

            log.info("File uploaded locally: {}", targetLocation);
            return fileDownloadUri;
        } catch (IOException ex) {
            log.error("Could not store file {}. Error: {}", fileName, ex.getMessage());
            throw new IOException("Could not store file " + fileName + ". Please try again!", ex);
        }
    }

    @Override
    public String storeFile(MultipartFile file, String folder, String filename) throws IOException {
        try {
            Path folderPath = this.fileStorageLocation.resolve(folder);
            Files.createDirectories(folderPath); // 폴더가 없으면 생성

            // 파일 확장자가 없는 경우 원본 확장자 사용 (선택 사항)
            // 여기서는 filename이 확장자를 포함한다고 가정
            Path targetLocation = folderPath.resolve(filename);

            Files.copy(file.getInputStream(), targetLocation, StandardCopyOption.REPLACE_EXISTING);

            String fileDownloadUri = ServletUriComponentsBuilder.fromCurrentContextPath()
                    .path("/api/v1/uploads/")
                    .path(folder + "/")
                    .path(filename)
                    .toUriString();

            log.info("File stored locally: {}", targetLocation);
            return fileDownloadUri;
        } catch (IOException ex) {
            log.error("Could not store file {}. Error: {}", filename, ex.getMessage());
            throw new IOException("Could not store file " + filename + ". Please try again!", ex);
        }
    }

    @Override
    public byte[] downloadFile(String folder, String filename) throws IOException {
        try {
            Path folderPath = this.fileStorageLocation.resolve(folder);
            Path filePath = folderPath.resolve(filename);

            log.info("Downloading file from local storage: {}", filePath);

            if (!Files.exists(filePath)) {
                log.error("File not found: {}", filePath);
                throw new IOException("File not found: " + filename);
            }

            byte[] data = Files.readAllBytes(filePath);
            log.info("Successfully downloaded file from local storage: {} ({} bytes)", filePath, data.length);
            return data;
        } catch (IOException ex) {
            log.error("Error downloading file from local storage: {}/{}", folder, filename, ex);
            throw new IOException("Could not download file: " + filename, ex);
        }
    }
}
