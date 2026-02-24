# ai/app/services/ast_service.py
"""
[역할 분담: AST 모델의 '뇌']
- 본 파일은 오직 "AST 모델 추론"에만 집중합니다.
- 이미 준비된(전처리된) 오디오를 받아서 Sliding Window -> AST 추론 -> Max Aggregation 과정을 거쳐 결과를 도출합니다.
- S3, LLM Fallback, 전처리 정책(DSP) 등 외부 비즈니스 로직은 전혀 알지 못하며, 오직 모델 입력 규격과 판단에만 충실합니다.

[주요 책임]
1. 5초 Sliding Window (Stride 40%) 생성: 모델 입력 규격을 맞추기 위한 로직
2. AST Feature Extractor & Model Inference (Batch 처리)
3. Chunk Aggregation (Max Pooling): 전체 오디오 중 가장 확실한 결함 포착
4. 신뢰도 기반 상태 결정 (Strict Normal Check)
"""
import torch
from transformers import ASTForAudioClassification, ASTFeatureExtractor
import os
import librosa
import torch.nn.functional as F
from ai.app.schemas.audio_schema import AudioResponse, AudioDetail

# =============================================================================
# [설정] 모델 경로
# =============================================================================
MODEL_PATH = "ai/weights/audio/best_ast_model"

# =============================================================================
# [정상 소리 라벨] - 이 라벨들은 NORMAL 상태로 처리됩니다
# =============================================================================
NORMAL_LABELS = {
    "normal",     # 정상 소리
}

# =============================================================================
# [결함 라벨 → 카테고리 매핑]
# 새 데이터셋 기준: engine, brake, starter, normal
# =============================================================================
LABEL_TO_CATEGORY = {
    "normal": "NORMAL",
    "engine": "ENGINE",
    "brake": "BRAKES",
    "starter": "STARTER",
}

LABEL_TO_DESCRIPTION = {
    "normal": "정상적인 차량 소리입니다.",
    "engine": "엔진 관련 이상 소음이 감지되었습니다. 점검이 필요합니다.",
    "brake": "브레이크 관련 이상 소음이 감지되었습니다. 즉시 점검이 필요합니다.",
    "starter": "시동 관련 이상 소음이 감지되었습니다. 배터리 및 스타터 모터 점검이 필요합니다.",
}

# =============================================================================
# [자동 카테고리 매핑 함수]
# =============================================================================
def get_category_from_label(label_name: str) -> str:
    """
    라벨 이름에서 카테고리 추출
    
    새 데이터셋 라벨: normal, engine, brake, starter
    """
    label_lower = label_name.lower()
    return LABEL_TO_CATEGORY.get(label_lower, "ENGINE")


def get_description_from_label(label_name: str) -> str:
    """라벨에 해당하는 설명 반환"""
    label_lower = label_name.lower()
    return LABEL_TO_DESCRIPTION.get(label_lower, "차량 소음 분석이 필요합니다.")

