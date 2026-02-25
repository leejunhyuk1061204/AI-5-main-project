# ai/app/services/audio/passt_hierarchical_service.py
"""
[단일 PaSST 하이브리드 오디오 추론 서비스]
이 모듈은 최고 성능의 PaSST 트랜스포머 아키텍처 하나로 1단계(필터)와 2단계(정밀진단)를 모두 수행합니다.
- Stage 1 (필터): PaSST 기반 (자동차 소리인지, 잡음/단순 말소리인지 고정밀 구분)
- Stage 2 (전문의): PaSST 기반 결함 진단 (엔진/브레이크/스타터 등 세부 결함 정밀 분석)

* 각 가중치(Stage 1, Stage 2)는 서버 구동 시 단 1번만 메모리에 로드되어 실시간 처리에 최적화됩니다.
"""

import torch
import torch.nn.functional as F
import librosa
import asyncio
import os
import numpy as np

# 모델 아키텍처를 불러옵니다 (가중치 파일이 아니라 뼈대(Class)를 불러오는 것)
from ai.scripts.audio.train_car_hierarchical import HierarchicalMoEPipeline
from ai.app.schemas.audio_schema import AudioResponse, AudioDetail

# ---------------------------------------------------------
# 글로벌 캐시 설정: FastAPI 서버 구동 중 내내 메모리에 상주할 두 개의 뇌
# ---------------------------------------------------------
_MODEL_STAGE1_PASST = None  # PaSST (문지기) 
_MODEL_STAGE2_PASST = None  # PaSST (전임의사)
DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

def _load_passt_models():
    """서버 기동 시 최초 1회만 두 가중치를 각각 메모리에 올리는 함수"""
    global _MODEL_STAGE1_PASST, _MODEL_STAGE2_PASST
    
    # 📌 가중치 파일 경로 설정 (지정된 weights 폴더)
    weights_dir = os.path.join(os.getcwd(), "ai", "weights", "audio")
    s1_weights_path = os.path.join(weights_dir, "hier_s1_passt.pt")
    s2_weights_path = os.path.join(weights_dir, "hier_s2_passt.pt")
    
    # [1단계 뇌 로드] PaSST (Stage 1 필터용)
    if _MODEL_STAGE1_PASST is None:
        print("🧠 [PaSST Audio] 1단계 정밀 문지기 가중치 메모리 로드 중...")
        _MODEL_STAGE1_PASST = HierarchicalMoEPipeline("passt").to(DEVICE)
        if os.path.exists(s1_weights_path):
            _MODEL_STAGE1_PASST.load_state_dict(torch.load(s1_weights_path, map_location=DEVICE))
            print("✅ 1단계 PaSST 가중치 로드 완료")
        else:
            print(f"⚠️ [경고] 1단계 가중치를 찾을 수 없습니다: {s1_weights_path}")
        _MODEL_STAGE1_PASST.eval()  # 추론 모드 고정
        
    # [2단계 뇌 로드] PaSST (Stage 2 결함진단용)
    if _MODEL_STAGE2_PASST is None:
        print("🧠 [PaSST Audio] 2단계 전문의 모델(PaSST) 메모리 로드 중...")
        _MODEL_STAGE2_PASST = HierarchicalMoEPipeline("passt").to(DEVICE)
        if os.path.exists(s2_weights_path):
            _MODEL_STAGE2_PASST.load_state_dict(torch.load(s2_weights_path, map_location=DEVICE))
            print("✅ 2단계 PaSST 가중치 로드 완료")
        else:
            print(f"⚠️ [경고] 2단계 가중치를 찾을 수 없습니다: {s2_weights_path}")
        _MODEL_STAGE2_PASST.eval()  # 추론 모드 고정

async def run_passt_inference(audio_buffer) -> AudioResponse:
    """FastAPI 이벤트 루프가 멈추지 않게 비동기(Async) 래퍼로 씌움"""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_passt_inference, audio_buffer)

