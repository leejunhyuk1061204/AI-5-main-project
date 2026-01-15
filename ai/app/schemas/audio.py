from pydantic import BaseModel

class AudioDetail(BaseModel):
    """진단 상세 정보"""
    diagnosed_label: str        # "SLIP_NOISE", "KNOCKING", "NORMAL" 등
    description: str            # "구동 벨트 장력 부족 의심"


class AudioResponse(BaseModel):
    """오디오 진단 응답 모델 (API 명세서 기준)"""
    primary_status: str         # "FAULTY" | "NORMAL"
    component: str              # "ENGINE_BELT", "ENGINE", "BEARING" 등
    detail: AudioDetail         # 진단 상세
    confidence: float           # 0.0 ~ 1.0
    is_critical: bool           # 긴급 정비 필요 여부
