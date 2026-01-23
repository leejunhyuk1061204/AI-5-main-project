# ai/app/services/visual_service.py
"""
통합 시각 분석 서비스 (Visual Orchestrator)

[역할]
1. 통합 진입점: 클라이언트의 모든 시각 분석 요청(이미지 URL)을 받아 처리하는 최상위 서비스입니다.
2. 지능형 라우팅: Router 서비스를 통해 장면을 분류하고, 각 도메인 전용 파이프라인(엔진, 타이어 등)으로 작업을 위임합니다.
3. 보안 및 전처리: SSRF 공격 방지를 위해 URL을 검증하고, 이미지를 안전하게 로드하여 중복 다운로드를 방지합니다.

[주요 기능]
- 스마트 종합 진단 (get_smart_visual_diagnosis)
- 안전한 이미지 로딩 및 전처리 (_safe_load_image)
- 장면별 분석 파이프라인 연결 (Engine, Dashboard, Exterior, Tire)
"""
from typing import Dict, Any, Optional
from ai.app.schemas.visual_schema import VisualResponse
from ai.app.services.router_service import RouterService, SceneType, get_router_service
from ai.app.services.llm_service import analyze_general_image
from ai.app.services.dashboard_service import analyze_dashboard_image
from ai.app.services.exterior_service import analyze_exterior_image
from ai.app.services.tire_service import analyze_tire_image

import httpx
import io
import re
from PIL import Image
from urllib.parse import urlparse
from typing import Tuple

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



