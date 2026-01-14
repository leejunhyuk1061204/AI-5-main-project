# app/services/audio_service.py
from app.services.hertz import process_to_16khz
from app.services.ast_service import run_ast_inference
from app.services.llm_service import analyze_audio_with_llm
from app.schemas.audio_schema import AudioResponse, AudioDetail

class AudioService:
    async def predict_audio_smart(self, s3_url: str) -> AudioResponse:
        """
        16kHz 전처리 -> AST 분류 -> LLM 정밀 진단 통합 흐름
        """
        # 1. 전처리: 16kHz 변환 (헤르즈.py 호출)
        audio_buffer = process_to_16khz(s3_url)
        
        if not audio_buffer:
            # 변환 실패 시 바로 LLM 시도
            return await analyze_audio_with_llm(s3_url)

        # 2. 1차 진단: AST 모델
        ast_result = await run_ast_inference(audio_buffer)
        
        # 3. 2차 진단 판단: 신뢰도가 낮거나(0.7 미만) 결과가 UNKNOWN일 때 LLM 호출
        if ast_result.confidence < 0.7 or ast_result.status == "UNKNOWN":
            print(f"[Audio Service] AST 결과 미흡 (신뢰도: {ast_result.confidence}). LLM으로 전환.")
            return await analyze_audio_with_llm(s3_url)
            
        return ast_result

    async def get_mock_normal_data(self) -> AudioResponse:
        """테스트용 정상 데이터"""
        return AudioResponse(
            status="NORMAL",
            analysis_type="AST",
            component="ENGINE",
            detail=AudioDetail(diagnosed_label="NORMAL", description="정상입니다."),
            confidence=0.99,
            is_critical=False
        )