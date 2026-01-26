# app/api/v1/routes/test_router.py
"""
로컬 테스트 라우터 (OpenAI/S3 없이 테스트 가능)
- Mock 응답
- 실제 YOLO 추론 (로컬 이미지)

===============================================================================
[섹션 1] /connect - 사용자님 코드 (main merge 전)
===============================================================================
[섹션 2] /test - ISC님 코드 (main 브랜치)
===============================================================================
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from fastapi.responses import JSONResponse
from ai.app.services.local_service import process_visual_mock, process_audio_mock
from ai.app.services.router_service import SceneType
from ai.app.schemas.visual_schema import VisualResponse, DetectionItem
from ai.app.schemas.audio_schema import AudioResponse
from ai.app.schemas.wear_factor import VehicleMetadata, DrivingHabits # 공통 메타데이터는 재사용
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from PIL import Image
import io
import os
import base64

# Singleton AnomalyDetector (한 번만 로드)
from ai.app.services.anomaly_service import AnomalyDetector
_anomaly_detector = None

def get_anomaly_detector():
    global _anomaly_detector
    if _anomaly_detector is None:
        _anomaly_detector = AnomalyDetector()
    return _anomaly_detector

# Singleton AST Model (한 번만 로드)
_ast_model = None
_ast_feature_extractor = None

def get_ast_model():
    global _ast_model, _ast_feature_extractor
    if _ast_model is None:
        from transformers import ASTForAudioClassification, ASTFeatureExtractor
        model_path = "ai/weights/audio/best_ast_model"
        if os.path.exists(model_path):
            print("[AST Singleton] Loading AST model...")
            _ast_model = ASTForAudioClassification.from_pretrained(model_path)
            _ast_feature_extractor = ASTFeatureExtractor.from_pretrained(model_path)
            print("[AST Singleton] AST model loaded!")
    return _ast_model, _ast_feature_extractor


# ==============================================================================
# [섹션 1] 사용자님 코드 (main merge 전) - prefix: /connect
# ==============================================================================

connect_router = APIRouter(prefix="/connect", tags=["Connect Test (사용자)"])


class FileUrlRequest(BaseModel):
    file_url: str


class OBDDataPoint(BaseModel):
    rpm: float
    load: float
    coolant: float
    voltage: float


class AnomalyRequest(BaseModel):
    time_series: List[Dict]


class AnomalyResponse(BaseModel):
    is_anomaly: bool
    anomaly_score: float
    threshold: float
    contributing_factors: List[str]


@connect_router.post("/predict/visual", response_model=VisualResponse)
async def connect_analyze_visual(file: UploadFile = File(...)):
    """
    [사용자 - Mock] 이미지 파일 직접 수신 -> Mock 응답 반환
    """
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Invalid image file type")
    
    content = await file.read()
    return await process_visual_mock(content)


@connect_router.post("/predict/audio", response_model=AudioResponse)
async def connect_analyze_audio(file: UploadFile = File(...)):
    """
    [사용자 - Mock] 오디오 파일 직접 수신 -> Mock 응답 반환
    """
    content = await file.read()
    return await process_audio_mock(content)


@connect_router.post("/visual", response_model=VisualResponse)
async def connect_analyze_visual_url(request: FileUrlRequest):
    """
    [사용자 - URL] 이미지 URL 수신 -> 파일 다운로드 -> Mock 응답 반환
    """
    import httpx
    
    filename = request.file_url.split("/")[-1]
    uploads_dir = os.path.join(os.path.dirname(__file__), "../../../../uploads")
    os.makedirs(uploads_dir, exist_ok=True)
    file_path = os.path.join(uploads_dir, filename)
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(request.file_url)
            content = response.content
            with open(file_path, "wb") as f:
                f.write(content)
    except Exception:
        content = b"mock_image_data"
    
    return await process_visual_mock(content)


@connect_router.post("/audio", response_model=AudioResponse)
async def connect_analyze_audio_url(request: FileUrlRequest):
    """
    [사용자 - URL] 오디오 URL 수신 -> 파일 다운로드 -> Mock 응답 반환
    """
    import httpx
    
    filename = request.file_url.split("/")[-1]
    uploads_dir = os.path.join(os.path.dirname(__file__), "../../../../uploads")
    os.makedirs(uploads_dir, exist_ok=True)
    file_path = os.path.join(uploads_dir, filename)
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(request.file_url)
            content = response.content
            with open(file_path, "wb") as f:
                f.write(content)
    except Exception:
        content = b"mock_audio_data"
    
    return await process_audio_mock(content)


@connect_router.post("/predict/anomaly", response_model=AnomalyResponse)
async def connect_analyze_anomaly(request: AnomalyRequest):
    """
    [사용자 - Mock] LSTM 시계열 이상 탐지 Mock 응답 반환
    """
    data_count = len(request.time_series)
    
    return AnomalyResponse(
        is_anomaly=data_count >= 10,
        anomaly_score=0.75 if data_count >= 10 else 0.25,
        threshold=0.70,
        contributing_factors=["RPM", "VOLTAGE"] if data_count >= 10 else []
    )


@connect_router.post("/predict/embedding")
async def connect_get_embedding(data: dict):
    """[사용자 - Mock] 더미 임베딩 반환 (1024차원)"""
    text = data.get("text", "")
    print(f"[Connect Router] Received Embedding Request: '{text[:50]}...'")
    dummy_vector = [0.01] * 1024
    
    return {
        "embedding": dummy_vector,
        "model": "mxbai-embed-large-dummy"
    }


@connect_router.post("/predict/comprehensive")
async def connect_comprehensive_mock(data: dict):
    """
    [사용자 - Mock] 종합 진단 Mock 응답 반환 (수동/자동 진단용)
    - 4.API 명세서.md (Part 2 - 6. AI 진단 통합)의 스펙을 준수함.
    
    Response Modes:
    - REPORT: 진단 완료 (Confidence High/Mid)
    - INTERACTIVE: 추가 정보 요청 (Confidence Low)
    
    대화 이력(conversation_history) 기반 시나리오:
    - 사진/오디오 없이 텍스트만: 4회까지 INTERACTIVE (백엔드 3턴 제한 테스트용)
    - 사진 또는 오디오 있음: REPORT 생성
    """
    import asyncio
    await asyncio.sleep(1)  # 분석 지연 시뮬레이션 (테스트용으로 단축)
    
    vehicle_id = data.get("vehicleId", "unknown")
    audio = data.get("analysis_results", {}).get("audioAnalysis") or data.get("audioAnalysis")
    visual = data.get("analysis_results", {}).get("visualAnalysis") or data.get("visualAnalysis")
    anomaly = data.get("analysis_results", {}).get("anomalyAnalysis") or data.get("anomalyAnalysis")
    rag_context = data.get("rag_context") or data.get("knowledgeData")
    
    # 대화 이력 파싱
    conversation = data.get("conversation_history", [])
    user_reply_count = len([m for m in conversation if m.get("role") == "user"])
    
    print(f"[Comprehensive] Request for vehicle: {vehicle_id}")
    print(f"- Visual: {'YES' if visual else 'NO'}, Audio: {'YES' if audio else 'NO'}, Anomaly: {'YES' if anomaly else 'NO'}")
    print(f"- Conversation history: {user_reply_count} user replies")

    # 분기 조건: 사진/오디오 있으면 → REPORT, 없으면 → 4회까지 INTERACTIVE
    has_media = bool(visual) or bool(audio)
    
    if has_media:
        # 사진 또는 오디오가 있으면 → REPORT 생성
        is_anomaly = anomaly.get("is_anomaly") if anomaly else False
        has_visual_issue = visual.get("status") == "FAULTY" if visual else False
        has_audio_issue = audio.get("status") == "FAULTY" if audio else False
        
        return {
            "response_mode": "REPORT",
            "confidence_level": "HIGH" if (audio or visual) else "MEDIUM",
            "summary": "수집된 데이터를 바탕으로 종합 분석을 완료했습니다.",
            "report_data": {
                "suspected_causes": [
                    {
                        "cause": "냉각 계통 점검 필요" if (is_anomaly or has_visual_issue) else "정상 상태",
                        "basis": "사용자 제공 미디어 분석 결과",
                        "source_type": "CONFIRMED",
                        "reliability": "HIGH"
                    }
                ],
                "final_guide": "미디어 분석 결과를 종합하여, 정기적인 점검을 권장합니다." if (is_anomaly or has_visual_issue or has_audio_issue) else "차량 상태가 양호합니다.",
                "risk_level": "MID" if (is_anomaly or has_visual_issue) else "LOW"
            },
            "interactive_data": None,
            "disclaimer": "본 진단은 AI 분석에 기반하며, 실제 정비 전문가의 의견과 다를 수 있습니다."
        }
    
    # 사진/오디오 없이 텍스트만 → 4회까지 INTERACTIVE (백엔드 3턴 제한 테스트용)
    if user_reply_count >= 4:
        # 4회 이상이면 AI에서도 REPORT (정상 케이스)
        return {
            "response_mode": "REPORT",
            "confidence_level": "MEDIUM",
            "summary": "대화를 통해 수집된 정보를 바탕으로 분석을 완료했습니다.",
            "report_data": {
                "suspected_causes": [
                    {
                        "cause": "추가 점검 권장",
                        "basis": "사용자 답변 종합 분석",
                        "source_type": "INFERRED",
                        "reliability": "MEDIUM"
                    }
                ],
                "final_guide": "대화를 통해 수집된 정보로는 명확한 진단이 어렵습니다. 정비소 방문을 권장합니다.",
                "risk_level": "MID"
            },
            "interactive_data": None,
            "disclaimer": "본 진단은 AI 추론에 기반하며 참고용입니다."
        }
    
    # 0~3회: INTERACTIVE 모드 유지
    follow_up_messages = [
        "정확한 진단을 위해 추가 정보가 필요합니다. 이상 증상이 언제부터 시작되었나요?",
        "감사합니다. 시동을 켤 때 특별한 소리가 나나요?",
        "알겠습니다. 최근 냉각수나 엔진오일 점검을 하신 적 있나요?",
        "추가 확인이 필요합니다. 계기판에 경고등이 켜진 적 있나요?"
    ]
    
    return {
        "response_mode": "INTERACTIVE",
        "confidence_level": "LOW",
        "summary": f"대화 {user_reply_count + 1}회차 - 추가 정보 수집 중",
        "report_data": None,
        "interactive_data": {
            "message": follow_up_messages[min(user_reply_count, 3)],
            "follow_up_questions": [
                "엔진룸 사진을 찍어서 보내주시면 더 정확한 분석이 가능합니다."
            ],
            "requested_actions": ["CAPTURE_PHOTO", "RECORD_AUDIO"]
        },
        "disclaimer": "추가 정보가 필요한 상태입니다."
    }

# ---- /connect 전용 Phase 2 Mock 스키마 ----
class ConnectConsumableContext(BaseModel):
    code: str
    last_replaced_mileage: float
    is_inferred: bool = False

class ConnectWearFactorRequest(BaseModel):
    vehicle_metadata: VehicleMetadata
    driving_habits: DrivingHabits
    consumables: List[ConnectConsumableContext]

class ConnectWearFactorResponse(BaseModel):
    wear_factors: Dict[str, float]
    remaining_lifes: Dict[str, float]
    model_version: str


@connect_router.post("/predict/wear-factor", response_model=ConnectWearFactorResponse)
async def connect_predict_wear_factor(request: ConnectWearFactorRequest):
    """
    [사용자 - Mock] Phase 2용 소모품별 마모도 및 예측 수명 응답
    - is_inferred=True: AI가 기초 데이터를 보정하여 수명 재계산
    - is_inferred=False: 사용자 데이터를 존중하여 가중치 누적 차감
    """
    import random
    
    wear_factors = {}
    remaining_lifes = {}
    
    for item in request.consumables:
        # 가중치 (Wear Factor)
        factor = round(random.uniform(0.8, 1.4), 2)
        wear_factors[item.code] = factor
        
        # 잔존 수명 (Remaining Life)
        if item.is_inferred:
            # 보정 모드: AI가 정교하게 예측한 % 제공
            life = round(random.uniform(40.0, 95.0), 1)
        else:
            # 누적 차감 모드: 현재 주행 패턴 기반 차감 시뮬레이션
            life = round(random.uniform(10.0, 85.0), 1)
            
        remaining_lifes[item.code] = life
    
    return ConnectWearFactorResponse(
        wear_factors=wear_factors,
        remaining_lifes=remaining_lifes,
        model_version="xgboost-mock-0.3.0-connect"
    )


@connect_router.get("/endpoints")
async def connect_list_endpoints():
    """[사용자] 사용 가능한 /connect 엔드포인트 목록"""
    return {
        "section": "사용자 (main merge 전)",
        "endpoints": [
            {"path": "/connect/predict/visual", "method": "POST", "description": "Visual Mock (파일 업로드)"},
            {"path": "/connect/predict/audio", "method": "POST", "description": "Audio Mock (파일 업로드)"},
            {"path": "/connect/visual", "method": "POST", "description": "Visual Mock (URL 방식)"},
            {"path": "/connect/audio", "method": "POST", "description": "Audio Mock (URL 방식)"},
            {"path": "/connect/predict/anomaly", "method": "POST", "description": "LSTM 이상탐지 Mock"},
            {"path": "/connect/predict/comprehensive", "method": "POST", "description": "종합 진단 Mock"},
            {"path": "/connect/predict/wear-factor", "method": "POST", "description": "마모율 예측 Mock"},
            {"path": "/connect/predict/embedding", "method": "POST", "description": "임베딩 Mock"},
        ]
    }


# ==============================================================================
# [섹션 2] ISC님 코드 (main 브랜치) - prefix: /test
# ==============================================================================

router = APIRouter(prefix="/test", tags=["Local Test (ISC)"])


@router.get("/health")
async def health_check():
    """서버 상태 확인"""
    return {"status": "OK", "message": "AI Server is running!"}


@router.post("/predict/visual", response_model=VisualResponse)
async def analyze_visual_local(file: UploadFile = File(...)):
    """[ISC - Mock] 이미지 파일 직접 수신 -> Mock 응답 반환"""
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Invalid image file type")
    
    content = await file.read()
    return await process_visual_mock(content)


@router.post("/predict/yolo")
async def analyze_yolo_local(category: str = "auto", force: Optional[str] = None, file: UploadFile = File(...), request: Request = None):
    """
    [ISC - Real YOLO] 로컬 이미지 → 실제 YOLO 추론
    카테고리에 따라 다른 모델 사용: engine, dashboard, tire, exterior
    """
    import tempfile
    import asyncio
    import io
    from PIL import Image
    from fastapi.responses import JSONResponse
    
    try:
        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Image file required")
        
        content = await file.read()
        image = Image.open(io.BytesIO(content))
        
        if image.mode != "RGB":
            image = image.convert("RGB")
        
        # 1. 모델 선택 (app.state 에서 가져옴)
        model = None
        scene_info = {}
        
        # 'force' 쿼리 파라미터가 있으면 라우터 무시하고 강제 적용
        if force:
            category = force
            print(f"[Test Router] Forced category: {category}")
        elif category == "auto" and request and hasattr(request.app.state, "get_router"):
            router = request.app.state.get_router()
            scene_type, confidence = await router.classify(image)
            scene_info = {
                "detected_scene": scene_type.value,
                "scene_confidence": round(float(confidence), 4)
            }
            # SceneType을 내부 카테고리 문자열로 매핑
            mapping = {
                SceneType.SCENE_ENGINE: "engine",
                SceneType.SCENE_DASHBOARD: "dashboard",
                SceneType.SCENE_EXTERIOR: "exterior",
                SceneType.SCENE_TIRE: "tire"
            }
            category = mapping.get(scene_type, "engine")
            print(f"[Test Router] Auto-detected category: {category} ({confidence:.2f})")

        if request and hasattr(request.app.state, "get_engine_yolo"):
            if category == "engine":
                model = request.app.state.get_engine_yolo()
            elif category == "dashboard":
                model = request.app.state.get_dashboard_yolo()
            elif category == "tire":
                model = request.app.state.get_tire_yolo()
            elif category == "exterior":
                # 외관은 cardd 모델 기본 사용
                model = request.app.state.get_exterior_yolo().get("cardd")
        
        # app.state에 모델이 없는 경우 (로컬 단독 실행 등) 직접 로드 시도
        if model is None:
            from ultralytics import YOLO
            paths = {
                "engine": "ai/weights/engine/best.pt",
                "dashboard": "ai/weights/dashboard/best.pt",
                "tire": "ai/weights/tire/best.pt",
                "exterior": "ai/weights/exterior/cardd/best.pt"
            }
            model_path = paths.get(category, "ai/weights/engine/best.pt")
            if os.path.exists(model_path):
                model = YOLO(model_path)
            else:
                # 최후의 수단: 기본 모델
                model_path = "ai/weights/yolov8n.pt"
                if os.path.exists(model_path):
                    model = YOLO(model_path)
                    print(f"[Warning] {category} 전용 가중치 없음. 기본 YOLOv8n 사용.")
                else:
                    return JSONResponse(status_code=400, content={
                        "status": "ERROR",
                        "message": f"{category} 모델 가중치가 없습니다. 학습을 먼저 진행하거나 Weights 폴더를 확인해 주세요.",
                        "category": category
                    })

        # 2. 전용 파이프라인 호출 (표준 JSON 규격 반영)
        # S3 URL 대신 Base64를 전달하여 로컬에서도 LLM 분석이 가능하도록 함
        img_b64 = base64.b64encode(content).decode('utf-8')
        s3_url_mock = f"data:image/jpeg;base64,{img_b64}"
        
        try:
            if category == "engine":
                from ai.app.services.engine_anomaly_service import EngineAnomalyPipeline
                pipeline = EngineAnomalyPipeline(anomaly_detector=request.app.state.get_anomaly_detector())
                try:
                    result = await pipeline.analyze(s3_url_mock, image=image, image_bytes=content, yolo_model=model)
                    
                    # 만약 결과가 여전히 에러(모델 없음 + API키 없음)라면 안내 강화
                    if result.get("status") == "ERROR" and "API Key" in str(result.get("data", {}).get("description")):
                        return JSONResponse(status_code=401, content=result)
                        
                    return JSONResponse(content=result)
                finally:
                    await pipeline.close()
            
            elif category == "dashboard":
                from ai.app.services.dashboard_service import analyze_dashboard_image
                result = await analyze_dashboard_image(image, s3_url_mock, model)
                return JSONResponse(content=result)
            
            elif category == "tire":
                from ai.app.services.tire_service import analyze_tire_image
                result = await analyze_tire_image(image, s3_url_mock, model)
                return JSONResponse(content=result)
            
            elif category == "exterior":
                from ai.app.services.exterior_service import analyze_exterior_image
                # 외관은 cardd와 carparts 두 모델이 필요함
                exterior_models = request.app.state.get_exterior_yolo() if request else {}
                cardd = exterior_models.get("cardd")
                carparts = exterior_models.get("carparts")
                result = await analyze_exterior_image(image, s3_url_mock, cardd, carparts)
                return JSONResponse(content=result)
            
            else:
                # 기본 처리 (YOLO Raw 데이터)
                # 기존 tmp_path 저장 및 predict 로직
                tmp_path = os.path.join(tempfile.gettempdir(), f"yolo_test_{os.getpid()}.jpg")
                image.save(tmp_path, "JPEG")
                try:
                    results = model.predict(source=tmp_path, conf=0.25, save=False)
                finally:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)

                output = {
                    "status": "SUCCESS",
                    "category": category,
                    **scene_info,
                    "source": f"uploaded:{file.filename}",
                    "model_type": "detection"
                }
                if hasattr(results[0], 'probs') and results[0].probs is not None:
                    output["model_type"] = "classification"
                    top1_idx = int(results[0].probs.top1)
                    output["top1_label"] = model.names[top1_idx]
                    output["top1_confidence"] = round(float(results[0].probs.top1conf), 4)
                    output["all_probs"] = {model.names[i]: round(float(p), 4) for i, p in enumerate(results[0].probs.data)}
                else:
                    detections = []
                    for r in results:
                        for box in r.boxes:
                            detections.append({
                                "label": model.names[int(box.cls[0])],
                                "confidence": round(float(box.conf[0]), 3),
                                "bbox": [int(v) for v in box.xyxy[0].tolist()]
                            })
                    output["detections"] = detections
                    output["count"] = len(detections)
                return JSONResponse(content=output)
                
        except Exception as e:
            print(f"[Test Router] Service Pipeline Error: {e}")
            import traceback
            traceback.print_exc()
            # 서비스 실패 시 롤백 (Raw 데이터라도 반환)
            return JSONResponse(content={"status": "ERROR", "message": f"Service Pipeline Failed: {str(e)}"}, status_code=500)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(content={
            "status": "ERROR",
            "message": str(e)
        }, status_code=500)


@router.post("/predict/audio")
async def analyze_audio_local(file: UploadFile = File(...)):
    """
    [ISC - Real AST] 로컬 오디오 업로드 → 실제 AST 추론 (ast_service 로직 사용)
    """
    try:
        content = await file.read()
        
        import tempfile
        import librosa
        import torch
        import torch.nn.functional as F
        from ai.app.services.ast_service import NORMAL_LABELS, get_category_from_label
        
        tmp_path = os.path.join(tempfile.gettempdir(), f"audio_test_{os.getpid()}.wav")
        
        with open(tmp_path, "wb") as f:
            f.write(content)
        
        try:
            audio_array, sr = librosa.load(tmp_path, sr=16000)
            
            # 싱글톤 AST 모델 사용 (매 요청마다 로드 X)
            model, feature_extractor = get_ast_model()
            
            if model is None:
                return JSONResponse(content={
                    "status": "FAULTY",
                    "analysis_type": "AST_MOCK",
                    "category": "ENGINE",
                    "detail": {
                        "diagnosed_label": "Engine_Knocking",
                        "description": "[Mock] 학습된 AST 모델이 없어 Mock 응답을 반환합니다."
                    },
                    "confidence": 0.95,
                    "is_critical": True,
                    "note": "모델 경로 없음: ai/weights/audio/best_ast_model"
                })
            
            analysis_type = "AST"
            
            inputs = feature_extractor(
                audio_array,
                sampling_rate=16000,
                return_tensors="pt",
                padding="max_length"
            )
            
            with torch.no_grad():
                outputs = model(**inputs)
                logits = outputs.logits
                probs = F.softmax(logits, dim=-1)
                confidence = probs.max().item()
                predicted_id = logits.argmax(-1).item()
            
            label_name = model.config.id2label[predicted_id]
            
            # ast_service.py의 함수 사용
            category = get_category_from_label(label_name)
            
            # ast_service.py의 NORMAL_LABELS 사용
            label_lower = label_name.lower()
            if confidence < 0.5:
                status = "UNKNOWN"
                is_critical = False
                category = "UNKNOWN_AUDIO"
                label_name = "unknown"  # 라벨도 unknown으로 변경
                description = "분류할 수 없는 소리입니다. 차량 관련 소리인지 확인해주세요."
            elif label_lower in NORMAL_LABELS or "normal" in label_lower:
                status = "NORMAL"
                is_critical = False
                description = "정상적인 소리입니다."
            else:
                status = "FAULTY"
                is_critical = True
                description = f"{label_name} 소음이 감지되었습니다. 점검이 필요합니다."
            
            return JSONResponse(content={
                "status": status,
                "analysis_type": analysis_type,
                "category": category,
                "detail": {
                    "diagnosed_label": label_name,
                    "description": description
                },
                "confidence": round(confidence, 4),
                "is_critical": is_critical,
                "source": f"uploaded:{file.filename}"
            })
            
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
                
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(content={
            "status": "ERROR",
            "message": str(e)
        }, status_code=500)


@router.post("/predict/embedding")
async def get_dummy_embedding(data: dict):
    """[ISC - Mock] 더미 임베딩 반환 (1024차원)"""
    text = data.get("text", "")
    print(f"[Test Router] Received Embedding Request: '{text[:50]}...'")
    dummy_vector = [0.01] * 1024
    
    return {
        "embedding": dummy_vector,
        "model": "mxbai-embed-large-dummy"
    }


@router.get("/endpoints")
async def list_endpoints():
    """[ISC] 사용 가능한 /test 엔드포인트 목록"""
    return {
        "section": "ISC (main 브랜치)",
        "endpoints": [
            {"path": "/test/health", "method": "GET", "description": "서버 상태 확인"},
            {"path": "/test/predict/yolo", "method": "POST", "description": "실제 YOLO 추론 (이미지 업로드)"},
            {"path": "/test/predict/visual", "method": "POST", "description": "Visual Mock 응답"},
            {"path": "/test/predict/audio", "method": "POST", "description": "Audio AST 추론"},
            {"path": "/test/predict/embedding", "method": "POST", "description": "임베딩 Mock"},
        ],
        "usage": {
            "insomnia": {
                "method": "POST",
                "url": "http://localhost:8000/test/predict/yolo",
                "body": "Multipart Form",
                "field": "file = 이미지 파일"
            }
        }
    }
