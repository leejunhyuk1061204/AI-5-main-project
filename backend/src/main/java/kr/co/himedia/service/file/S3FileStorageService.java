package kr.co.himedia.service.file;

import io.awspring.cloud.s3.S3Template;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.time.Duration;
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
    public String uploadFile(MultipartFile file, String folder) throws IOException {
        String fileName = folder + "/" + UUID.randomUUID().toString() + "_" + file.getOriginalFilename();

        try {
            // S3Template simplifies the upload process
            s3Template.upload(bucketName, fileName, file.getInputStream());

            // Generate a pre-signed URL valid for 1 hour
            String fileUrl = s3Template.createSignedGetURL(bucketName, fileName, Duration.ofHours(1)).toString();

            log.info("File uploaded to S3 and signed URL generated: {}", fileUrl);
            return fileUrl;
        } catch (Exception ex) {
            log.error("Error uploading to S3 or signing URL", ex);
            throw new IOException("Could not upload file to S3", ex);
        }
    }
}