async def _safe_load_image(url: str) -> Tuple[Image.Image, bytes]:
    """
    S3 URL 이미지를 안전하게 로드
    1. SSRF 방지 (URL 검증)
    2. 중복 다운로드 방지 (한 번만 다운로드하여 반환)
    """
    # 1. SSRF 검증
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
            return image, content
            
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
            - cardd_yolo: CarDD YOLO 모델
            - carparts_yolo: CarParts YOLO 모델
            - tire_yolo: Tire YOLO 모델
    
    Returns:
        {"type": "SCENE_*", "content": VisualResponse}
    """
    if models is None:
        models = {}
    
    # Step 0: 이미지 안전 로드 (전처리)
    try:
        image, image_bytes = await _safe_load_image(s3_url)
    except Exception as e:
        print(f"[Visual Service] 이미지 로드 실패: {e}")
        return {"type": "ERROR", "content": {"message": str(e)}}

    # Step 1: Router로 장면 분류
    router = models.get("router") or get_router_service()
    
    try:
        scene_type, confidence = await router.classify(image)
        print(f"[Visual Service] Router 분류: {scene_type.value} (신뢰도: {confidence:.2f})")
    except Exception as e:
        print(f"[Visual Service] Router 실패, LLM Fallback: {e}")
        llm_result = await analyze_general_image(s3_url)
        return {"type": "LLM_FALLBACK", "content": llm_result}
    
    # Step 2: 장면별 분기
    result_data = None
    try:
        if scene_type == SceneType.SCENE_ENGINE:
            # ENGINE: 기존 EngineAnomalyPipeline 사용
            from ai.app.services.engine_anomaly_service import EngineAnomalyPipeline
            
            pipeline = EngineAnomalyPipeline()
            engine_yolo = models.get("engine_yolo")
            
            try:

                result_data = await pipeline.analyze(s3_url, image=image, image_bytes=image_bytes, yolo_model=engine_yolo)
                if isinstance(result_data, dict):
                    result_data["scene_type"] = scene_type
                return {"type": scene_type.value, "content": result_data}
            finally:
                await pipeline.close()
        
        elif scene_type == SceneType.SCENE_DASHBOARD:
            # DASHBOARD: YOLO(10종) → LLM
            dashboard_yolo = models.get("dashboard_yolo")
            result_data = await analyze_dashboard_image(image, s3_url, dashboard_yolo)
            if hasattr(result_data, "scene_type"):
                result_data.scene_type = scene_type
            return {"type": scene_type.value, "content": result_data}
        
        elif scene_type == SceneType.SCENE_EXTERIOR:
            # EXTERIOR: CarDD + CarParts → IoU → LLM
            cardd_yolo = models.get("cardd_yolo")
            carparts_yolo = models.get("carparts_yolo")
            result_data = await analyze_exterior_image(image, s3_url, cardd_yolo, carparts_yolo)
            if hasattr(result_data, "scene_type"):
                result_data.scene_type = scene_type
            return {"type": scene_type.value, "content": result_data}
        
        elif scene_type == SceneType.SCENE_TIRE:
            # TIRE: YOLO → LLM
            tire_yolo = models.get("tire_yolo")
            result_data = await analyze_tire_image(image, s3_url, tire_yolo)
            if hasattr(result_data, "scene_type"):
                result_data.scene_type = scene_type
            return {"type": scene_type.value, "content": result_data}
        
        else:
            # Unknown scene → LLM Fallback
            print(f"[Visual Service] Unknown scene: {scene_type}, LLM Fallback")
            llm_result = await analyze_general_image(s3_url)
            return {"type": "LLM_FALLBACK", "content": llm_result}
            
    except Exception as e:
        print(f"[Visual Service] 분석 오류, LLM Fallback: {e}")
        llm_result = await analyze_general_image(s3_url)
        return {"type": "LLM_FALLBACK", "content": llm_result}
    
    finally:
        # Active Learning: 분석 결과 기록
        await _record_for_active_learning(s3_url, scene_type, confidence)


async def _record_for_active_learning(
    s3_url: str, 
    scene_type: SceneType, 
    confidence: float
):
    """
    Active Learning용 데이터 기록
    Confidence < 0.9 (Fast Path 통과 못함)일 경우 LLM 정답 JSON 생성 및 S3 저장
    """
    try:
        from ai.app.services.manifest_service import add_visual_entry
        from ai.app.services.llm_service import generate_training_labels
        import boto3
        import json

        label_key = None
        
        # 신뢰도가 0.9 미만이면 LLM이 정답(Oracle)을 생성하여 S3에 저장
        if confidence < 0.9:
            print(f"[Active Learning] 저신뢰 데이터 감지 ({confidence:.2f} < 0.9). LLM 라벨링 시작...")
            domain_map = {
                SceneType.SCENE_ENGINE: "engine",
                SceneType.SCENE_DASHBOARD: "dashboard",
                SceneType.SCENE_TIRE: "tire",
                SceneType.SCENE_EXTERIOR: "exterior"
            }
            domain = domain_map.get(scene_type, "engine")
            
            # LLM 정답 생성 (Oracle)
            oracle_labels = await generate_training_labels(s3_url, domain)
            
            if oracle_labels.get("labels"):
                # S3에 JSON 저장
                s3 = boto3.client('s3')
                bucket = os.getenv("S3_BUCKET_NAME", "car-sentry-data")
                file_id = os.path.basename(s3_url).split('.')[0]
                label_key = f"dataset/{domain}/llm_confirmed/{file_id}.json"
                
                s3.put_object(
                    Bucket=bucket,
                    Key=label_key,
                    Body=json.dumps(oracle_labels, ensure_ascii=False, indent=2),
                    ContentType='application/json'
                )
                print(f"[Active Learning] 고품질 정답지 저장 완료: {label_key}")

        # Manifest 기록 (original_url은 그대로, label_key는 LLM이 만든 JSON 경로)
        add_visual_entry(
            original_url=s3_url,
            category=scene_type.value,
            label_key=label_key,
            status="ANALYZED" if label_key else "HIGH_CONFIDENCE",
            analysis_type=scene_type.value,
            detections=None,
            confidence=confidence
        )
        print(f"[Active Learning] Manifest 기록 완료: {scene_type.value} ({confidence:.2f})")
        
    except Exception as e:
        print(f"[Active Learning] 기록 실패 (무시): {e}")
