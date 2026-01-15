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

## 출력 예시
# {
#     "status": "NORMAL",
#     "analysis_type": "LLM_AUDIO",
#     "category": "엔진",
#     "detail": {
#         "diagnosed_label": "SLIP_NOISE",
#         "description": "슬립 노이즈가 발견되었습니다."
#     },
#     "confidence": 0.9,
#     "is_critical": false,
#     "description": "이 차량의 엔진에서 슬립 노이즈가 발견되었습니다."
# }