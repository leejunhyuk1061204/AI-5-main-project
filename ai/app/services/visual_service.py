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
from typing import Dict, Any, Optional, Tuple
import httpx
import io
import re
import base64
from PIL import Image
from urllib.parse import urlparse

from ai.app.services.router_service import RouterService, SceneType, get_router_service
from ai.app.services.llm_service import analyze_general_image
from ai.app.services.dashboard_service import analyze_dashboard_image
from ai.app.services.exterior_service import analyze_exterior_image
from ai.app.services.tire_service import analyze_tire_image

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
    # 0. Data URL 처리 (테스트용 base64)
    if url.startswith("data:"):
        try:
            # data:image/jpeg;base64,xxxx
            header, encoded = url.split(",", 1)
            content = base64.b64decode(encoded)
            image = Image.open(io.BytesIO(content)).convert("RGB")
            return image, content
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
        return {
            "status": "ERROR",
            "analysis_type": "IO_ERROR",
            "category": "ERROR",
            "data": {"message": str(e)}
        }

    # Step 1: Router로 장면 분류
    router = models.get("router") or get_router_service()
    
    try:
        scene_type, confidence = await router.classify(image)
        print(f"[Visual Service] Router 분류: {scene_type.value} (신뢰도: {confidence:.2f})")
        
        # 신뢰도가 낮으면 LLM에게 직접 판단 요청 (Fallback)
        if confidence < 0.85:
            print(f"[Visual Service] Router 신뢰도 낮음, LLM Fallback 실행")
            return await analyze_general_image(s3_url)
            
    except Exception as e:
        print(f"[Visual Service] Router 실패, LLM Fallback: {e}")
        llm_result = await analyze_general_image(s3_url)
        return llm_result
    
    # Step 2: 장면별 분기
    result_data = None
    try:
        if scene_type == SceneType.SCENE_ENGINE:
            # ENGINE: 기존 EngineAnomalyPipeline 사용
            from ai.app.services.engine_anomaly_service import EngineAnomalyPipeline
            
            pipeline = EngineAnomalyPipeline(anomaly_detector=models.get("anomaly_detector"))
            engine_yolo = models.get("engine_yolo")
            
            try:
                result_data = await pipeline.analyze(s3_url, image=image, image_bytes=image_bytes, yolo_model=engine_yolo)
                # API 명세서 형식으로 바로 반환 (content 래핑 제거)
                return result_data
            finally:
                await pipeline.close()
        
        elif scene_type == SceneType.SCENE_DASHBOARD:
            # DASHBOARD: YOLO(10종) → LLM
            dashboard_yolo = models.get("dashboard_yolo")
            result_data = await analyze_dashboard_image(image, s3_url, dashboard_yolo)
            # API 명세서 형식으로 바로 반환
            return result_data
        
        elif scene_type == SceneType.SCENE_EXTERIOR:
            # EXTERIOR: CarDD + CarParts → IoU → LLM
            cardd_yolo = models.get("cardd_yolo")
            carparts_yolo = models.get("carparts_yolo")
            result_data = await analyze_exterior_image(image, s3_url, cardd_yolo, carparts_yolo)
            # API 명세서 형식으로 바로 반환
            return result_data
        
        elif scene_type == SceneType.SCENE_TIRE:
            # TIRE: YOLO → LLM
            tire_yolo = models.get("tire_yolo")
            result_data = await analyze_tire_image(image, s3_url, tire_yolo)
            # API 명세서 형식으로 바로 반환
            return result_data
        
        else:
            # Unknown scene → LLM Fallback
            print(f"[Visual Service] Unknown scene: {scene_type}, LLM Fallback")
            llm_result = await analyze_general_image(s3_url)
            return llm_result
            
    except Exception as e:
        print(f"[Visual Service] 분석 오류, LLM Fallback: {e}")
        llm_result = await analyze_general_image(s3_url)
        return llm_result
    
    finally:
        # =================================================================
        # [Active Learning] 모델 재학습을 위한 데이터 수집
        # =================================================================
        # 왜 저신뢰 데이터만 수집하는가?
        # → 고신뢰(≥0.9): 모델이 이미 잘 맞추니까 재학습 효과 없음
        # → 저신뢰(<0.9): 모델이 헷갈려하는 데이터 → 이걸 학습해야 실력이 늘음
        # =================================================================
        if confidence < 0.9:
            await _record_for_active_learning(s3_url, scene_type, confidence)


