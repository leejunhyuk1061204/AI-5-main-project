from pydantic import BaseModel
from typing import Optional

class AudioDetail(BaseModel):
    diagnosed_label: str # SLIP_NOISE 등
    description: str     # 상세 설명

class AudioResponse(BaseModel):
    status: str          # NORMAL, FAULTY
    analysis_type: str   # AST 또는 LLM_AUDIO
    category: str        # 엔진, 벨트, 서스펜션 등 (분류)
    detail: AudioDetail
    confidence: float
    is_critical: bool
    description: Optional[str] = None # LLM용 추가 설명