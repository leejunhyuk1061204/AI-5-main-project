# ai/app/services/audio_service.py
"""
통합 오디오 분석 서비스 (Audio Orchestrator)

[역할]
1. 오디오 데이터 로드: S3 URL로부터 오디오 파일을 다운로드하고, SSRF 공격을 방지하기 위해 도메인을 검증합니다.
2. 오디오 전처리: 분석에 적합하도록 16kHz WAV 포맷으로 변환합니다.
3. 지능형 진단: AST(Audio Spectrogram Transformer) 모델과 LLM(Audio Vision)을 연동하여 기계 결함 소음을 분석합니다.

[주요 기능]
- 오디오 정밀 진단 (get_audio_diagnosis)
- 안전한 오디오 로딩 및 전처리 (_safe_load_audio)
- AST 및 LLM 기반 복합 분석 수행
"""
import os
from ai.app.services.hertz import process_to_16khz
from ai.app.services.ast_service import run_ast_inference
from ai.app.services.llm_service import analyze_audio_with_llm
from ai.app.services.audio_enhancement import denoise_audio
from ai.app.schemas.audio_schema import AudioResponse, AudioDetail
import httpx
import io
import re
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

MAX_AUDIO_SIZE = 10 * 1024 * 1024  # 10MB

class AudioService:
    async def _safe_load_audio(self, url: str) -> bytes:
        """
        오디오 파일을 안전하게 로드 (SSRF 방지 및 크기 제한)
        """
        try:
            parsed = urlparse(url)
            hostname = parsed.hostname or ""
            
            # 1. SSRF 검증
            blocked_patterns = [
                r"localhost", r"127\.0\.0\.\d+", r"10\.\d+\.\d+\.\d+",
                r"172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+", r"192\.168\.\d+\.\d+",
                r"169\.254\.\d+\.\d+", r"0\.0\.0\.0",
            ]
            for pattern in blocked_patterns:
                if re.match(pattern, hostname, re.IGNORECASE):
                    raise ValueError(f"Blocked URL domain: {hostname}")
            
            is_allowed = False
            for allowed_pattern in ALLOWED_DOMAINS:
                if re.match(allowed_pattern, hostname, re.IGNORECASE):
                    is_allowed = True
                    break
            
            if not is_allowed and hostname:
                 # S3 외 도메인은 경고 로깅 후 진행 (필요시 엄격하게 block)
                 print(f"[Safe Audio Load] Warning: External domain {hostname}")

        except Exception as e:
            raise ValueError(f"Audio URL Validation Error: {e}")

        # 2. 다운로드
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.get(url)
                response.raise_for_status()
                content = response.content
                
                if len(content) > MAX_AUDIO_SIZE:
                    raise ValueError("Audio file too large")
                return content
            except Exception as e:
                raise ValueError(f"Failed to download audio: {e}")

    async def predict_audio_smart(self, s3_url: str, ast_model=None) -> AudioResponse:
        """
        통합 오디오 분석 흐름
        1. 안전하게 다운로드 (중앙화)
        2. 16kHz 전처리
        3. AST/LLM 추론
        """
        # 1. 중앙화된 오디오 로드
        try:
            audio_bytes = await self._safe_load_audio(s3_url)
        except Exception as e:
            print(f"[Audio Service] 로드 실패: {e}")
            return AudioResponse(
                status="ERROR",
                analysis_type="IO",
                category="UNKNOWN_AUDIO",
                detail=AudioDetail(diagnosed_label="Load Error", description=str(e)),
                confidence=0.0
            )

        # 2. 전처리: 16kHz 변환
        # 기존 process_to_16khz는 URL을 받으므로, 바이트를 넘기거나 URL을 그대로 쓰되 다운로드는 안하게 내부 수정 필요
        # 일단은 기존 구조 유지를 위해 URL을 넘기되, 내부에서 다운로드 중복 체크를 하게 하거나 
        # (이번 태스크에서는 audio_buffer를 이미 확보했다고 가정하고 넘기는게 정석)
        # 헤르즈.py를 수정하기보다 여기서 바로 buffer를 만들어 넘깁니다.
        from ai.app.services.hertz import convert_bytes_to_16khz
        audio_buffer = convert_bytes_to_16khz(audio_bytes)
        
        if not audio_buffer is None: # audio_buffer is np.ndarray from hertz
             # [Enhancement] 전처리: 소음 제거 (U-Net Denoising)
             try:
                 audio_buffer = await denoise_audio(audio_buffer)
             except Exception as e:
                 print(f"[Audio Service] Denoising 실패 (Pass-through): {e}")

        # 2. 1차 진단: AST 모델
        ast_result = await run_ast_inference(audio_buffer, ast_model_payload=ast_model)
        
        # 3. 2차 진단 판단
        if ast_result.confidence < 0.85 or ast_result.status == "UNKNOWN":
            print(f"[Audio Service] AST 결과 미흡. LLM으로 전환.")
            final_result = await analyze_audio_with_llm(s3_url, audio_bytes=audio_bytes)
        else:
            final_result = ast_result

        # =================================================================
        # [Active Learning] 모델 재학습을 위한 오디오 데이터 수집
        # =================================================================
        # 왜 저신뢰 데이터만 수집하는가?
        # → 고신뢰(≥0.9): AST 모델이 이미 잘 분류함 → 재학습 효과 없음
        # → 저신뢰(<0.9): 모델이 헷갈려하는 소리 → 이걸 학습해야 실력이 늘음
        #
        # [저장 조건] - 두 가지 모두 충족해야 저장
        # 1. 신뢰도 < 0.9 (모델이 불확실한 데이터)
        # 2. 품질 통과 (정상적인 오디오, 분석 가능한 상태)
        #
        # [배제 조건] - 재학습해도 도움 안 되는 데이터
        # - status == "RE_RECORD_REQUIRED": 소음 과다 (바람소리, 지하철 등)
        # - status == "UNKNOWN": 차량 소리인지 구분 불가
        # - status == "ERROR": LLM 분석 자체가 실패
        #
        # [S3 저장 경로]
        # - dataset/audio/llm_confirmed/{file_id}.json
        # - 예: dataset/audio/llm_confirmed/engine_sound_001.json
        # =================================================================
        if final_result.confidence < 0.9:
            try:
                # 필요한 모듈 임포트 (함수 내부에서 하여 순환 참조 방지)
                from ai.app.services.manifest_service import add_audio_entry
                from ai.app.services.llm_service import generate_audio_labels
                import boto3
                import json

                print(f"[Active Learning] 저신뢰 오디오 감지 ({final_result.confidence:.2f} < 0.9). LLM 오디오 라벨링 시작...")
                
                # =================================================================
                # Step 1: LLM에게 정답 라벨 생성 요청 (Oracle)
                # =================================================================
                # LLM(GPT-4o Audio)이 소리를 듣고 어떤 종류의 소리인지 분류
                # 반환값 예시:
                # {
                #   "label": "Engine_Knock",
                #   "category": "ENGINE",
                #   "status": "FAULTY",
                #   "confidence": 0.85
                # }
                oracle_labels = await generate_audio_labels(s3_url, audio_bytes=audio_bytes)
                
                # =================================================================
                # Step 2: 품질 필터링 - 재학습 가치 없는 데이터 배제
                # =================================================================
                status = oracle_labels.get("status", "")
                
                # [배제 1] 소음 과다 - 재녹음 필요
                # 예: 바람소리, 지하철 소음 등으로 엔진 소리가 안 들림
                if status == "RE_RECORD_REQUIRED":
                    print(f"[Active Learning] 배제: 소음 과다 (재녹음 필요)")
                    return final_result  # 저장하지 않고 결과만 반환
                
                # [배제 2] 분석 불가 상태
                # 예: 너무 짧거나, 무음이거나, 차량 소리인지 구분 불가
                if status in ["UNKNOWN", "ERROR"]:
                    print(f"[Active Learning] 배제: 분석 불가 상태 ({status})")
                    return final_result  # 저장하지 않고 결과만 반환
                
                # [배제 3] 라벨이 없는 경우
                # 예: LLM도 어떤 소리인지 분류 못함
                if not oracle_labels.get("label"):
                    print(f"[Active Learning] 배제: 라벨 없음")
                    return final_result  # 저장하지 않고 결과만 반환
                
                # =================================================================
                # Step 3: 품질 통과 → S3에 라벨 JSON 저장
                # =================================================================
                # AWS S3 클라이언트 생성 (환경변수에서 자격증명 자동 로드)
                s3 = boto3.client('s3')
                
                # 버킷 이름: 환경변수에 없으면 기본값 사용
                bucket = os.getenv("S3_BUCKET_NAME", "car-sentry-data")
                
                # 파일 ID 추출: "engine_sound_001.wav" → "engine_sound_001"
                file_id = os.path.basename(s3_url).split('.')[0]
                
                # 저장 경로: dataset/llm_confirmed/audio/{file_id}.json
                retraining_label_key = f"dataset/llm_confirmed/audio/{file_id}.json"
                
                # S3에 JSON 파일 업로드
                s3.put_object(
                    Bucket=bucket,
                    Key=retraining_label_key,
                    Body=json.dumps(oracle_labels, ensure_ascii=False, indent=2),
                    ContentType='application/json'
                )
                print(f"[Active Learning] 오디오 고품질 정답지 저장 완료: {retraining_label_key}")

                # =================================================================
                # Step 4: Manifest에 기록 (데이터 목록 관리용)
                # =================================================================
                # Manifest = 어떤 데이터가 수집되었는지 목록을 관리하는 JSON 파일
                # 나중에 재학습 시 이 목록을 보고 데이터를 불러옴
                add_audio_entry(
                    original_url=s3_url,                  # 원본 오디오 S3 위치
                    category=final_result.category,       # ENGINE, BRAKES 등
                    diagnosed_label=oracle_labels.get("label"),  # LLM이 분류한 라벨
                    status=status,                        # NORMAL, FAULTY 등
                    analysis_type="LLM_ORACLE",           # LLM이 생성한 정답임을 표시
                    confidence=final_result.confidence    # 원래 AST 모델의 신뢰도
                )
                print(f"[Manifest] 오디오 분석 이력 기록 완료: {s3_url}")

            except Exception as e:
                # Active Learning 실패해도 메인 분석에는 영향 없음
                print(f"[Active Learning Audio] 기록 실패 (무시): {e}")
            
        return final_result

    async def get_mock_normal_data(self) -> AudioResponse:
        """테스트용 정상 데이터"""
        return AudioResponse(
            status="NORMAL",
            analysis_type="AST",
            category="ENGINE",
            detail=AudioDetail(diagnosed_label="NORMAL", description="정상입니다."),
            confidence=0.99,
            is_critical=False
        )