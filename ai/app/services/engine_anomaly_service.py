# ai/app/services/engine_anomaly_service.py
"""
Engine Anomaly Detection Pipeline

[설계 원칙]
1. AI는 S3 URL만 받아서 추론 수행
2. 원본 이미지 관리는 서버에서 담당
3. AI는 결과(라벨, bbox, score)만 반환
4. 히트맵은 base64로 반환 (S3 업로드 안 함)

[보안]
- SSRF 방지: S3 도메인만 허용 (Allow-list)
- 비동기 I/O: httpx 사용 (Blocking 없음)
"""
import httpx
import uuid
import asyncio
import io
import base64
import filetype
import re
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import urlparse
from PIL import Image
from dataclasses import dataclass, asdict
import json
import os

from ai.app.services.yolo_service import run_yolo_inference
from ai.app.services.crop_service import crop_detected_parts
from ai.app.services.anomaly_service import AnomalyDetector
from ai.app.services.heatmap_service import generate_heatmap_overlay
from ai.app.services.llm_service import suggest_anomaly_label_with_base64, analyze_general_image
from ai.app.schemas.visual_schema import VisualResponse

# =============================================================================
# Configuration
# =============================================================================
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
IMAGE_PIXEL_LIMIT = 100_000_000   # 100M Pixels
Image.MAX_IMAGE_PIXELS = IMAGE_PIXEL_LIMIT

SEMAPHORE = asyncio.Semaphore(5)  # Concurrency Limit
HTTP_TIMEOUT = 30.0  # seconds

# =============================================================================
# SSRF 방지: 허용된 도메인 (Allow-list)
# =============================================================================
ALLOWED_DOMAINS = [
    r".*\.s3\.amazonaws\.com$",
    r".*\.s3\.ap-northeast-2\.amazonaws\.com$",
    r".*\.s3-ap-northeast-2\.amazonaws\.com$",
    r"s3\.amazonaws\.com$",
    r"s3\.ap-northeast-2\.amazonaws\.com$",
    # 필요시 추가
]

# EV Parts Definition
EV_PARTS = {
    "Inverter", "Electric_Motor", "Charging_Port", 
    "Inverter_Coolant_Reservoir", "Secondary_Coolant_Reservoir"
}

# =============================================================================
# Result Dataclass
# =============================================================================
@dataclass
class PartAnalysisResult:
    """단일 부품 분석 결과"""
    part_name: str
    bbox: List[int]
    confidence: float
    is_anomaly: bool
    anomaly_score: float
    threshold: float
    defect_label: str
    defect_category: str
    description: str
    severity: str
    recommended_action: str
    heatmap_base64: Optional[str] = None


# =============================================================================
# URL Validation (SSRF 방지)
# =============================================================================
def validate_s3_url(url: str) -> bool:
    """
    S3 URL 검증 (SSRF 방지)
    - 허용된 도메인만 통과
    - localhost, 메타데이터 URL 차단
    """
    try:
        parsed = urlparse(url)
        
        # HTTPS만 허용
        if parsed.scheme not in ['https', 'http']:
            return False
        
        hostname = parsed.hostname or ""
        
        # 차단 목록 (SSRF 공격 패턴)
        blocked_patterns = [
            r"localhost",
            r"127\.0\.0\.\d+",
            r"10\.\d+\.\d+\.\d+",
            r"172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+",
            r"192\.168\.\d+\.\d+",
            r"169\.254\.\d+\.\d+",  # AWS 메타데이터
            r"0\.0\.0\.0",
        ]
        
        for pattern in blocked_patterns:
            if re.match(pattern, hostname, re.IGNORECASE):
                print(f"[SSRF Block] Blocked URL: {url}")
                return False
        
        # 허용 목록 검사
        for allowed_pattern in ALLOWED_DOMAINS:
            if re.match(allowed_pattern, hostname, re.IGNORECASE):
                return True
        
        print(f"[SSRF Block] Domain not in allow-list: {hostname}")
        return False
        
    except Exception as e:
        print(f"[URL Validation Error] {e}")
        return False


