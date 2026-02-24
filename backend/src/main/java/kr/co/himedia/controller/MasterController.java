package kr.co.himedia.controller;

import kr.co.himedia.common.ApiResponse;
import kr.co.himedia.dto.master.CarModelDto;
import kr.co.himedia.dto.master.ConsumableItemDto;
import kr.co.himedia.service.MasterDataService;
import kr.co.himedia.service.file.FileStorageService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.core.io.Resource;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import javax.imageio.ImageIO;
import java.awt.Graphics2D;
import java.awt.RenderingHints;
import java.awt.image.BufferedImage;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.util.List;
import java.util.UUID;

@Slf4j
@RestController
@RequestMapping("/api/v1/master")
@RequiredArgsConstructor
public class MasterController {

    private final MasterDataService masterDataService;
    private final List<FileStorageService> fileStorageServices;

    /**
     * [BE-VH-003] 제조사 목록 조회
     */
    @GetMapping("/manufacturers")
    public ResponseEntity<ApiResponse<List<String>>> getManufacturers() {
        log.info("Request manufacturers list");
        List<String> manufacturers = masterDataService.getManufacturers();
        return ResponseEntity.ok(ApiResponse.success(manufacturers));
    }

    @GetMapping("/models")
    public ResponseEntity<ApiResponse<List<CarModelDto>>> getModels(
            @RequestParam("manufacturer") String manufacturer) {
        log.info("Request models list for manufacturer: {}", manufacturer);
        List<CarModelDto> models = masterDataService.getModelsByManufacturer(manufacturer);
        return ResponseEntity.ok(ApiResponse.success(models));
    }

    /**
     * [BE-VH-003] 고유 모델명 목록 조회
     */
    @GetMapping("/models/names")
    public ResponseEntity<ApiResponse<List<String>>> getModelNames(
            @RequestParam("manufacturer") String manufacturer) {
        List<String> names = masterDataService.getModelNamesByManufacturer(manufacturer);
        return ResponseEntity.ok(ApiResponse.success(names));
    }

    /**
     * [BE-VH-003] 모델별 연식 목록 조회
     */
    @GetMapping("/models/years")
    public ResponseEntity<ApiResponse<List<Integer>>> getModelYears(
            @RequestParam("manufacturer") String manufacturer,
            @RequestParam("modelName") String modelName) {
        List<Integer> years = masterDataService.getModelYears(manufacturer, modelName);
        return ResponseEntity.ok(ApiResponse.success(years));
    }

    /**
     * [BE-VH-003] 모델별 연료 타입 목록 조회
     */
    @GetMapping("/models/fuels")
    public ResponseEntity<ApiResponse<List<String>>> getFuelTypes(
            @RequestParam("manufacturer") String manufacturer,
            @RequestParam("modelName") String modelName,
            @RequestParam("modelYear") Integer modelYear) {
        List<String> fuels = masterDataService.getFuelTypes(manufacturer, modelName, modelYear);
        return ResponseEntity.ok(ApiResponse.success(fuels));
    }

    /**
     * [BE-VH-003] 소모품 목록 조회
     */
    @GetMapping("/consumables")
    public ResponseEntity<ApiResponse<List<ConsumableItemDto>>> getConsumables() {
        List<ConsumableItemDto> consumables = masterDataService.getAllConsumables();
        return ResponseEntity.ok(ApiResponse.success(consumables));
    }

