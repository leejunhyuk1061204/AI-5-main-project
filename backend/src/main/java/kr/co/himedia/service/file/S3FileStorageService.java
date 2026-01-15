package kr.co.himedia.service.file;

import io.awspring.cloud.s3.S3Template;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.util.UUID;

/**
 * AWS S3를 사용하는 저장소 구현체
 * app.storage.type=s3 일 때 빈으로 등록됨
 */
@Slf4j
@Service
@RequiredArgsConstructor
@ConditionalOnProperty(prefix = "app.storage", name = "type", havingValue = "s3")
public class S3FileStorageService implements FileStorageService {

    private final S3Template s3Template;

    @Value("${spring.cloud.aws.s3.bucket:car-sentry-bucket}")
    private String bucketName;

    @Override
    public String uploadFile(MultipartFile file) throws IOException {
        String fileName = "uploads/" + UUID.randomUUID().toString() + "_" + file.getOriginalFilename();

        try {
            // S3Template simplifies the upload process
            var resource = s3Template.upload(bucketName, fileName, file.getInputStream());
            String fileUrl = resource.getURL().toString();

            log.info("File uploaded to S3: {}", fileUrl);
            return fileUrl;
        } catch (Exception ex) {
            log.error("Error uploading to S3", ex);
            throw new IOException("Could not upload file to S3", ex);
        }
    }
}