async def _record_for_active_learning(
    s3_url: str, 
    scene_type: SceneType, 
    confidence: float
):
    """
    [Active Learning] 저신뢰 데이터의 정답 라벨을 LLM으로 생성하여 S3에 저장
    
    ┌─────────────────────────────────────────────────────────────┐
    │ Active Learning이란?                                        │
    │ - 모델이 틀리거나 불확실한 데이터를 수집                      │
    │ - LLM(GPT)이 정답(Oracle)을 생성                             │
    │ - 이 정답으로 모델을 재학습시켜 성능 향상                     │
    └─────────────────────────────────────────────────────────────┘
    
    [저장 조건] - 두 가지 모두 충족해야 저장
    1. 신뢰도 < 0.9 (모델이 불확실한 데이터)
    2. 품질 통과 (차량 관련 이미지, 분석 가능한 상태)
    
    [배제 조건] - 재학습해도 도움 안 되는 데이터
    - status == "IRRELEVANT": 차량 관련 없는 이미지 (고양이 사진 등)
    - status == "ERROR": 분석 불가 (너무 어둡거나 흐림)
    - labels가 비어있음: LLM도 객체를 못 찾음 (의미 없는 이미지)
    
    [S3 저장 경로]
    - dataset/{domain}/llm_confirmed/{file_id}.json
    - 예: dataset/engine/llm_confirmed/abc123.json
    """
    try:
        # 필요한 모듈 임포트 (함수 내부에서 하여 순환 참조 방지)
        from ai.app.services.manifest_service import add_visual_entry
        from ai.app.services.llm_service import generate_training_labels
        import boto3
        import json

        # 장면 타입 → 도메인 이름 변환
        # 예: SceneType.SCENE_ENGINE → "engine"
        domain_map = {
            SceneType.SCENE_ENGINE: "engine",
            SceneType.SCENE_DASHBOARD: "dashboard",
            SceneType.SCENE_TIRE: "tire",
            SceneType.SCENE_EXTERIOR: "exterior"
        }
        domain = domain_map.get(scene_type, "engine")
        
        print(f"[Active Learning] 저신뢰 데이터 감지 ({confidence:.2f} < 0.9). LLM 라벨링 시작...")
        
        # =================================================================
        # Step 1: LLM에게 정답 라벨 생성 요청 (Oracle)
        # =================================================================
        # LLM(GPT-4o)이 이미지를 보고 객체의 위치와 종류를 알려줌
        # 반환값 예시:
        # {
        #   "labels": [{"class": "Battery", "bbox": [0.5, 0.3, 0.1, 0.1]}],
        #   "status": "NORMAL"
        # }
        oracle_labels = await generate_training_labels(s3_url, domain)
        
        # =================================================================
        # Step 2: 품질 필터링 - 재학습 가치 없는 데이터 배제
        # =================================================================
        # LLM이 반환한 상태값으로 품질 판단
        status = oracle_labels.get("status", "")
        
        # [배제 1] 차량 관련 없는 이미지
        # 예: 음식 사진, 풍경 사진 등 → 차량 모델 학습에 쓸모없음
        if status == "IRRELEVANT":
            print(f"[Active Learning] 배제: 차량 관련 없는 이미지")
            return  # 저장하지 않고 종료
        
        # [배제 2] 분석 불가 상태
        # 예: 너무 어둡거나, 흐릿하거나, 일부만 보이는 경우
        if status == "ERROR":
            print(f"[Active Learning] 배제: 분석 불가 상태")
            return  # 저장하지 않고 종료
        
        # [배제 3] LLM도 객체를 못 찾은 경우
        # 예: 빈 배경만 있는 이미지 → 라벨이 없으면 학습 불가
        if not oracle_labels.get("labels"):
            print(f"[Active Learning] 배제: 라벨 없음 (객체 미감지)")
            return  # 저장하지 않고 종료
        
        # =================================================================
        # Step 3: 품질 통과 → S3에 라벨 JSON 저장
        # =================================================================
        # AWS S3 클라이언트 생성 (환경변수에서 자격증명 자동 로드)
        s3 = boto3.client('s3')
        
        # 버킷 이름: 환경변수에 없으면 기본값 사용
        bucket = os.getenv("S3_BUCKET_NAME", "car-sentry-data")
        
        # 파일 ID 추출: "abc123.jpg" → "abc123"
        file_id = os.path.basename(s3_url).split('.')[0]
        
        # 저장 경로: dataset/llm_confirmed/visual/{domain}/{file_id}.json
        label_key = f"dataset/llm_confirmed/visual/{domain}/{file_id}.json"
        
        # S3에 JSON 파일 업로드
        s3.put_object(
            Bucket=bucket,
            Key=label_key,
            Body=json.dumps(oracle_labels, ensure_ascii=False, indent=2),
            ContentType='application/json'
        )
        print(f"[Active Learning] 고품질 정답지 저장 완료: {label_key}")
        
        # =================================================================
        # Step 4: Manifest에 기록 (데이터 목록 관리용)
        # =================================================================
        # Manifest = 어떤 데이터가 수집되었는지 목록을 관리하는 JSON 파일
        # 나중에 재학습 시 이 목록을 보고 데이터를 불러옴
        add_visual_entry(
            original_url=s3_url,       # 원본 이미지 S3 위치
            category=scene_type.value, # ENGINE, DASHBOARD 등
            label_key=label_key,       # 라벨 JSON S3 위치
            status=status,             # NORMAL, WARNING 등
            analysis_type=scene_type.value,
            detections=None,
            confidence=confidence      # 원래 모델의 신뢰도
        )
        print(f"[Active Learning] Manifest 기록 완료: {scene_type.value} ({confidence:.2f})")
        
    except Exception as e:
        # Active Learning 실패해도 메인 분석에는 영향 없음
        print(f"[Active Learning] 기록 실패 (무시): {e}")
