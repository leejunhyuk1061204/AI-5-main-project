import os
import json
import base64
import httpx
import re
from openai import AsyncOpenAI
from ai.app.schemas.visual_schema import VisualResponse
from ai.app.schemas.audio_schema import AudioResponse, AudioDetail

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ---------------------------------------------------------
# 1. 시각 전문 진단 (GPT-4o Vision)
# ---------------------------------------------------------
async def analyze_general_image(s3_url: str) -> VisualResponse:
    SYSTEM_PROMPT = """
    당신은 'Car-Sentry 시각 분석 팀'의 수석 검수관입니다. 
    당신의 임무는 제공된 이미지에서 육안으로 식별 가능한 모든 결함을 찾는 것입니다.

    [분석 가이드라인]
    1. 분류(Category): 사진 속 주요 부품이 무엇인지 먼저 판단하십시오.
       - EXTERIOR (외관: 범퍼, 도어, 휀더, 스크래치 등)
       - TIRES_WHEELS_IMAGE (타이어, 휠)
       - GLASS_WINDOWS (유리, 창문, 썬팅)
       - LIGHTS (헤드램프, 테일램프)
       - ENGINE_ROOM (엔진룸 내부, 배터리)
       - UNDERBODY (하부, 배기구, 녹)
       - INTERIOR (실내: 시트, 핸들, 대시보드)
       - UNKNOWN_IMAGE (확신없음)
    2. 결함 식별: 픽셀 단위로 정밀 관찰하여 미세한 균열, 누유, 파손을 찾으십시오.
    3. 논리적 추론: 시각적 증거에 기반한 원인 분석.

    [데이터 품질 대응]
    - 화질 저하, 초점 미흡 시 status를 "RE_UPLOAD_REQUIRED"로 설정하십시오.

    [출력 형식]
    {
        "status": "NORMAL" | "WARNING" | "CRITICAL" | "RE_UPLOAD_REQUIRED",
        "category": "분류명(위 리스트 중 택1)",
        "description": "상황 요약",
        "recommendation": "조치 방법",
        "analysis_summary": "결론에 도달한 주요 근거 요약"
    }
    """

    try:
        # [Correct] Vision Input via 'responses.create' (New SDK Protocol)
        response = await client.responses.create(
            model="gpt-4o",
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": SYSTEM_PROMPT + "\n\n이 차량 외관 사진을 분석해줘."},
                        {"type": "input_image", "image_url": s3_url}
                    ]
                }
            ],
            response_format={"type": "json_object"}
        )
        
        # [Correct] Access output via output_text
        result = json.loads(response.output_text)
        current_status = result.get("status", "WARNING")
        
        return VisualResponse(
            status=current_status,
            analysis_type="LLM_VISION",
            category=result.get("category", "ETC"), # 카테고리 추가
            description=result.get("description", "분석 결과가 없습니다."),
            recommendation=result.get("recommendation", "점검이 필요합니다."),
            processed_image_url=s3_url
        )
    except Exception as e:
        print(f"[LLM Vision Error] {e}")
        return VisualResponse(status="ERROR", description="이미지 분석 중 오류 발생", processed_image_url=s3_url)

# ---------------------------------------------------------
# 2. 청각 전문 진단 (GPT-4o Audio)
# ---------------------------------------------------------
async def analyze_audio_with_llm(s3_url: str) -> AudioResponse:
    SYSTEM_PROMPT = """
    당신은 'Car-Sentry 소음·진동(NVH) 분석 팀'의 수석 엔지니어입니다. 
    오디오 데이터에서 기계적인 이상 징후를 소리만으로 찾아내십시오.

    [분석 가이드라인]
    1. 분류(Category): 소리의 근원지가 되는 핵심 부품을 분류하십시오.
       - ENGINE (엔진: 노킹, 밸브 소리)
       - SUSPENSION (서스펜션: 찌그덕, 덜컹거림)
       - BRAKES (브레이크: 스끼, 쇠 갈리는 소리)
       - EXHAUST (배기: 머플러 터진 소리, 배기음)
       - TIRES_WHEELS_AUDIO (타이어/휠: 주행 소음, 베어링)
       - BODY (차체: 풍절음, 잡소리)
       - UNKNOWN_AUDIO (확신없음)
    2. 음향적 특징: 리듬, 피치, 질감 분석.
    3. 기계적 연결: 소리와 부품 마찰의 상관관계 추론.
    
    [데이터 품질 대응]
    - 소음 과다 시 status를 "RE_RECORD_REQUIRED"로 설정하십시오.

    [출력 형식]
    {
        "diagnosed_label": "진단명",
        "category": "분류명(위 리스트 중 택1)",
        "description": "상세 분석 및 조언",
        "status": "NORMAL" | "FAULTY" | "RE_RECORD_REQUIRED",
        "confidence": 0.0 ~ 1.0,
        "analysis_summary": "주요 근거 요약"
    }
    """
   
    try:
        async with httpx.AsyncClient(timeout=10.0) as httpx_client:
            audio_response = await httpx_client.get(s3_url)
            audio_response.raise_for_status()
            audio_data = base64.b64encode(audio_response.content).decode('utf-8')

        # [Correct] Audio Input via 'responses.create' (New SDK Protocol)
        response = await client.responses.create(
            model="gpt-4o-audio-preview",
            input=[{
                "role": "user",
                "content": [
                    {"type": "input_text", "text": SYSTEM_PROMPT + "\n\n이 소리를 진단하고 반드시 JSON 포맷으로 응답하세요."},
                    {
                        "type": "input_audio",
                        "audio": audio_data,
                        "format": "wav"
                    }
                ]
            }]
        )
        
        content = response.output_text
        
        # [Robust] Regex를 이용한 강력한 JSON 추출
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group())
            except json.JSONDecodeError:
                result = {"status": "FAULTY", "description": content, "diagnosed_label": "Unknown"}
        else:
            result = {"status": "FAULTY", "description": content, "diagnosed_label": "Unknown"}

        current_status = result.get("status", "FAULTY")

        return AudioResponse(
            status=current_status,
            analysis_type="LLM_AUDIO",
            category=result.get("category", "ENGINE"), # 카테고리 추가 (기본값 ENGINE)
            detail=AudioDetail(
                diagnosed_label=result.get("diagnosed_label", "LLM 진단"),
                description=result.get("description", "분석 완료")
            ),
            confidence=float(result.get("confidence", 0.8)),
            is_critical=(current_status == "FAULTY")
        )
    except Exception as e:
        print(f"[LLM Audio Error] {e}")
        return AudioResponse(status="ERROR", confidence=0.0)