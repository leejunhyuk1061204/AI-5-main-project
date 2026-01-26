
# ai/app/services/engine_anomaly_service.py
"""
엔진룸 이상 정밀 분석 파이프라인 (Engine Anomaly Pipeline)

[파일 설명]
이 파일은 엔진룸 이미지를 분석하여 부품별 결함을 탐지하는 파이프라인입니다.
YOLO로 26종 부품을 감지하고, PatchCore로 이상을 탐지한 후, LLM으로 결함을 해석합니다.

[API 응답 형식]
{
  "status": "WARNING",
  "analysis_type": "SCENE_ENGINE",
  "category": "ENGINE_ROOM",
  "data": { vehicle_type, parts_detected, anomalies_found, results[] }
}
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

from ai.app.services.engine_yolo_service import run_yolo_inference
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
# Reliability Thresholds
# =============================================================================
FAST_PATH_THRESHOLD = 0.9  # 90% 확신할 때만 LLM 스킵

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
# validate_s3_url 제거 (visual_service에서 통합 관리)


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

    async def analyze(
        self, 
        s3_url: str, 
        image: Optional[Image.Image] = None,
        image_bytes: Optional[bytes] = None,
        yolo_model=None
    ) -> Dict[str, Any]:
        """
        엔진 이미지 분석 (메인 진입점)
        
        Args:
            s3_url: S3 URL (기존 인터페이스 유지 및 로깅용)
            image: 미리 로드된 PIL Image (중복 다운로드 방지)
            image_bytes: 미리 로드된 이미지 바이트 (중복 다운로드 방지)
            yolo_model: YOLO 모델
        """
        request_id = str(uuid.uuid4())[:8]
        
        # 1. 이미지 로드 (전달받은 이미지가 없으면 오류 - visual_service에서 미리 로드되어야 함)
        if image is None or image_bytes is None:
             # 하위 호환성 위해 로드 시도하되, 가급적 visual_service 사용 권장
             from ai.app.services.visual_service import _safe_load_image
             try:
                 image, image_bytes = await _safe_load_image(s3_url)
             except Exception as e:
                 return {"status": "ERROR", "message": f"Image load failed: {e}", "request_id": request_id}

        # 2. YOLO 추론
        yolo_result = await run_yolo_inference(s3_url, image=image, model=yolo_model)
        
        # =================================================================
        # Path B: YOLO가 부품을 감지하지 못한 경우
        # =================================================================
        if yolo_result.detected_count == 0:
            print(f"[Pipeline] Path B: No parts detected. LLM Fallback.")
            llm_result = await analyze_general_image(s3_url)
            
            # API 명세서 형식에 맞춤
            return {
                "status": llm_result.status if hasattr(llm_result, 'status') else "ERROR",
                "analysis_type": "SCENE_ENGINE",
                "category": "ENGINE_ROOM",
                "data": {
                    "vehicle_type": None,
                    "parts_detected": 0,
                    "anomalies_found": 0,
                    "results": [],
                    "llm_fallback": True,
                    "description": llm_result.description if hasattr(llm_result, 'description') else None,
                    "recommendation": llm_result.recommendation if hasattr(llm_result, 'recommendation') else None
                }
            }

        # =================================================================
        # Path A: 정밀 분석
        # =================================================================
        detected_labels = [d.label for d in yolo_result.detections]
        is_ev = any(part in EV_PARTS for part in detected_labels)
        vehicle_type = "EV" if is_ev else "ICE"
        
        # 부품 크롭
        crops = await crop_detected_parts(image_bytes, yolo_result.detections)
        
        # =================================================================
        # 각 부품별 분석 수행 (병렬 처리로 속도 향상)
        # =================================================================
        # [중요] s3_url을 각 부품 분석 함수에 전달해야 함
        # → Active Learning 시 S3에 라벨 데이터를 저장할 때 파일명 생성에 필요
        # =================================================================
        tasks = []
        for i, (part_name, (crop_img, bbox)) in enumerate(crops.items()):
            # YOLO confidence 전달
            conf = yolo_result.detections[i].confidence if i < len(yolo_result.detections) else 0.0
            tasks.append(
                # [수정] s3_url 파라미터 추가하여 Active Learning에서 파일 경로 생성 가능
                self._analyze_single_part(part_name, crop_img, bbox, conf, request_id, s3_url)
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

        # 최종 상태 결정: 이상이 있으면 WARNING, CRITICAL 판정
        final_status = "NORMAL"
        for res in results:
            if res.get("severity") == "CRITICAL":
                final_status = "CRITICAL"
                break
            elif res.get("is_anomaly") or res.get("severity") == "WARNING":
                final_status = "WARNING"
        
        # API 명세서 형식에 맞춤
        return {
            "status": final_status,
            "analysis_type": "SCENE_ENGINE",
            "category": "ENGINE_ROOM",
            "data": {
                "vehicle_type": vehicle_type,
                "parts_detected": len(results),
                "anomalies_found": anomaly_count,
                "results": results
            }
        }

    async def _analyze_single_part(
        self, 
        part_name: str, 
        crop_img: Image.Image, 
        bbox: List[int],
        confidence: float,
        request_id: str,
        s3_url: str  # [추가] Active Learning S3 저장 시 파일명 생성에 필요
    ) -> PartAnalysisResult:
        """
        단일 부품 이상 탐지
        
        [파라미터 설명]
        - s3_url: 원본 이미지의 S3 경로. Active Learning 시 라벨 JSON 저장 경로 생성에 사용.
                  예: s3://bucket/images/abc123.jpg → dataset/engine/llm_confirmed/abc123_Battery.json
        """
        async with SEMAPHORE:
            # Anomaly Detection
            anomaly_result = await self.anomaly_detector.detect(crop_img, part_name)
            
            heatmap_b64 = None
            
            if anomaly_result.is_anomaly:
                # [Dual-Check] 이상 발견 시 무조건 LLM 호출
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
                
                # [Active Learning] 엔진룸 이상탐지 정답(Oracle) S3 저장
                try:
                    import boto3
                    s3 = boto3.client('s3')
                    bucket = os.getenv("S3_BUCKET_NAME", "car-sentry-data")
                    # 부품별 고유 ID 생성 (이미지ID + 부품명)
                    file_id = os.path.basename(s3_url).split('.')[0]
                    label_key = f"dataset/engine/llm_confirmed/{file_id}_{part_name}.json"
                    
                    oracle_data = {
                        "domain": "engine",
                        "source_url": s3_url,
                        "part_name": part_name,
                        "bbox": bbox,
                        "labels": [{"class": part_name, "bbox": bbox}], # YOLO 재학습용
                        "anomaly_label": llm_res.get("defect_label"),   # Anomaly 분류 재학습용
                        "status": llm_res.get("severity")
                    }
                    
                    s3.put_object(
                        Bucket=bucket,
                        Key=label_key,
                        Body=json.dumps(oracle_data, ensure_ascii=False, indent=2),
                        ContentType='application/json'
                    )
                    print(f"[Active Learning] 엔진 부품 정답지 저장 완료: {label_key}")
                except Exception as e:
                    print(f"[Active Learning Engine] 저장 실패: {e}")

            else:
                # [Fast Path] 정상이고 확신도가 높으면(Score가 매우 낮으면) LLM 스킵
                # Confidence = 1.0 - (score / threshold) 로 근사치 계산
                normal_confidence = 1.0 - (anomaly_result.score / anomaly_result.threshold) if anomaly_result.threshold > 0 else 1.0
                
                if normal_confidence >= FAST_PATH_THRESHOLD:
                    print(f"[Engine] Fast Path 적용: {part_name} (Normal Confidence: {normal_confidence:.2f})")
                    llm_res = {
                        "defect_category": "NORMAL",
                        "defect_label": "Normal",
                        "description_ko": f"{part_name} 부품이 정상적인 상태입니다. 특별한 결함 징후가 발견되지 않았습니다.",
                        "severity": "NORMAL",
                        "recommended_action": "주기적인 육안 점검을 유지하십시오."
                    }
                else:
                    # 정상 범위지만 확신도가 낮으면 LLM 확인 (Dual-Check)
                    print(f"[Engine] 낮은 확신도 정상({normal_confidence:.2f}), LLM 확인 요청: {part_name}")
                    crop_b64 = self._image_to_base64(crop_img)
                    llm_res = await suggest_anomaly_label_with_base64(
                        crop_base64=crop_b64,
                        heatmap_base64=None, # 정상일 땐 히트맵 생략 가능
                        part_name=part_name,
                        anomaly_score=anomaly_result.score
                    )

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

    # _load_image_async 제거 (visual_service 피쳐 활용)

    def _image_to_base64(self, image: Image.Image, format: str = "PNG") -> str:
        """PIL Image를 Base64 문자열로 변환"""
        buffer = io.BytesIO()
        image.save(buffer, format=format)
        return base64.b64encode(buffer.getvalue()).decode('utf-8')

    async def close(self):
        """HTTP 클라이언트 종료 (필요시)"""
        pass
