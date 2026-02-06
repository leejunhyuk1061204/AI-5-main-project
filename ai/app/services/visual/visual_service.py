# ai/app/services/visual_service.py
"""
통합 시각 분석 서비스 (Visual Orchestrator)

[파일 설명]
이 파일은 시각 분석 API의 진입점입니다.
Router로 장면을 분류(ENGINE/DASHBOARD/EXTERIOR/TIRE)하고,
각 도메인 전용 파이프라인으로 분석을 위임합니다.

[API 응답 형식 - 모든 장면 공통]
{
  "status": "NORMAL | WARNING | CRITICAL | ERROR",
  "analysis_type": "SCENE_ENGINE | SCENE_DASHBOARD | SCENE_EXTERIOR | SCENE_TIRE",
  "category": "ENGINE_ROOM | DASHBOARD | EXTERIOR | TIRE",
  "data": { ... 장면별 상세 데이터 ... }
}
"""
import os
from typing import Dict, Any, Optional, Tuple, List
import httpx
import io
import re
import base64
from PIL import Image
from urllib.parse import urlparse
import numpy as np
import cv2

from ai.app.services.visual.router_service import RouterService, SceneType, get_router_service
from ai.app.services.common.llm_service import analyze_general_image, generate_training_labels
from ai.app.services.common.llm_guard import validate_llm_label_result, sanitize_confidence
from ai.app.services.visual.domains.dashboard_service import analyze_dashboard_image
from ai.app.services.visual.domains.exterior_service import analyze_exterior_image
from ai.app.services.visual.domains.tire_service import analyze_tire_image

# =============================================================================
# SSRF 방지: 허용된 도메인 (Allow-list)
# =============================================================================
ALLOWED_DOMAINS = [
    r".*\.s3\.amazonaws\.com$",
    r".*\.s3\.ap-northeast-2\.amazonaws\.com$",
    r".*\.s3-ap-northeast-2\.amazonaws\.com$",
    r"s3\.amazonaws\.com$",
    r"s3\.ap-northeast-2\.amazonaws\.com$",
]

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def check_image_quality(image: Image.Image) -> List[str]:
    """
    이미지 품질 문제 감지
    
    Args:
        image: PIL Image 객체
    
    Returns:
        품질 문제 리스트 (예: ["TOO_DARK", "BLURRY"])
    """
    issues = []
    img_array = np.array(image)
    
    # 1. 밝기 체크
    if len(img_array.shape) == 3:  # RGB
        brightness = np.mean(img_array)
    else:  # Grayscale
        brightness = np.mean(img_array)
    
    if brightness < 50:
        issues.append("TOO_DARK")
    elif brightness > 200:
        issues.append("TOO_BRIGHT")
    
    # 2. 흐림 체크 (Laplacian variance)
    gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY) if len(img_array.shape) == 3 else img_array
    blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
    
    if blur_score < 100:
        issues.append("BLURRY")
    
    return issues


