# ai/app/services/audio_service.py
"""
[역할 분담: 전체 파이프라인의 '관제탑']
- 본 파일은 오디오 분석의 전체 워크플로우를 관리하는 '오케스트레이터'입니다.
- 개별 모델의 세부 구현(Sliding Window 등)은 알지 못하며, 어떤 데이터를 누구에게 맡겨서 어떤 최종 응답을 만들지만 결정합니다.

[주요 책임]
1. Infrastructure: S3 URL 보안 검증(SSRF 방지), 오디오 다운로드 및 크기 제한
2. Signal: `audio_preprocessing.py`를 통한 전처리(노이즈/음성 제거) 정책 적용
3. Orchestration: AST 서비스 호출 및 결과 수신
4. Decision: 신뢰도 게이트 판정 및 LLM Fallback 실행 여부 결정
5. Data: 저신뢰 데이터에 대한 Active Learning(LLM Oracle) 기록 관리
"""
import os
import logging

# Logger 설정
logger = logging.getLogger(__name__)

from ai.app.services.audio.hertz import process_to_16khz
from ai.app.services.audio.ast_service import run_ast_inference
from ai.app.services.common.llm_service import analyze_audio_with_llm
from ai.app.schemas.audio_schema import AudioResponse, AudioDetail
import httpx
import librosa
import numpy as np
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
                
                # [Debug] Check if content is valid audio or S3 error
                sample = content[:100]
                logger.info(f"[Audio Debug] Downloaded {len(content)} bytes. Head: {sample}")
                if b"<Error>" in sample or b"<?xml" in sample:
                    logger.error(f"[Audio Debug] S3 Error suspected: {content.decode('utf-8', errors='ignore')}")
                
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
            logger.error(f"[Audio Service] 로드 실패: {e}")
            return AudioResponse(
                status="ERROR",
                analysis_type="IO",
                category="UNKNOWN_AUDIO",
                detail=AudioDetail(diagnosed_label="FAULTY_SOUND"),
                confidence=0.0
            )

        # 2. 전처리: 노이즈 필터링 파이프라인 (음성/잡음 제거)
        try:
            from ai.app.services.audio.audio_preprocessing import preprocess_audio_pipeline
            preprocessed_bytes, speech_ratio = await preprocess_audio_pipeline(audio_bytes, source_url=s3_url)
            logger.info(f"[Audio Service] 노이즈 필터링 완료 (원본: {len(audio_bytes)}B → 처리: {len(preprocessed_bytes)}B, 음성비율: {speech_ratio:.2%})")
        except Exception as e:
            logger.warning(f"[Audio Service] 전처리 실패 (Fallback to raw): {e}")
            preprocessed_bytes = audio_bytes
            speech_ratio = 0.0
        
        # 3. 16kHz 변환 (이미 전처리에서 완료되었으나 버퍼 형태로 변환)
        audio_buffer = io.BytesIO(preprocessed_bytes)
        
        # 3. 1차/2차 단일 PaSST 하이브리드 추론 (Stage 1: PaSST -> Stage 2: PaSST)
        logger.info(f"[Audio Service] PaSST 통합 계층형 추론 시작 (preprocessed: {len(preprocessed_bytes):,} bytes)")
        try:
            from ai.app.services.audio.passt_hierarchical_service import run_passt_inference
            ai_result = await run_passt_inference(audio_buffer)
            logger.info(f"[Audio Service] PaSST 추론 완료 (status={ai_result.status}, conf={ai_result.confidence})")
        except Exception as e:
            logger.error(f"[Audio Service] PaSST Inference Error: {e}")
            from ai.app.schemas.audio_schema import AudioResponse, AudioDetail
            ai_result = AudioResponse(
                status="UNKNOWN",
                analysis_type="PASST_FAILED",
                category="UNKNOWN_AUDIO",
                detail=AudioDetail(diagnosed_label="FAULTY_SOUND"),
                confidence=0.0,
                is_critical=False
            )
        
        # =================================================================
        # 🛡️ [Refinement] LLM Fallback (분석 거절 또는 저신뢰 시 LLM 투입)
        # =================================================================
        # 1) Stage 1에서 자동차 소리가 아니라고 판단했거나 (PASST_STAGE1_REJECT)
        # 2) AI 결과의 신뢰도가 낮은 경우 (0.85 미만)
        is_rejected = ai_result.analysis_type == "PASST_STAGE1_REJECT"
        is_low_confidence = ai_result.confidence < 0.85

        if is_rejected or is_low_confidence:
            logger.info(f"[Audio Service] LLM Fallback 기동 (Reject={is_rejected}, LowConf={is_low_confidence})")
            try:
                # LLM에게 오디오 분석 요청 (AudioResponse 객체 반환)
                llm_result = await analyze_audio_with_llm(s3_url, audio_bytes=audio_bytes)
                
                # AI 결과를 LLM의 더 똑똑한 해석으로 덮어씀 (객체 속성에 직접 접근)
                ai_result.status = llm_result.status
                ai_result.analysis_type = "LLM_FALLBACK"
                ai_result.category = llm_result.category
                ai_result.detail = llm_result.detail
                ai_result.confidence = llm_result.confidence
                ai_result.is_critical = llm_result.is_critical
                
                logger.info(f"[Audio Service] LLM Fallback 완료: {llm_result.status}, Category: {llm_result.category}")
            except Exception as e:
                logger.error(f"[Audio Service] LLM Fallback 실패 (AI 결과 유지): {e}")

        # 4. 최종 리포트 확정
        final_result = ai_result

        # =================================================================
        # [Active Learning] 공통 서비스 활용
        # =================================================================
        if final_result.confidence < 0.85:
            try:
                from ai.app.services.common.llm_service import generate_audio_labels
                from ai.app.services.common.active_learning_service import get_active_learning_service

                logger.info(f"[Active Learning] 저신뢰 오디오 감지 ({final_result.confidence:.2f}). LLM 라벨링 시작...")
                
                # Step 1: LLM Oracle
                oracle_labels = await generate_audio_labels(s3_url, audio_bytes=audio_bytes)
                status = oracle_labels.get("status", "")
                
                # Step 2: Quality Check
                if status == "RE_RECORD_REQUIRED" or status in ["UNKNOWN", "ERROR"] or not oracle_labels.get("label"):
                    logger.info(f"[Active Learning] 배제: 품질 미달 ({status})")
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
                logger.error(f"[Active Learning Audio] 기록 실패 (무시): {e}")
            
        return final_result

    async def get_mock_normal_data(self) -> AudioResponse:
        """테스트용 정상 데이터"""
        return AudioResponse(
            status="NORMAL",
            analysis_type="AST",
            category="ENGINE",
            detail=AudioDetail(diagnosed_label="NORMAL_SOUND"),
            confidence=0.99,
            is_critical=False
        )