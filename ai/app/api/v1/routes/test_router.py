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
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from ai.app.services.local_service import process_visual_mock, process_audio_mock
from ai.app.schemas.visual_schema import VisualResponse, DetectionItem
from ai.app.schemas.audio_schema import AudioResponse
from ai.app.schemas.wear_factor import VehicleMetadata, DrivingHabits # 공통 메타데이터는 재사용
from pydantic import BaseModel, Field
from typing import List, Dict
from PIL import Image
import io
import os

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
    """
    import asyncio
    await asyncio.sleep(3)  # 실제 분석 시간을 시뮬레이션하기 위한 지연
    
    vehicle_id = data.get("vehicleId", "unknown")
    audio = data.get("analysis_results", {}).get("audioAnalysis") or data.get("audioAnalysis")
    visual = data.get("analysis_results", {}).get("visualAnalysis") or data.get("visualAnalysis")
    anomaly = data.get("analysis_results", {}).get("anomalyAnalysis") or data.get("anomalyAnalysis")
    rag_context = data.get("rag_context") or data.get("knowledgeData")
    
    print(f"[Comprehensive] Request for vehicle: {vehicle_id}")
    print(f"- Visual: {'YES' if visual else 'NO'}, Audio: {'YES' if audio else 'NO'}, Anomaly: {'YES' if anomaly else 'NO'}")

    # 케이스 1: 데이터가 너무 부족하여 추가 정보가 필요한 경우 (INTERACTIVE)
    if not audio and not visual and not anomaly:
        return {
            "response_mode": "INTERACTIVE",
            "confidence_level": "LOW",
            "summary": "차량 데이터가 부족하여 정확한 진단이 어렵습니다.",
            "report_data": None,
            "interactive_data": {
                "message": "안전한 진단을 위해 추가 정보가 필요합니다. 엔진룸 사진을 찍거나 소음을 녹음해 주세요.",
                "follow_up_questions": [
                    "이상 증상이 언제부터 시작되었나요?",
                    "최근에 경고등이 점등된 적이 있나요?"
                ],
                "requested_actions": ["CAPTURE_PHOTO", "RECORD_AUDIO"]
            },
            "disclaimer": "본 진단은 데이터 부족 상태에서의 추론이므로 참고용으로만 활용하세요."
        }

    # 케이스 2: 분석 결과가 존재할 때 (REPORT)
    # 실제로는 복합적인 로직이 들어가겠지만 Mock에서는 간단히 생성
    is_anomaly = anomaly.get("is_anomaly") if anomaly else False
    
    return {
        "response_mode": "REPORT",
        "confidence_level": "HIGH" if (audio and visual) else "MEDIUM",
        "summary": "차량 점검 결과 이상 징후가 감지되었습니다." if is_anomaly else "차량 전반적인 상태는 양호합니다.",
        "report_data": {
            "suspected_causes": [
                {
                    "cause": "냉각 계통 점검 필요" if is_anomaly else "소모품 관리",
                    "basis": "OBD 수온 이상 감지" if is_anomaly else "정기 점검 주기 도달",
                    "source_type": "CONFIRMED" if is_anomaly else "INFERRED",
                    "reliability": "HIGH"
                }
            ],
            "final_guide": "가까운 정비소를 방문하여 냉각수 및 벨트 상태를 점검받으시길 권장합니다." if is_anomaly else "정기적인 소모품 교체 외에는 특이사항이 없습니다."
        },
        "interactive_data": None,
        "disclaimer": "본 진단은 2010~2013년식 매뉴얼 및 AI 추론에 기반하며, 실제 정비 전문가의 의견과 다를 수 있습니다."
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
async def analyze_yolo_local(file: UploadFile = File(...)):
    """
    [ISC - Real YOLO + Real PatchCore] 로컬 이미지 → 실제 파이프라인 (S3/LLM 제외)
    
    프로덕션 (/predict/engine)과 동일한 로직:
    - YOLO: 엔진 부품 탐지
    - Crop: 부품별 이미지 추출
    - Anomaly (PatchCore): 이상 탐지
    - LLM: 건너뜀 (테스트용)
    """
    import tempfile
    import asyncio
    from dataclasses import asdict
    
    try:
        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Image file required")
        
        content = await file.read()
        image = Image.open(io.BytesIO(content))
        
        if image.mode != "RGB":
            image = image.convert("RGB")
        
        # 1. YOLO 추론 (로컬 이미지 버전)
        from ultralytics import YOLO
        
        model_path = "ai/weights/engine/best.pt"
        if not os.path.exists(model_path):
            # 모델 없으면 기본 모델 사용
            from ultralytics import YOLO as BaseYOLO
            model = BaseYOLO("yolov8n.pt")
            print(f"[Warning] 학습 모델 없음. 기본 모델 사용")
        else:
            model = YOLO(model_path)
        
        tmp_path = os.path.join(tempfile.gettempdir(), f"yolo_test_{os.getpid()}.jpg")
        image.save(tmp_path, "JPEG")
        
        try:
            yolo_results = model.predict(source=tmp_path, conf=0.25, save=False)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        
        # YOLO 결과 파싱
        detections = []
        for r in yolo_results:
            for box in r.boxes:
                label_idx = int(box.cls[0])
                label_name = model.names[label_idx]
                confidence = float(box.conf[0])
                bbox = box.xyxy[0].tolist()  # [x1, y1, x2, y2]
                
                detections.append({
                    "label": label_name,
                    "confidence": round(confidence, 3),
                    "bbox": [int(v) for v in bbox]
                })
        
        # 신뢰도 낮은 탐지 필터링 (오탐 방지)
        MIN_CONFIDENCE = 0.5
        detections = [d for d in detections if d["confidence"] >= MIN_CONFIDENCE]
        
        # Path B: 부품 미감지
        if len(detections) == 0:
            return JSONResponse(content={
                "status": "SUCCESS",
                "path": "B",
                "source": f"uploaded:{file.filename}",
                "vehicle_type": None,
                "parts_detected": 0,
                "message": "엔진룸 부품을 감지하지 못했습니다. 선명한 이미지로 재촬영해주세요."
            })
        
        # Path A: 부품별 분석
        EV_PARTS = {"Inverter", "Electric_Motor", "Charging_Port", "Inverter_Coolant_Reservoir"}
        detected_labels = [d["label"] for d in detections]
        is_ev = any(part in EV_PARTS for part in detected_labels)
        vehicle_type = "EV" if is_ev else "ICE"
        
        # 2. Crop + PatchCore Anomaly Detection (싱글톤 사용)
        anomaly_detector = get_anomaly_detector()
        
        results = []
        anomaly_count = 0
        
        for det in detections:
            # Crop 이미지 추출
            x1, y1, x2, y2 = det["bbox"]
            crop_img = image.crop((x1, y1, x2, y2))
            
            # PatchCore 이상 탐지
            anomaly_result = await anomaly_detector.detect(crop_img, det["label"])
            
            is_anomaly = bool(anomaly_result.is_anomaly)
            if is_anomaly:
                anomaly_count += 1
                defect_info = {
                    "defect_category": "ANOMALY",
                    "defect_label": f"{det['label']}_Anomaly",
                    "description": f"{det['label']}에서 이상이 감지되었습니다. (Score: {anomaly_result.score:.2f})",
                    "severity": "WARNING" if anomaly_result.score < 0.8 else "CRITICAL",
                    "recommended_action": "정비소 점검 권장"
                }
            else:
                defect_info = {
                    "defect_category": "NORMAL",
                    "defect_label": "Normal",
                    "description": f"{det['label']}은(는) 정상 상태입니다.",
                    "severity": "NORMAL",
                    "recommended_action": "조치 불필요"
                }
            
            results.append({
                "part_name": det["label"],
                "bbox": det["bbox"],
                "confidence": det["confidence"],
                "is_anomaly": is_anomaly,
                "anomaly_score": round(anomaly_result.score, 4),
                "threshold": anomaly_result.threshold,
                **defect_info
            })
        
        return JSONResponse(content={
            "status": "SUCCESS",
            "path": "A",
            "source": f"uploaded:{file.filename}",
            "vehicle_type": vehicle_type,
            "parts_detected": len(detections),
            "anomalies_found": anomaly_count,
            "results": results
        })
        
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