# =============================================================================
# Main Pipeline
# =============================================================================
class EngineAnomalyPipeline:
    """
    엔진룸 이상 탐지 파이프라인
    - 비동기 I/O (httpx)
    - SSRF 방지 (URL 검증)
    - 결과는 JSON으로 반환 (S3 업로드 없음)
    """
    
    def __init__(self):
        self.anomaly_detector = AnomalyDetector()
        # 비동기 HTTP 클라이언트
        self.http_client = httpx.AsyncClient(timeout=HTTP_TIMEOUT)

    async def analyze(self, s3_url: str, yolo_model=None) -> Dict[str, Any]:
        """
        엔진 이미지 분석 (메인 진입점)
        """
        request_id = str(uuid.uuid4())[:8]
        
        # 0. SSRF 방지: URL 검증
        if not validate_s3_url(s3_url):
            return {
                "status": "ERROR", 
                "message": "Invalid URL: Only S3 URLs are allowed",
                "request_id": request_id
            }
        
        # 1. 이미지 로드 (비동기)
        try:
            image, image_bytes = await self._load_image_async(s3_url)
        except ValueError as e:
            return {"status": "ERROR", "message": str(e), "request_id": request_id}

        # 2. YOLO 추론
        yolo_result = await run_yolo_inference(s3_url, model=yolo_model)
        
        # =================================================================
        # Path B: YOLO가 부품을 감지하지 못한 경우
        # =================================================================
        if yolo_result.detected_count == 0:
            print(f"[Pipeline] Path B: No parts detected.")
            llm_result = await analyze_general_image(s3_url)
            
            return {
                "status": "SUCCESS",
                "request_id": request_id,
                "path": "B",
                "source_url": s3_url,
                "vehicle_type": None,
                "parts_detected": 0,
                "llm_analysis": llm_result.dict(),
                "is_hard_negative": llm_result.category == "ENGINE"
            }

        # =================================================================
        # Path A: 정밀 분석
        # =================================================================
        detected_labels = [d.label for d in yolo_result.detections]
        is_ev = any(part in EV_PARTS for part in detected_labels)
        vehicle_type = "EV" if is_ev else "ICE"
        
        # 부품 크롭
        crops = await crop_detected_parts(image_bytes, yolo_result.detections)
        
        # 각 부품별 분석 (병렬)
        tasks = []
        for i, (part_name, (crop_img, bbox)) in enumerate(crops.items()):
            # YOLO confidence 전달
            conf = yolo_result.detections[i].confidence if i < len(yolo_result.detections) else 0.0
            tasks.append(
                self._analyze_single_part(part_name, crop_img, bbox, conf, request_id)
            )
        
        part_results = await asyncio.gather(*tasks)
        
        # 결과 집계
        results = []
        anomaly_count = 0
        for res in part_results:
            if res:
                results.append(asdict(res))
                if res.is_anomaly:
                    anomaly_count += 1

        return {
            "status": "SUCCESS",
            "request_id": request_id,
            "path": "A",
            "source_url": s3_url,
            "vehicle_type": vehicle_type,
            "parts_detected": len(results),
            "anomalies_found": anomaly_count,
            "results": results
        }

    async def _analyze_single_part(
        self, 
        part_name: str, 
        crop_img: Image.Image, 
        bbox: List[int],
        confidence: float,
        request_id: str
    ) -> PartAnalysisResult:
        """단일 부품 이상 탐지"""
        async with SEMAPHORE:
            # Anomaly Detection
            anomaly_result = await self.anomaly_detector.detect(crop_img, part_name)
            
            heatmap_b64 = None
            
            if anomaly_result.is_anomaly:
                # 히트맵 생성
                heatmap_overlay = generate_heatmap_overlay(crop_img, anomaly_result.heatmap)
                
                # 이미지를 Base64로 변환
                crop_b64 = self._image_to_base64(crop_img)
                heatmap_b64 = self._image_to_base64(heatmap_overlay)
                
                # LLM에게 Base64로 직접 전달
                llm_res = await suggest_anomaly_label_with_base64(
                    crop_base64=crop_b64,
                    heatmap_base64=heatmap_b64,
                    part_name=part_name,
                    anomaly_score=anomaly_result.score
                )
            else:
                llm_res = {
                    "defect_category": "NORMAL",
                    "defect_label": "Normal",
                    "description_ko": "정상 상태입니다.",
                    "severity": "NORMAL",
                    "recommended_action": "조치 불필요"
                }

            return PartAnalysisResult(
                part_name=part_name,
                bbox=bbox,
                confidence=confidence,
                is_anomaly=anomaly_result.is_anomaly,
                anomaly_score=anomaly_result.score,
                threshold=anomaly_result.threshold,
                defect_label=llm_res.get("defect_label", "Unknown"),
                defect_category=llm_res.get("defect_category", "UNKNOWN"),
                description=llm_res.get("description_ko", ""),
                severity=llm_res.get("severity", "WARNING"),
                recommended_action=llm_res.get("recommended_action", ""),
                heatmap_base64=heatmap_b64
            )

    async def _load_image_async(self, url: str) -> Tuple[Image.Image, bytes]:
        """
        비동기로 S3 URL에서 이미지 로드
        """
        # HEAD 요청으로 크기 확인
        try:
            head_response = await self.http_client.head(url)
            content_length = int(head_response.headers.get('Content-Length', 0))
            if content_length > MAX_FILE_SIZE:
                raise ValueError(f"Image too large: {content_length} bytes")
        except httpx.RequestError as e:
            raise ValueError(f"Failed to check image: {e}")
        
        # GET 요청으로 이미지 다운로드
        try:
            response = await self.http_client.get(url)
            response.raise_for_status()
            content = response.content
        except httpx.RequestError as e:
            raise ValueError(f"Failed to download image: {e}")
        
        if len(content) > MAX_FILE_SIZE:
            raise ValueError(f"Image too large: {len(content)} bytes")
        
        # Magic Bytes 검증
        kind = filetype.guess(content)
        if kind is None or kind.mime not in ['image/jpeg', 'image/png']:
            raise ValueError(f"Invalid file type: {kind.mime if kind else 'Unknown'}")
        
        image = Image.open(io.BytesIO(content))
        return image, content

    def _image_to_base64(self, image: Image.Image, format: str = "PNG") -> str:
        """PIL Image를 Base64 문자열로 변환"""
        buffer = io.BytesIO()
        image.save(buffer, format=format)
        return base64.b64encode(buffer.getvalue()).decode('utf-8')

    async def close(self):
        """HTTP 클라이언트 종료"""
        await self.http_client.aclose()
