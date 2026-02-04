
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

from ai.app.services.visual.domains.engine.engine_yolo_service import run_yolo_inference
from ai.app.services.visual.yolo_utils import convert_xywh_to_xyxy
from ai.app.services.visual.utils.crop_service import crop_detected_parts
from ai.app.services.visual.domains.engine.anomaly_service import AnomalyDetector
from ai.app.services.visual.utils.heatmap_service import generate_heatmap_overlay
from ai.app.services.visual.utils.heatmap_service import generate_heatmap_overlay
from ai.app.services.common.llm_service import suggest_anomaly_label_with_base64, analyze_general_image
from ai.app.schemas.visual_schema import VisualResponse
from ai.app.services.common.active_learning_service import get_active_learning_policy

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
    "Inverter", "Charging_Port", 
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
    severity: str
    # description, recommended_action 삭제 (API 명세서와 일치)


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
    
    def __init__(self, anomaly_detector: Optional[AnomalyDetector] = None):
        if anomaly_detector:
            self.anomaly_detector = anomaly_detector
        else:
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
             from ai.app.services.visual.visual_service import _safe_load_image
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
            # [보정 로직] Router가 엔진룸으로 잘못 분류했지만 LLM이 계기판으로 판단한 경우
            if hasattr(llm_result, "category") and llm_result.category == "DASHBOARD":
                print("[Engine Pipeline] 💡 Router Miss detected! Redirecting to Dashboard analysis...")
                from ai.app.services.visual.domains.dashboard_service import analyze_dashboard_image
                return await analyze_dashboard_image(image, s3_url, yolo_model=None)
            
            # [NEW] 만약 상태가 WARNING/CRITICAL인데 results가 비어있다면, LLM에게 강제로 라벨링을 요청
            fallback_results = []
            status = llm_result.status if hasattr(llm_result, 'status') else "ERROR"
            
            if status in ["WARNING", "CRITICAL"]:
                print(f"[Engine] YOLO Miss detected (Status: {status}). Requesting LLM Labeling...")
                from ai.app.services.common.llm_service import generate_training_labels
                label_result = await generate_training_labels(s3_url, "engine")
                
                for lbl in label_result.get("labels", []):
                    # LLM 라벨을 PartAnalysisResult (dict) 포맷으로 변환
                    fallback_results.append({
                        "part_name": lbl.get("class", "Unknown"),
                        "bbox": lbl.get("bbox", [0,0,0,0]),
                        "confidence": 0.9,
                        "is_anomaly": True,
                        "anomaly_score": 1.0,
                        "threshold": 0.5,
                        "defect_label": "Anomaly(LLM)",
                        "defect_category": "UNKNOWN",
                        "severity": status,
                        "heatmap_base64": None
                    })

            return {
                "status": status,
                "analysis_type": "SCENE_ENGINE",
                "category": "ENGINE_ROOM",
                "data": {
                    "vehicle_type": None,
                    "parts_detected": len(fallback_results),
                    "anomalies_found": len([r for r in fallback_results if r["is_anomaly"]]),
                    "results": fallback_results,
                    "llm_fallback": True
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
            final_is_anomaly = anomaly_result.is_anomaly  # [Fix] Track final decision
            
            heatmap_b64 = None
            
            if anomaly_result.is_anomaly:
                # [Dual-Check] 이상 발견 시 무조건 LLM 호출
                heatmap_b64 = None
                try:
                    # 히트맵 생성 (PatchCore 학습 전이면 에러가 날 수 있으므로 예외 처리)
                    if anomaly_result.heatmap is not None:
                        heatmap_overlay = generate_heatmap_overlay(crop_img, anomaly_result.heatmap)
                        heatmap_b64 = self._image_to_base64(heatmap_overlay)
                except Exception as e:
                    print(f"[Engine Warning] Heatmap generation failed (Model might be untrained): {e}")
                    heatmap_b64 = None
                
                # 이미지를 Base64로 변환
                crop_b64 = self._image_to_base64(crop_img)
                
                # LLM에게 Base64 + Heatmap(Optional) + BBox 정보 전달 (Robust Hybrid)
                llm_res = await suggest_anomaly_label_with_base64(
                    crop_base64=crop_b64,
                    heatmap_base64=heatmap_b64, # 있으면 사용, 없으면 None
                    bbox=bbox,                  # BBox는 항상 사용
                    part_name=part_name,
                    anomaly_score=anomaly_result.score
                )

                # [수정] Dual-Check: Anomaly Detector가 이상을 감지했더라도, 
                # LLM이 정밀 분석 후 "정상(NORMAL)"이라고 판단하면 이를 존중합니다. (False Positive 방지)
                # PatchCore는 민감하게 반응할 수 있으므로, LLM의 의미론적 판단을 최종 결과로 사용합니다.
                # 단, LLM이 연결되지 않아 "Local/Mock" 모드로 동작 중일 때는 PatchCore 결과를 유지해야 합니다.
                # [Fix] 명시적인 'is_mock' 필드 우선 사용, 없으면 문자열 체크 (하위 호환)
                is_mock_analysis = llm_res.get("is_mock", "분석 모드)" in llm_res.get("description_ko", ""))
                
                if (llm_res.get("defect_category") == "NORMAL" or llm_res.get("severity") == "NORMAL") and not is_mock_analysis:
                     print(f"[Engine] Anomaly Detector flagged issue, but LLM classified as NORMAL. Trusting LLM.")
                     final_is_anomaly = False  # [중요] LLM이 정상이라고 판단하면, 최종 결과도 "정상(False)"으로 덮어씁니다.
                else:
                     # LLM도 이상 동의 시, 또는 LLM이 Mock 모드일 때는 PatchCore의 감지 결과(True)를 그대로 유지합니다.
                     pass
                
                # [Active Learning] 엔진룸 이상탐지 정답(Oracle) S3 저장 (Filter Applied)
                policy = get_active_learning_policy()
                should_save = policy.should_collect(
                    status=llm_res.get("severity", "WARNING"),
                    confidence=confidence, # YOLO Confidence
                    labels=[llm_res.get("defect_label")],
                    is_llm_fallback=True
                )

                if should_save:
                    try:
                        import boto3
                        s3 = boto3.client('s3')
                        bucket = os.getenv("S3_BUCKET_NAME", "car-sentry-data")
                        # 부품별 고유 ID 생성 (이미지ID + 부품명)
                        # 파일 ID 추출: s3_url이 base64인 경우 처리
                        if s3_url.startswith("data:"):
                            import hashlib
                            file_id = hashlib.md5(s3_url.encode()).hexdigest()[:10]
                        else:
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
                    print(f"[Active Learning] Skip saving {part_name} - Policy Rejected (Normal or Low Quality)")

            else:
                # [Fast Path] 정상이고 확신도가 높으면(Score가 매우 낮으면) LLM 스킵
                # Confidence = 1.0 - (score / threshold) 로 근사치 계산
                normal_confidence = 1.0 - (anomaly_result.score / anomaly_result.threshold) if anomaly_result.threshold > 0 else 1.0
                
                if normal_confidence >= FAST_PATH_THRESHOLD:
                    print(f"[Engine] Fast Path 적용: {part_name} (Normal Confidence: {normal_confidence:.2f})")
                    llm_res = {
                        "defect_category": "NORMAL",
                        "defect_label": "Normal",
                        "severity": "NORMAL"
                    }
                else:
                    # 정상 범위지만 확신도가 낮으면 LLM 확인 (Dual-Check)
                    print(f"[Engine] 낮은 확신도 정상({normal_confidence:.2f}), LLM 확인 요청: {part_name}")
                    crop_b64 = self._image_to_base64(crop_img)
                    llm_res = await suggest_anomaly_label_with_base64(
                        crop_base64=crop_b64,
                        heatmap_base64=None, # 정상일 땐 히트맵 생략 가능
                        bbox=bbox,           # BBox는 항상 사용
                        part_name=part_name,
                        anomaly_score=anomaly_result.score
                    )

            # [Consistency Enforce] 최종 판정이 정상이면, 결함 필드는 '정상'으로 통일
            if not final_is_anomaly:
                llm_res["defect_category"] = "NORMAL"
                llm_res["defect_label"] = "NORMAL"
                llm_res["severity"] = "NORMAL"

            return PartAnalysisResult(
                part_name=part_name,
                bbox=convert_xywh_to_xyxy(bbox),
                confidence=confidence,
                is_anomaly=final_is_anomaly,  # [Fix] Use final decision
                anomaly_score=anomaly_result.score,
                threshold=anomaly_result.threshold,
                defect_label=llm_res.get("defect_label", "Unknown"),
                defect_category=llm_res.get("defect_category", "UNKNOWN"),
                severity=llm_res.get("severity", "WARNING")
                # description, recommended_action 삭제 (API 명세서와 일치)
            )

    # _load_image_async 제거 (visual_service 피쳐 활용)

    def _image_to_base64(self, image: Image.Image, format: str = "JPEG") -> str:
        """PIL Image를 Base64 문자열로 변환 (RGB 변환 및 JPEG 포합 보장)"""
        buffer = io.BytesIO()
        # RGBA 등을 RGB로 변환 (OpenAI JPEG 호환성)
        if image.mode != "RGB":
            image = image.convert("RGB")
        image.save(buffer, format=format, quality=85)
        return base64.b64encode(buffer.getvalue()).decode('utf-8')

    async def close(self):
        """HTTP 클라이언트 종료 (필요시)"""
        pass
