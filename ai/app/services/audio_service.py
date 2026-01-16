# app/services/audio_service.py
import os
from ai.app.services.hertz import process_to_16khz
from ai.app.services.ast_service import run_ast_inference
from ai.app.services.llm_service import analyze_audio_with_llm
from ai.app.schemas.audio_schema import AudioResponse, AudioDetail

class AudioService:
    async def predict_audio_smart(self, s3_url: str, ast_model=None) -> AudioResponse:
        """
        16kHz 전처리 -> AST 분류 -> LLM 정밀 진단 통합 흐름
        """
        # 1. 전처리: 16kHz 변환 (헤르즈.py 호출)
        audio_buffer = process_to_16khz(s3_url)
        
        if not audio_buffer:
            # 변환 실패 시 바로 LLM 시도
            return await analyze_audio_with_llm(s3_url)

        # 2. 1차 진단: AST 모델
        ast_result = await run_ast_inference(audio_buffer, ast_model_payload=ast_model)
        
        # 3. 2차 진단 판단: 신뢰도가 낮거나(0.85 미만) 결과가 UNKNOWN일 때 LLM 호출
        if ast_result.confidence < 0.85 or ast_result.status == "UNKNOWN":
            print(f"[Audio Service] AST 결과 미흡 (신뢰도: {ast_result.confidence}). LLM으로 전환.")
            final_result = await analyze_audio_with_llm(s3_url)
        else:
            final_result = ast_result

        # [Active Learning] 데이터 수집 필터링
        # 1. 신뢰도가 너무 낮으면(0.9 미만) 학습 데이터로 쓰지 않음 (쓰레기 데이터 방지)
        # 2. 재녹음 요구(RE_RECORD_REQUIRED)는 당연히 제외
        if final_result.confidence >= 0.9 and final_result.status != "RE_RECORD_REQUIRED":
            print(f"[Data Collection] 유효한 데이터 수집됨! (Confidence: {final_result.confidence})")
            
            import boto3
            import uuid
            from datetime import datetime
            
            s3_client = boto3.client('s3')
            BUCKET_NAME = "your-bucket-name"  # 중요! TODO: 실제 버킷 이름으로 변경 ###
            
            # 카테고리별 폴더 구조: dataset/audio/{CATEGORY}/{filename}.{ext}
            category = final_result.category  # ENGINE, SUSPENSION, BRAKES 등
            unique_id = str(uuid.uuid4())[:8]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 원본 파일 확장자 추출 (mp3, wav, m4a 등)
            from urllib.parse import urlparse
            url_path = urlparse(s3_url).path
            file_ext = os.path.splitext(url_path)[1].lower() or ".wav"
            
            s3_key = f"dataset/audio/{category}/{timestamp}_{unique_id}{file_ext}"
            
            # 원본 파일 다운로드 후 S3에 재업로드 (카테고리 폴더로 이동)
            import requests
            audio_data = requests.get(s3_url).content
            s3_client.put_object(
                Bucket=BUCKET_NAME,
                Key=s3_key,
                Body=audio_data,
                Metadata={
                    "diagnosed_label": final_result.detail.diagnosed_label,
                    "confidence": str(final_result.confidence),
                    "source_url": s3_url
                }
            )
            print(f"[S3 Upload] 저장 완료: s3://{BUCKET_NAME}/{s3_key}")
        else:
            print("[Data Collection] 학습 가치가 낮은 데이터이므로 수집 제외.")
            
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