package kr.co.himedia.service;

import com.google.cloud.vision.v1.*;
import com.google.protobuf.ByteString;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;
import kr.co.himedia.common.exception.BaseException;
import kr.co.himedia.common.exception.ErrorCode;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;

@Service
public class OcrService {

    /**
     * 이미지에서 텍스트 추출 (Google Vision API)
     */
    public String extractTextFromImage(MultipartFile file) {
        try (ImageAnnotatorClient vision = ImageAnnotatorClient.create()) {
            // 이미지 바이트 변환
            ByteString imgBytes = ByteString.copyFrom(file.getBytes());

            // 이미지 생성
            Image img = Image.newBuilder().setContent(imgBytes).build();

            // 텍스트 감지 요청 생성
            Feature feat = Feature.newBuilder().setType(Feature.Type.TEXT_DETECTION).build();
            AnnotateImageRequest request = AnnotateImageRequest.newBuilder()
                    .addFeatures(feat)
                    .setImage(img)
                    .build();

            List<AnnotateImageRequest> requests = new ArrayList<>();
            requests.add(request);

            // API 호출
            BatchAnnotateImagesResponse response = vision.batchAnnotateImages(requests);
            List<AnnotateImageResponse> responses = response.getResponsesList();

            StringBuilder sb = new StringBuilder();

            for (AnnotateImageResponse res : responses) {
                if (res.hasError()) {
                    System.err.printf("Error: %s\n", res.getError().getMessage());
                    throw new BaseException(ErrorCode.INTERNAL_SERVER_ERROR,
                            "OCR analysis failed: " + res.getError().getMessage());
                }

                // 전체 텍스트 (첫 번째 annotation이 전체 텍스트임)
                if (!res.getTextAnnotationsList().isEmpty()) {
                    sb.append(res.getTextAnnotationsList().get(0).getDescription());
                }
            }

            return sb.toString();

        } catch (IOException e) {
            throw new BaseException(ErrorCode.INTERNAL_SERVER_ERROR, "Failed to process image file");
        } catch (Exception e) {
            throw new BaseException(ErrorCode.INTERNAL_SERVER_ERROR, "Vision API error: " + e.getMessage());
        }
    }

    /**
     * OCR 텍스트에서 주요 정보 파싱 (Regex)
     */
    public kr.co.himedia.dto.maintenance.MaintenanceReceiptResponse parseReceiptData(String text) {
        String shopName = null;
        java.time.LocalDate date = java.time.LocalDate.now(); // 못 찾으면 오늘 날짜
        Integer cost = 0;
        String detectedItem = "UNKNOWN";

        String[] lines = text.split("\n");

        // 1. 상호명 (보통 첫 줄에 위치)
        if (lines.length > 0) {
            shopName = lines[0].trim();
        }

        // 2. 날짜 (YYYY-MM-DD, YYYY/MM/DD, YYYY년 MM월 DD일 등 간단 매칭)
        // 실제로는 더 정교한 Regex 필요
        java.util.regex.Pattern datePattern = java.util.regex.Pattern
                .compile("\\d{4}[-/.년]\\s?\\d{1,2}[-/.월]\\s?\\d{1,2}");
        java.util.regex.Matcher dateMatcher = datePattern.matcher(text);
        if (dateMatcher.find()) {
            // 날짜 파싱 로직은 복잡하므로 일단 문자열만 찾고 스킵 (실무에선 DateTimeFormatter 필요)
            // 여기선 현재 날짜 그대로 둠
        }

        // 3. 금액 (마지막 줄 근처 숫자 or '합계' 키워드 뒤)
        // 단순히 숫자 중 가장 큰 값을 찾거나 '합계' 뒤의 숫자를 찾음
        java.util.regex.Pattern costPattern = java.util.regex.Pattern.compile("[0-9,]+원?");
        for (String line : lines) {
            if (line.contains("합계") || line.contains("총액") || line.contains("결제 금액")) {
                java.util.regex.Matcher m = costPattern.matcher(line);
                while (m.find()) {
                    String numStr = m.group().replaceAll("[^0-9]", "");
                    if (!numStr.isEmpty()) {
                        try {
                            int val = Integer.parseInt(numStr);
                            if (val > cost)
                                cost = val;
                        } catch (NumberFormatException ignored) {
                        }
                    }
                }
            }
        }

        // 못 찾았으면 전체 텍스트에서 가장 큰 숫자 (위험하지만 임시)
        if (cost == 0) {
            java.util.regex.Matcher m = costPattern.matcher(text);
            while (m.find()) {
                String numStr = m.group().replaceAll("[^0-9]", "");
                if (!numStr.isEmpty()) {
                    try {
                        int val = Integer.parseInt(numStr);
                        // 1억 이상은 제외 (전화번호일 확률)
                        if (val > cost && val < 100000000)
                            cost = val;
                    } catch (NumberFormatException ignored) {
                    }
                }
            }
        }

        // 4. 항목 추론 (단순 키워드)
        if (text.contains("타이어"))
            detectedItem = "TIRES";
        else if (text.contains("엔진오일") || text.contains("오일"))
            detectedItem = "ENGINE_OIL";
        else if (text.contains("패드") || text.contains("라이닝"))
            detectedItem = "BRAKE_PADS";
        else if (text.contains("와이퍼"))
            detectedItem = "WIPER";

        return kr.co.himedia.dto.maintenance.MaintenanceReceiptResponse.builder()
                .ocrText(text)
                .shopName(shopName)
                .date(date)
                .cost(cost)
                .detectedItem(detectedItem)
                .build();
    }
}