def _sync_passt_inference(audio_buffer) -> AudioResponse:
    """실제 하이브리드(PaSST -> PaSST) 2단계 추론이 일어나는 동기(Sync) 로직"""
    # 1. 모델이 없으면 로드합니다.
    _load_passt_models()
    
    try:
        # ---------------------------------------------------------
        # [데이터 준비] S3에서 다운받은 버퍼를 Librosa로 32kHz 로드 (PaSST 최적화 속도)
        # ---------------------------------------------------------
        audio_buffer.seek(0)
        # 주의: PaSST의 내부 백본은 32000Hz 입력을 선호하므로 전처리 과정에서 32kHz로 잡습니다.
        audio_array, sr = librosa.load(audio_buffer, sr=32000)
        
        # ---------------------------------------------------------
        # [공통 전처리] 5초 Sliding Window 자르기 (Stride 40%)
        # ---------------------------------------------------------
        target_seconds = 5.0
        window_size = int(32000 * target_seconds)
        stride = int(window_size * 0.4)
        
        if len(audio_array) < window_size:
            chunks = [librosa.util.fix_length(audio_array, size=window_size)]
        else:
            chunks = []
            for start in range(0, len(audio_array) - window_size + 1, stride):
                chunks.append(audio_array[start:start + window_size])
            if len(audio_array) > window_size and (len(audio_array) - window_size) % stride != 0:
                chunks.append(audio_array[-window_size:])
                
        # 파이토치 텐서[Batch, Length]로 변환 후 GPU/CPU 전송
        inputs = torch.tensor(np.array(chunks), dtype=torch.float32).to(DEVICE)
        
        
        # =========================================================
        # 🛡️ 1단계 추론: PaSST 정밀 문지기 통과 (Car vs OOD)
        # =========================================================
        with torch.no_grad():
            res_s1 = _MODEL_STAGE1_PASST(inputs, stage=1)
            probs_s1 = F.softmax(res_s1, dim=1)
            max_probs_s1, _ = torch.max(probs_s1, dim=0) 
            
        stage1_pred = max_probs_s1.argmax().item()
        
        # 1: OOD (Out of Distribution, 비-자동차 소음)
        # [Refinement] 단순 argmax가 아닌, 자동차 소리에 대한 확신도가 일정 수준(예: 80%) 이상일 때만 통과
        car_conf = probs_s1[0, 0].item()
        ood_conf = probs_s1[0, 1].item()
        
        if stage1_pred == 1 or car_conf < 0.80:
            reason = "OOD_DETECTED" if stage1_pred == 1 else "LOW_CAR_CONFIDENCE"
            print(f"🛑 [Stage 1 Reject] 자동차 소리가 아님. (Reason: {reason}, Car Conf: {car_conf:.4f}, OOD Conf: {ood_conf:.4f})")
            return AudioResponse(
                status="UNKNOWN",
                analysis_type="PASST_STAGE1_REJECT",
                category="UNKNOWN_AUDIO",
                detail=AudioDetail(diagnosed_label="NON_CAR_SOUND"),
                confidence=car_conf,
                is_critical=False
            )
            
            
        # =========================================================
        # 🩺 2단계 추론: PaSST 전문의 정밀 진단 (Normal vs Abnormal)
        # =========================================================
        with torch.no_grad():
            logits, gate_weights, gate_logits = _MODEL_STAGE2_PASST(inputs, stage=2)
            probs_s2 = F.softmax(logits, dim=1)
            
            # 결함의 특징(Abnormal)이 가장 강하게 감지된 청크를 기준으로 삼음 (Max Pooling)
            max_probs_s2, _ = torch.max(probs_s2, dim=0)
            
        stage2_pred = max_probs_s2.argmax().item()
        confidence = max_probs_s2[stage2_pred].item()
        
        # Router 결정을 평균 내어 이 소리가 [시동 / 엔진 / 브레이크] 중 어느 도메인인지 판별
        avg_gate = gate_weights.mean(dim=0)
        domain_idx = avg_gate.argmax().item()
        domain_map = {0: "STARTER", 1: "ENGINE", 2: "BRAKES"}
        category = domain_map.get(domain_idx, "ENGINE")
        
        # 0: 정상 (Normal)
        if stage2_pred == 0:
            print(f"✅ [Stage 2 Normal] 정상 차량 소음. (Category: {category}, Confidence: {confidence:.4f})")
            return AudioResponse(
                status="NORMAL",
                analysis_type="ENG_B_PASST",
                category=category,
                detail=AudioDetail(diagnosed_label="NORMAL_SOUND"),
                confidence=round(confidence, 4),
                is_critical=False
            )
        # 1: 비정상 (Faulty)
        else:
            print(f"🚨 [Stage 2 Faulty] 결함 소음 감지! (Category: {category}, Confidence: {confidence:.4f})")
            return AudioResponse(
                status="CRITICAL",
                analysis_type="ENG_B_PASST",
                category=category,
                detail=AudioDetail(diagnosed_label="FAULTY_SOUND"),
                confidence=round(confidence, 4),
                is_critical=True
            )
            
    except Exception as e:
        print(f"❌ [PaSST Inference Error] {e}")
        import traceback
        traceback.print_exc()
        return AudioResponse(
            status="UNKNOWN",
            analysis_type="PASST_ERROR",
            category="UNKNOWN_AUDIO",
            detail=AudioDetail(diagnosed_label="FAULTY_SOUND"),
            confidence=0.0,
            is_critical=False
        )