async def _safe_load_image(url: str) -> Tuple[Image.Image, bytes, List[str]]:
    """
    S3 URL 이미지를 안전하게 로드
    1. SSRF 방지 (URL 검증)
    2. 중복 다운로드 방지 (한 번만 다운로드하여 반환)
    3. 이미지 품질 검증 (밝기, 흐림 체크)
    """
    # 0. Data URL 처리 (테스트용 base64)
    if url.startswith("data:"):
        try:
            # data:image/jpeg;base64,xxxx
            header, encoded = url.split(",", 1)
            content = base64.b64decode(encoded)
            image = Image.open(io.BytesIO(content)).convert("RGB")
            quality_warnings = check_image_quality(image)
            return image, content, quality_warnings
        except Exception as e:
            raise ValueError(f"Invalid Data URL format: {e}")

    # 1. SSRF 검증 (S3 URL 전용)
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        
        # 차단 목록 (SSRF 공격 패턴)
        blocked_patterns = [
            r"localhost", r"127\.0\.0\.\d+", r"10\.\d+\.\d+\.\d+",
            r"172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+", r"192\.168\.\d+\.\d+",
            r"169\.254\.\d+\.\d+", r"0\.0\.0\.0",
        ]
        
        for pattern in blocked_patterns:
            if re.match(pattern, hostname, re.IGNORECASE):
                raise ValueError(f"Blocked URL domain: {hostname}")
        
        # 허용 도메인 체크
        is_allowed = False
        for allowed_pattern in ALLOWED_DOMAINS:
            if re.match(allowed_pattern, hostname, re.IGNORECASE):
                is_allowed = True
                break
        
        if not is_allowed:
            # 로컬 파일 경로인 경우(학습/테스트 context)는 통과하도록 설계 가능하지만, 
            # 여기서는 S3 URL 전용이므로 domain이 없는 경우는 block
            if not hostname:
                raise ValueError("Host not found in URL")
            # print(f"[Safe Load] Warning: Domain not in allow-list ({hostname}), proceeding with caution")
    
    except Exception as e:
        raise ValueError(f"URL Validation Error: {e}")

    # 2. 이미지 다운로드
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            content = response.content
            
            if len(content) > MAX_FILE_SIZE:
                raise ValueError("Image too large")
                
            image = Image.open(io.BytesIO(content)).convert("RGB")
            
            # 3. 품질 검증
            quality_warnings = check_image_quality(image)
            
            return image, content, quality_warnings
            
        except Exception as e:
            raise ValueError(f"Failed to load image from URL: {e}")