    /**
     * [BE-RECEIPT-001] 영수증 이미지 조회
     */
    @GetMapping("/receipts/{receiptId}")
    public ResponseEntity<Resource> getReceiptImage(@PathVariable UUID receiptId) {
        try {
            String filename = receiptId.toString() + ".jpg";
            log.info("@@@@@@@@@@ Fetching receipt image from storage. Available services: {}",
                    fileStorageServices.stream().map(s -> s.getClass().getSimpleName()).toList());

            // 모든 가용한 StorageService를 시도 (S3 -> Local 순으로 탐색)
            byte[] imageData = null;
            for (FileStorageService service : fileStorageServices) {
                try {
                    log.info("@@@@@@@@@@ Trying storage service: {}", service.getClass().getSimpleName());
                    imageData = service.downloadFile("receipts", filename);
                    if (imageData != null && imageData.length > 0) {
                        log.info("@@@@@@@@@@ Successfully found file in: {}", service.getClass().getSimpleName());
                        break;
                    }
                } catch (Exception e) {
                    log.warn("@@@@@@@@@@ Failed to find file in {}: {}", service.getClass().getSimpleName(),
                            e.getMessage());
                }
            }

            if (imageData == null || imageData.length == 0) {
                log.error("@@@@@@@@@@ Image data not found in any storage for: {}", filename);
                return ResponseEntity.notFound().build();
            }

            // 고해상도 이미지 리사이징 (모바일 렌더링 최적화)
            byte[] processedData = resizeImageIfNeeded(imageData, 1200);

            // 바이트 배열을 Resource로 변환
            Resource resource = new ByteArrayResource(processedData);

            log.info("@@@@@@@@@@ Successfully retrieved receipt image: {} (Original: {} bytes, Processed: {} bytes)",
                    receiptId, imageData.length, processedData.length);

            return ResponseEntity.ok()
                    .contentType(MediaType.IMAGE_JPEG)
                    .contentLength(processedData.length)
                    .header(HttpHeaders.CACHE_CONTROL, "max-age=3600")
                    .body(resource);

        } catch (Exception e) {
            log.error("Unexpected error while retrieving receipt image: {}", receiptId, e);
            return ResponseEntity.internalServerError().build();
        }
    }

    /**
     * 이미지 크기가 큰 경우 리사이징 수행
     */
    private byte[] resizeImageIfNeeded(byte[] imageData, int maxWidth) {
        try {
            log.info("@@@@@@@@@@ Attempting to resize image. Original size: {} bytes", imageData.length);
            BufferedImage originalImage = ImageIO.read(new ByteArrayInputStream(imageData));
            if (originalImage == null) {
                log.warn("@@@@@@@@@@ ImageIO.read returned null. Image format might not be supported.");
                return imageData;
            }

            int width = originalImage.getWidth();
            int height = originalImage.getHeight();
            log.info("@@@@@@@@@@ Original image dimensions: {}x{}", width, height);

            // 이미 폭이 좁으면 그대로 반환
            if (width <= maxWidth) {
                log.info("@@@@@@@@@@ Image width {} is smaller than maxWidth {}. Skipping resize.", width, maxWidth);
                return imageData;
            }

            // 비율 유지하며 리사이징
            int newWidth = maxWidth;
            int newHeight = (height * maxWidth) / width;
            log.info("@@@@@@@@@@ Resizing to: {}x{}", newWidth, newHeight);

            BufferedImage resizedImage = new BufferedImage(newWidth, newHeight, BufferedImage.TYPE_INT_RGB);
            Graphics2D g = resizedImage.createGraphics();

            // 품질 우선 설정
            g.setRenderingHint(RenderingHints.KEY_INTERPOLATION, RenderingHints.VALUE_INTERPOLATION_BILINEAR);
            g.setRenderingHint(RenderingHints.KEY_RENDERING, RenderingHints.VALUE_RENDER_QUALITY);
            g.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);

            g.drawImage(originalImage, 0, 0, newWidth, newHeight, null);
            g.dispose();

            ByteArrayOutputStream baos = new ByteArrayOutputStream();
            ImageIO.write(resizedImage, "jpeg", baos);
            byte[] processed = baos.toByteArray();
            log.info("@@@@@@@@@@ Resize successful. New size: {} bytes", processed.length);
            return processed;

        } catch (Exception e) {
            log.warn("@@@@@@@@@@ Failed to resize image, returning original: {}", e.getMessage(), e);
            return imageData;
        }
    }

    /**
     * 테스트 엔드포인트
     */
    @GetMapping("/hello")
    public ResponseEntity<String> hello() {
        log.info("MasterController hello test");
        return ResponseEntity.ok("MasterController is ALIVE");
    }
}
