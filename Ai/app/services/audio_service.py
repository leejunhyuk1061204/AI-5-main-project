from fastapi import UploadFile, HTTPException
from ai.app.schemas.audio import AudioResponse, AudioDetail

class AudioService:
    """오디오 분석 및 진단을 담당하는 서비스 클래스"""

    SUPPORTED_AUDIO_EXTENSIONS = {".wav", ".m4a", ".mp3", ".flac", ".ogg"}

    @classmethod
    def validate_audio_file(cls, filename: str) -> bool:
        """오디오 파일 확장자 검증"""
        if not filename:
            return False
        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        return ext in cls.SUPPORTED_AUDIO_EXTENSIONS

    async def predict_audio(self, file: UploadFile) -> AudioResponse:
        """
        오디오 파일을 분석하여 진단 결과를 반환합니다.
        현재는 Mock 데이터를 반환하며, 추후 YAMNet 모델이 연동될 예정입니다.
        """
        # 파일 확장자 검증
        if not self.validate_audio_file(file.filename):
            raise HTTPException(
                status_code=400,
                detail=f"지원하지 않는 파일 형식입니다. 지원 형식: {', '.join(self.SUPPORTED_AUDIO_EXTENSIONS)}"
            )

        print(f"[Audio Service] Processing audio file: {file.filename}")

        # TODO: 실제 YAMNet 모델 연동 시 아래 로직 구현
        # 1. 오디오 파일을 16kHz로 리샘플링
        # 2. Mel-Spectrogram 변환
        # 3. YAMNet 모델로 추론
        # 4. 차량 관련 클래스 필터링 및 결과 매핑

        # [Mock Data] 명세서와 동일한 형태의 가짜 데이터 리턴 - FAULTY 케이스
        return AudioResponse(
            primary_status="FAULTY",
            component="ENGINE_BELT",
            detail=AudioDetail(
                diagnosed_label="SLIP_NOISE",
                description="구동 벨트 장력 부족 의심"
            ),
            confidence=0.88,
            is_critical=False
        )

    async def get_mock_normal_data(self, file: UploadFile) -> AudioResponse:
        """테스트용 정상 상태 Mock 반환"""
        print(f"[Audio Service] Test normal - Processing: {file.filename}")
        
        return AudioResponse(
            primary_status="NORMAL",
            component="ENGINE",
            detail=AudioDetail(
                diagnosed_label="NORMAL",
                description="정상적인 엔진 작동음입니다"
            ),
            confidence=0.95,
            is_critical=False
        )
