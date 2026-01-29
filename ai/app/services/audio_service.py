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
    def __init__(self):
        # [Optimization] boto3 client는 Thread-safe하므로 초기화 시 한 번만 생성하여 재사용
        import boto3
        self.s3 = boto3.client('s3')

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
            
            if not is_allowed:
                # [Security] 정책 통일: Visual Service와 동일하게 Block
                if not hostname:
                     raise ValueError("Host not found in URL")
                raise ValueError(f"Blocked URL domain: {hostname}")

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
        # Threshold 상수 적용
        FAST_PATH_AUDIO_CONF = 0.85
        
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
        from ai.app.services.hertz import convert_bytes_to_16khz
        audio_buffer = await convert_bytes_to_16khz(audio_bytes)
        
        # 3. 1차 진단: AST 모델
        try:
            ast_result = await run_ast_inference(audio_buffer, ast_model_payload=ast_model)
        except Exception as e:
            print(f"[Audio Service] AST Inference Error: {e}")
            from ai.app.schemas.audio_schema import AudioResponse, AudioDetail
            ast_result = AudioResponse(
                status="UNKNOWN",
                analysis_type="AST_FAILED",
                category="UNKNOWN_AUDIO",
                detail=AudioDetail(diagnosed_label="Error", description="AST Model Failed"),
                confidence=0.0,
                is_critical=False
            )
        
        # 4. 2차 진단 판단 (Threshold 적용)
        if ast_result.confidence < FAST_PATH_AUDIO_CONF or ast_result.status == "UNKNOWN":
            print(f"[Audio Service] AST 결과 미흡 (또는 에러). LLM으로 전환.")
            wav_bytes = audio_buffer.getvalue() if audio_buffer else audio_bytes
            final_result = await analyze_audio_with_llm(s3_url, audio_bytes=wav_bytes)
        else:
            final_result = ast_result

        # =================================================================
        # [Active Learning] 공통 서비스 활용
        # =================================================================
        if final_result.confidence < 0.85:
            try:
                from ai.app.services.llm_service import generate_audio_labels
                from ai.app.services.active_learning_service import get_active_learning_service

                print(f"[Active Learning] 저신뢰 오디오 감지 ({final_result.confidence:.2f}). LLM 라벨링 시작...")
                
                # Step 1: LLM Oracle
                oracle_labels = await generate_audio_labels(s3_url, audio_bytes=audio_bytes)
                status = oracle_labels.get("status", "")
                
                # Step 2: Quality Check
                if status == "RE_RECORD_REQUIRED" or status in ["UNKNOWN", "ERROR"] or not oracle_labels.get("label"):
                    print(f"[Active Learning] 배제: 품질 미달 ({status})")
                    return final_result

                # Step 3: Save & Manifest (via Common Service)
                al_service = get_active_learning_service()
                label_key = al_service.save_oracle_label(
                    s3_url=s3_url, 
                    label_data=oracle_labels, 
                    domain="audio"
                )
                
                if label_key:
                    al_service.record_manifest(
                        s3_url=s3_url,
                        category=final_result.category,
                        label_key=label_key,
                        status=status,
                        confidence=final_result.confidence,
                        analysis_type=oracle_labels.get("label", "Unknown_Audio"), # 실제 라벨 전달
                        domain="audio"
                    )

            except Exception as e:
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