# =============================================================================
# 추론 함수
# =============================================================================
async def run_ast_inference(processed_audio_buffer, ast_model_payload=None) -> AudioResponse:
    """16kHz WAV 버퍼를 받아 AST 모델로 소리 분류 (Async Wrapper)"""
    import asyncio
    loop = asyncio.get_running_loop()

    # 모델 미로드 시 Mock 응답
    if ast_model_payload is None:
        print("[AST Service] Model payload is None! Returning Mock Response.")
        label_name = "Engine_Knocking"
        category = get_category_from_label(label_name)
        
        return AudioResponse(
            status="FAULTY",
            analysis_type="AST_MOCK",
            category=category,
            data=AudioDetail(
                diagnosed_label=label_name,
                description="테스트용: 엔진 노킹 소음 감지 (Mock)"
            ),
            confidence=0.95,
            is_critical=True
        )

    model = ast_model_payload.get("model")
    feature_extractor = ast_model_payload.get("feature_extractor")

    if model is None or feature_extractor is None:
        print("[AST Service] Model or FeatureExtractor is None! Returning Mock Response.")
        return AudioResponse(status="ERROR", analysis_type="AST", category="ERROR", data=AudioDetail(diagnosed_label="Error", description="Model not loaded"), confidence=0, is_critical=False)

    # =========================================================================
    # 실제 추론 로직 (동기 함수) - Sliding Window 적용
    # =========================================================================
    def _sync_inference(audio_buffer):
        try:
            # 1. 오디오 로드 (16kHz)
            print("[AST Inference] 오디오 로드 시작...")
            audio_buffer.seek(0)
            audio_array, sr = librosa.load(audio_buffer, sr=16000)
            print(f"[AST Inference] 오디오 로드 완료: {len(audio_array)/sr:.2f}s")
            
            # 2. Sliding Window 설정 (5초 윈도우, Stride 40%)
            window_size = 16000 * 5
            stride = int(window_size * 0.4)
            
            if len(audio_array) < window_size:
                chunks = [librosa.util.fix_length(audio_array, size=window_size)]
            else:
                chunks = []
                for start in range(0, len(audio_array) - window_size + 1, stride):
                    chunks.append(audio_array[start:start + window_size])
                if len(audio_array) > window_size and (len(audio_array) - window_size) % stride != 0:
                    chunks.append(audio_array[-window_size:])
            
            # [성능] 실제 5초 클립 균등 선택 (주파수 왜곡 없음)
            # - 시간 압축 X → 소리 특성 그대로 보존
            # - 전/중/후 구간에서 대표 클립을 고르게 추출
            MAX_CHUNKS = 13  # 최대 13개 (= MAX_CHUNKS * 5초 ≈ 65초치 커버)
            if len(chunks) > MAX_CHUNKS:
                step = len(chunks) / MAX_CHUNKS
                chunks = [chunks[int(i * step)] for i in range(MAX_CHUNKS)]
                print(f"[AST Inference] 대표 클립 {len(chunks)}개 선택 (오디오 전체 커버, 주파수 보존)")
            else:
                print(f"[AST Inference] Sliding Window 완료: {len(chunks)}개 청크")
            
            # 3. Batch Inference (성능 최적화)
            print(f"[AST Inference] Feature Extraction 시작 ({len(chunks)}개 청크)...")
            inputs = feature_extractor(
                chunks, 
                sampling_rate=16000, 
                return_tensors="pt", 
                padding="max_length"
            )
            
            print("[AST Inference] Feature Extraction 완료")
            print(f"[AST Inference] 모델 추론 시작 (batch_size={len(chunks)})...")
            with torch.no_grad():
                outputs = model(**inputs)
                logits = outputs.logits
                # [Optimization] probs (n_chunks, n_classes)는 추후 Heatmap/Localization에 활용 가능
                probs = F.softmax(logits, dim=-1)
            print("[AST Inference] 모델 추론 완료")
            
            # 4. Aggregation: Max Pooling across time (결함 감지 확률 극대화)
            max_probs, _ = torch.max(probs, dim=0)
            
            # 최종 스코어 및 ID 추출
            confidence = max_probs.max().item()
            predicted_id = max_probs.argmax().item()
            label_name = model.config.id2label[predicted_id]
            label_lower = label_name.lower()

            # 5. 상태 결정 로직 정교화
            # [Refinement] AST는 소음 환경에서 낮은 confidence(0.4대)를 보일 때가 많으므로 임계값 하향
            if confidence < 0.4:
                status = "UNKNOWN"
                category = "UNKNOWN_SOUND"
                diagnosed_label = "FAULTY_SOUND" # 보수적 접근
                is_critical = False
            
            # [Refinement] NORMAL 판단: 전체 max가 normal이면서, normal 확신도가 높을 때만 (False Normal 방지)
            else:
                defect_scores = []
                for name, idx in model.config.label2id.items():
                    if name.lower() != "normal":
                        defect_scores.append(max_probs[idx].item())
                
                if label_lower == "normal" and confidence > 0.6 and (not defect_scores or confidence > max(defect_scores)):
                    status = "NORMAL"
                    category = get_category_from_label(label_name)
                    diagnosed_label = "NORMAL_SOUND"
                    is_critical = False
                else:
                    status = "CRITICAL"
                    category = get_category_from_label(label_name)
                    diagnosed_label = "FAULTY_SOUND"
                    is_critical = True
            
            # 6. Build probability map for all_probs
            all_probs_map = {}
            for name, idx in model.config.label2id.items():
                all_probs_map[name.lower()] = float(max_probs[idx].item())

            return AudioResponse(
                status=status,
                analysis_type="AST_WINDOW",
                category=category,
                detail=AudioDetail(
                    diagnosed_label=diagnosed_label
                ),
                confidence=round(confidence, 4),
                is_critical=is_critical
            )
            
        except Exception as e:
            print(f"[AST Inference Error] {e}")
            return AudioResponse(
                status="UNKNOWN",
                analysis_type="AST",
                category="UNKNOWN_AUDIO",
                detail=AudioDetail(
                    diagnosed_label="FAULTY_SOUND"
                ),
                confidence=0.0,
                is_critical=False
            )

    # 별도 스레드에서 실행
    return await loop.run_in_executor(None, _sync_inference, processed_audio_buffer)