async def get_smart_visual_diagnosis(
    s3_url: str, 
    models: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    통합 시각 분석: Router → 전문 파이프라인
    
    Args:
        s3_url: S3 이미지 URL
        models: 모델 딕셔너리
            - router: RouterService
            - engine_yolo: Engine YOLO 모델
            - dashboard_yolo: Dashboard YOLO 모델
            - exterior_yolo: Exterior Unified YOLO 모델 (22종)
            - tire_yolo: Tire YOLO 모델
    
    Returns:
        {"type": "SCENE_*", "content": VisualResponse}
    """
    if models is None:
        models = {}
    
    # Step 0: 이미지 안전 로드 (전처리)
    try:
        image, image_bytes, quality_warnings = await _safe_load_image(s3_url)
    except Exception as e:
        print(f"[Visual Service] 이미지 로드 실패: {e}")
        return {
            "status": "ERROR",
            "analysis_type": "IO_ERROR",
            "category": "ERROR",
            "data": {"message": str(e)}
        }

    # Step 1: Router로 장면 분류
    # [Optimization] 이미 로드된 모델 우선 재사용
    router = models.get("router")
    if not router:
        # models에 없으면 싱글톤/캐시된 인스턴스 가져오기 시도
        router = get_router_service()
    
    try:
        scene_type, confidence = await router.classify(image)
        print(f"[Visual Service] Router 분류: {scene_type.value} (신뢰도: {confidence:.2f})")
        
        # 신뢰도가 낮으면 LLM에게 직접 판단 요청 (Fallback)
        if confidence < 0.4:
            print(f"[Visual Fallback] Router 결과: {scene_type.value} (신뢰도: {confidence:.2f}) -> LLM으로 전환 요청")
            # [Fix] llm_result 먼저 생성 (NameError 방지)
            llm_result = await analyze_general_image(s3_url)
            print(f"[Visual Fallback] LLM 응답: {llm_result}")
            
            # Map LLM result to VisualResponse (llm_result is VisualResponse object)
            # IRRELEVANT 처리 -> SCENE_ETC로 통합하되 Status로 구분
            if llm_result.category == "IRRELEVANT":
                 return {
                    "status": "ERROR",
                    "analysis_type": "SCENE_ETC",
                    "category": "IRRELEVANT",
                    "data": llm_result.data
                }

            # Mapping sub_type (category) to SceneType string
            sub_type = llm_result.category
            mapped_type = f"SCENE_{sub_type}" if sub_type in ["DASHBOARD", "EXTERIOR", "TIRE", "ENGINE"] else "SCENE_ETC"
            
            # [Fix] Standardize Response Format (Schema Mapping)
            standardized_data = llm_result.data
            
            # Additional: Generate BBoxes if domain allows
            llm_detections = []
            if sub_type in ["ENGINE", "DASHBOARD", "EXTERIOR", "TIRE"]:
                try:
                    print(f"[Visual Service] LLM Fallback: Requesting BBox for {sub_type}...")
                    label_result = await generate_training_labels(s3_url, sub_type.lower())
                    
                    # [Guard] Validate LLM Result
                    if not validate_llm_label_result(label_result):
                        print(f"[Visual Fallback] LLM BBox 생성 실패 또는 유효하지 않음: {label_result}")
                        # Skip processing, llm_detections remains []
                    else:
                        print(f"[Visual Fallback] LLM BBox 생성 결과: {label_result}")
                        for lbl in label_result.get("labels", []):
                            # [Sanitize] Add source check
                            lbl = sanitize_confidence(lbl)
                            
                            # BBox Conversion: Ratio ([x1, y1, x2, y2]) -> Pixel ([x, y, w, h])
                            raw_bbox = lbl.get("bbox", [0, 0, 0, 0])
                            pixel_bbox = [0, 0, 0, 0]
                            if image and len(raw_bbox) == 4:
                                from ai.app.services.visual.yolo_utils import normalize_to_xywh
                                pixel_bbox = normalize_to_xywh(raw_bbox, image.width, image.height)

                            # Domain-specific mapping
                            if sub_type == "ENGINE":
                                llm_detections.append({
                                    "part_name": lbl.get("part", "Unknown").replace(" ", "_"),
                                    "bbox": pixel_bbox,
                                    "is_anomaly": True,
                                    "anomaly_score": 0.5,
                                    "threshold": 0.5,
                                    "defect_label": lbl.get("damage", "Anomaly").replace(" ", "_"),
                                    "severity": "WARNING",
                                    "description": "AI 정밀 분석으로 식별된 부품입니다."
                                })
                            elif sub_type == "DASHBOARD":
                                llm_detections.append({
                                    "label": lbl.get("part", "Unknown").replace(" ", "_"),
                                    "color_severity": "YELLOW",
                                    "confidence": 0.9,
                                    "bbox": pixel_bbox,
                                    "is_blinking": None,
                                    "meaning": lbl.get("damage", "Warning").replace(" ", "_")
                                })
                            elif sub_type == "EXTERIOR":
                                llm_detections.append({
                                    "part": lbl.get("part", "Unknown").replace(" ", "_"), 
                                    "damage_type": lbl.get("damage", "Damage").replace(" ", "_"),
                                    "severity": "WARNING",
                                    "confidence": 0.9,
                                    "bbox": pixel_bbox
                                })
                            elif sub_type == "TIRE":
                                pass
                except Exception as e:
                    print(f"[Visual Service] LLM BBox Gen Error: {e}")

            # Ensure all labels use underscores
            for det in llm_detections:
                for key in ["part_name", "label", "part", "damage_type", "defect_label", "meaning"]:
                    if key in det and isinstance(det[key], str):
                        det[key] = det[key].replace(" ", "_").replace("(", "_").replace(")", "")

            # [Logic] analysis_status 결정
            # - 기본적으로 LLM Fallback은 'PARTIAL' (YOLO 미사용)로 볼 수도 있으나, 
            # - BBox를 성공적으로 찾았거나(detections > 0), 
            # - 애초에 문제가 없다고 판단된 경우(damage_found=False / normal)는 'SUCCESS'로 표기 가능.
            # - "손상 있음(damage=True)인데 박스 없음(detections=0)"인 경우만 'PARTIAL' (사용자 요청 사항)
            
            status_val = "SUCCESS"
            has_damage = (llm_result.status != "NORMAL")
            has_detections = (len(llm_detections) > 0)
            
            if has_damage and not has_detections:
                status_val = "PARTIAL"

            if sub_type == "ENGINE":
                standardized_data = {
                    "analysis_status": status_val,
                    "vehicle_type": "UNKNOWN",
                    "parts_detected": len(llm_detections),
                    "anomalies_found": len(llm_detections),
                    "results": llm_detections 
                }
            elif sub_type == "DASHBOARD":
                standardized_data = {
                    "analysis_status": status_val,
                    "vehicle_context": {"inferred_model": None, "dashboard_type": None},
                    "detected_count": len(llm_detections),
                    "detections": llm_detections
                }
            elif sub_type == "EXTERIOR":
                standardized_data = {
                    "analysis_status": status_val,
                    "damage_found": (llm_result.status != "NORMAL") or (len(llm_detections) > 0),
                    "detections": llm_detections
                }
            elif sub_type == "TIRE":
                standardized_data = {
                    "analysis_status": status_val,
                    "wear_status": "UNKNOWN",
                    "wear_level_pct": None,
                    "critical_issues": [],
                    "is_replacement_needed": False
                }

            return {
                "status": llm_result.status,
                "analysis_type": mapped_type,
                "category": sub_type,
                "data": standardized_data
            }
            
    except Exception as e:
        print(f"[Visual Service] Router 실패, LLM Fallback: {e}")
        llm_result = await analyze_general_image(s3_url)
        return llm_result
    
    # Step 2: 장면별 분기
    result_data = None
    try:
        if scene_type == SceneType.SCENE_ENGINE:
            # ENGINE: 기존 EngineAnomalyPipeline 사용
            from ai.app.services.visual.domains.engine.engine_anomaly_service import EngineAnomalyPipeline
            from ai.app.services.visual.domains.engine.anomaly_detector_service import get_anomaly_detector_service
            
            # ENGINE: YOLO (부품 탐지) → PatchCore (이상 탐지) → LLM (결함 해석)
            engine_yolo = models.get("engine_yolo")
            anomaly_detector = models.get("anomaly_detector") or get_anomaly_detector_service()
            
            pipeline = EngineAnomalyPipeline(anomaly_detector=anomaly_detector)
            try:
                # PatchCore 분석 파이프라인 호출
                result_data = await pipeline.analyze(
                    s3_url=s3_url,
                    image=image,
                    image_bytes=image_bytes,
                    yolo_model=engine_yolo,
                    anomaly_detector=anomaly_detector
                )
                
                # quality_warnings 추가
                if quality_warnings:
                    result_data["quality_warnings"] = quality_warnings
                
                # API 명세서 형식으로 바로 반환
                return result_data
            finally:
                await pipeline.close()
        
        elif scene_type == SceneType.SCENE_DASHBOARD:
            # DASHBOARD: YOLO (경고등 탐지) → LLM Fallback
            dashboard_yolo = models.get("dashboard_yolo")
            result_data = await analyze_dashboard_image(image, s3_url, dashboard_yolo)
            
            # quality_warnings 추가
            if quality_warnings:
                result_data["quality_warnings"] = quality_warnings
            
            # API 명세서 형식으로 바로 반환
            return result_data
        
        elif scene_type == SceneType.SCENE_EXTERIOR:
            # EXTERIOR: Unified YOLO (22 classes)
            exterior_yolo = models.get("exterior_yolo")
            result_data = await analyze_exterior_image(image, s3_url, exterior_yolo)
            
            # quality_warnings 추가
            if quality_warnings:
                result_data["quality_warnings"] = quality_warnings
            
            # API 명세서 형식으로 바로 반환
            return result_data
        
        elif scene_type == SceneType.SCENE_TIRE:
            # TIRE: YOLO → LLM
            tire_yolo = models.get("tire_yolo")
            result_data = await analyze_tire_image(image, s3_url, tire_yolo)
            
            # quality_warnings 추가
            if quality_warnings:
                result_data["quality_warnings"] = quality_warnings
            
            # API 명세서 형식으로 바로 반환
            return result_data
        
        else:
            # Unknown scene → LLM Fallback
            print(f"[Visual Fallback] 정의되지 않은 장면: {scene_type} -> LLM으로 전환 요청")
            llm_result = await analyze_general_image(s3_url)
            print(f"[Visual Fallback] LLM 응답: {llm_result}")
            
            # quality_warnings 추가
            if quality_warnings:
                llm_result["quality_warnings"] = quality_warnings
            
            return llm_result
            
    except Exception as e:
        print(f"[Visual Fallback] 분석 오류 발생, LLM으로 전환: {e}")
        llm_result = await analyze_general_image(s3_url)
        print(f"[Visual Fallback] LLM 응답: {llm_result}")
        
        # quality_warnings 추가
        if quality_warnings:
            llm_result["quality_warnings"] = quality_warnings
        
        return llm_result
    
    finally:
        # =================================================================
        # [Active Learning] 모델 재학습을 위한 데이터 수집
        # =================================================================
        # [Fix] confidence 변수가 정의되지 않았을 경우(예외 발생 시) 방지
        if 'confidence' in locals() and confidence < 0.85:
            await _record_for_active_learning(s3_url, scene_type, confidence)


async def _record_for_active_learning(
    s3_url: str, 
    scene_type: SceneType, 
    confidence: float
):
    """
    [Active Learning] 중앙 집중식 서비스 사용
    """
    try:
        from ai.app.services.common.active_learning_service import get_active_learning_service
        from ai.app.services.common.llm_service import generate_training_labels

        if scene_type == SceneType.SCENE_DASHBOARD:
             # Dashboard는 자체 서비스 내에서 Active Learning을 수행하므로 중복 수집 방지
             return

        # 장면 타입 → 도메인 이름 변환
        domain_map = {
            SceneType.SCENE_ENGINE: "engine",
            SceneType.SCENE_DASHBOARD: "dashboard",
            SceneType.SCENE_TIRE: "tire",
            SceneType.SCENE_EXTERIOR: "exterior"
        }
        domain = domain_map.get(scene_type)
        if not domain:
            # 매핑되지 않는 도메인(ETC 등)은 수집하지 않음
            return
        
        print(f"[Active Learning] 저신뢰 데이터 감지 ({confidence:.2f} < 0.85). LLM 라벨링 시작...")
        
        # Step 1: Oracle
        # Step 1: Oracle
        oracle_labels = await generate_training_labels(s3_url, domain)
        status = oracle_labels.get("status")

        # [Rule] Status 기반 필터링 제거 (UX용이므로 학습데이터 선정 기준 아님)
        # 오직 '라벨이 존재하는가' + '난이도가 적절한가'만 판단
        
        labels = oracle_labels.get("labels", [])
        if not labels:
            print(f"[Active Learning] 배제: 라벨 없음")
            return

        # [Rule] 너무 쉬운 데이터(High Confidence)는 이미 잘하므로 수집 제외
        if confidence > 0.85:
            return

        if status in ["IRRELEVANT", "ERROR"]:
            return

        # Step 3: Save & Manifest
        al_service = get_active_learning_service()
        label_key = al_service.save_oracle_label(s3_url, oracle_labels, domain, confidence=confidence)
        
        if label_key:
            al_service.record_manifest(
                s3_url=s3_url,
                category=scene_type.name.replace("SCENE_", ""), # SCENE_ENGINE -> ENGINE
                label_key=label_key,
                status=status,
                confidence=confidence,
                analysis_type="LLM_ORACLE_VISUAL",
                domain="visual"
            )
        
    except Exception as e:
        print(f"[Active Learning] 기록 실패 (무시): {e}")
