# ai/app/services/llm_service.py
"""
AI 분석 결과 해석 및 리포트 생성 서비스 (LLM)

[역할]
1. 전문가급 진단: YOLO, PatchCore 등의 수치적 결과를 사람이 이해할 수 있는 자연어로 변환합니다.
2. 멀티 모달 분석: 시각(Vision)과 청각(Audio) 데이터를 모두 처리하며, 복합적인 상황을 추론합니다.
3. 범용 분석(Fallback): 전용 AI 모델이 없거나 확신도가 낮을 때 GPT-4o가 직접 사진을 보고 판단합니다.

[주요 기능]
- 엔진룸 이상 분석 (suggest_anomaly_label)
- 범용 이미지 진단 (analyze_general_image)
- 계기판 경고등 해석 (interpret_dashboard_warnings)
- 외관 파손 리포트 생성 (generate_exterior_report)
- 타이어 상태 정밀 진단 (interpret_tire_status)
- 오디오 기반 기계음 진단 (analyze_audio_with_llm)
"""
import os
import json
import base64
import httpx
import re
from typing import Optional, List, Dict
from openai import AsyncOpenAI
from ai.app.schemas.visual_schema import VisualResponse
from ai.app.schemas.audio_schema import AudioResponse, AudioDetail

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY") or "MISSING_KEY")

# ---------------------------------------------------------
# 1. 시각 전문 진단 (GPT-4o Vision)
# ---------------------------------------------------------

async def suggest_anomaly_label(
    heatmap_url: str,
    crop_url: str,
    part_name: str,
    anomaly_score: float
) -> dict:
    """
    [Path A: Engine Detect]
    YOLO가 탐지한 부품의 Crop 이미지와 Heatmap을 분석하여 이상 원인을 제안합니다.
    URL은 반드시 Presigned URL이어야 합니다.
    """
    SYSTEM_PROMPT = f"""
    당신은 'Car-Sentry 엔진룸 결함 분석 전문가'입니다.
    
    분석 대상: {part_name}
    이상 점수: {anomaly_score:.2f}

    [입력 이미지 설명]
    1. 첫 번째 이미지: 부품 원본 Crop
    2. 두 번째 이미지: 이상 부위가 붉게 표시된 Heatmap Overlay

    [임무]
    - Anomaly Detector가 이미 이 부품을 '이상(Anomaly)'으로 판정했습니다.
    - 당신의 역할은 판정 여부를 따지는 것이 아니라, '어떤 종류의 결함인지' 설명하는 것입니다.
    - 붉은색 Heatmap 영역에 집중하여 시각적 특징을 서술하세요.

    [결함 분류 기준]
    - LEAK: 누유, 액체 흔적 (오일, 냉각수)
    - CORROSION: 녹, 산화, 부식 (배터리 단자 등)
    - PHYSICAL: 균열, 찌그러짐, 탈락, 파손
    - CONTAMINATION: 먼지 퇴적, 이물질
    - WEAR: 벨트 마모, 호스 경화
    - UNKNOWN: 특징이 불명확함

    [출력 형식 - JSON]
    {{
        "defect_category": "카테고리명",
        "defect_label": "구체적_라벨명 (예: Battery_Acid_Leak)",
        "description_ko": "한글 설명 (비전문가도 이해하기 쉽게)",
        "severity": "MINOR|WARNING|CRITICAL",
        "recommended_action": "권장 조치"
    }}
    """
    
    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": [
                    {"type": "text", "text": "이 부품의 이상 영역을 분석해주세요."},
                    {"type": "image_url", "image_url": {"url": crop_url}}, # Presigned URL
                    {"type": "image_url", "image_url": {"url": heatmap_url}} # Presigned URL
                ]}
            ],
            response_format={"type": "json_object"},
            max_tokens=500,
            timeout=30.0 # Circuit Breaker: Timeout
        )
        content = response.choices[0].message.content
        return json.loads(content)
        
    except Exception as e:
        print(f"[LLM Anomaly Error] {e}")
        # Fallback Safe JSON
        return {
            "defect_category": "UNKNOWN",
            "defect_label": "Analysis_Failed",
            "description_ko": "AI 정밀 분석 중 오류가 발생했습니다. (일시적 장애)",
            "severity": "WARNING",
            "recommended_action": "육안 점검 권장"
        }


async def suggest_anomaly_label_with_base64(
    crop_base64: str,
    heatmap_base64: str,
    part_name: str,
    anomaly_score: float
) -> dict:
    """
    [Path A: Engine Detect - Base64 버전]
    URL 대신 Base64 인코딩된 이미지를 직접 전달합니다.
    S3 업로드 없이 LLM 분석 가능!
    """
    SYSTEM_PROMPT = f"""
    당신은 'Car-Sentry 엔진룸 결함 분석 전문가'입니다.
    
    분석 대상: {part_name}
    이상 점수: {anomaly_score:.2f}

    [입력 이미지 설명]
    1. 첫 번째 이미지: 부품 원본 Crop
    2. 두 번째 이미지: 이상 부위가 붉게 표시된 Heatmap Overlay

    [임무]
    - Anomaly Detector가 이미 이 부품을 '이상(Anomaly)'으로 판정했습니다.
    - 당신의 역할은 '어떤 종류의 결함인지' 설명하는 것입니다.
    - 붉은색 Heatmap 영역에 집중하여 시각적 특징을 서술하세요.

    [결함 분류 기준]
    - LEAK: 누유, 액체 흔적 (오일, 냉각수)
    - CORROSION: 녹, 산화, 부식 (배터리 단자 등)
    - PHYSICAL: 균열, 찌그러짐, 탈락, 파손
    - CONTAMINATION: 먼지 퇴적, 이물질
    - WEAR: 벨트 마모, 호스 경화
    - UNKNOWN: 특징이 불명확함

    [출력 형식 - JSON]
    {{
        "defect_category": "카테고리명",
        "defect_label": "구체적_라벨명 (예: Battery_Acid_Leak)",
        "description_ko": "한글 설명 (비전문가도 이해하기 쉽게)",
        "severity": "MINOR|WARNING|CRITICAL",
        "recommended_action": "권장 조치"
    }}
    """
    
    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": [
                    {"type": "text", "text": "이 부품의 이상 영역을 분석해주세요."},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{crop_base64}"}
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{heatmap_base64}"}
                    }
                ]}
            ],
            response_format={"type": "json_object"},
            max_tokens=500,
            timeout=30.0
        )
        content = response.choices[0].message.content
        return json.loads(content)
        
    except Exception as e:
        print(f"[LLM Anomaly Base64 Error] {e}")
        return {
            "defect_category": "UNKNOWN",
            "defect_label": "Analysis_Failed",
            "description_ko": "AI 정밀 분석 중 오류가 발생했습니다.",
            "severity": "WARNING",
            "recommended_action": "육안 점검 권장"
        }

async def analyze_general_image(s3_url: str) -> VisualResponse:
    """
    [Path B: Fallback / 범용 분석]
    YOLO가 놓쳤거나, 별도 모델이 없는 이미지에 대한 LLM 분류.
    - DASHBOARD (계기판 경고등) 포함: 별도 YOLO 학습 없이 LLM이 분류
    - ENGINE 포함: Hard Mining용
    """
    SYSTEM_PROMPT = """
    당신은 'Car-Sentry 시각 분석 팀'의 수석 검수관입니다. 
    제공된 이미지를 분석하여 차량 관련 여부를 판단하고 진단하십시오.

    [분석 단계]
    1. Vehicle Validation: 이 이미지가 자동차와 관련이 있습니까? (부품 포함)
       - NO -> type="IRRELEVANT"
    
    2. Classification (Sub Type):
       - DASHBOARD (계기판 경고등 사진) **예: 엔진 경고등, ABS, 타이어 압력 등**
       - EXTERIOR (외관 - 범퍼, 도어, 펜더 등)
       - INTERIOR (실내 - 시트, 핸들 등)
       - TIRE (타이어/휠)
       - LAMP (헤드램프/테일램프)
       - ENGINE (엔진룸/부품) **YOLO가 놓친 엔진 부품일 수 있음**
    
    3. Diagnosis: 손상 여부 및 설명
       - DASHBOARD의 경우: 어떤 경고등이 켜져 있는지 나열

    [출력 형식 - JSON]
    {
        "type": "VEHICLE" | "IRRELEVANT",
        "sub_type": "DASHBOARD" | "EXTERIOR" | "INTERIOR" | "TIRE" | "LAMP" | "ENGINE" | "NONE",
        "status": "NORMAL" | "WARNING" | "CRITICAL",
        "description": "한글 설명",
        "recommendation": "조치"
    }
    """

    try:
        response = await client.chat.completions.create(
            model="gpt-4o",  # [비용 절약] Path B는 단순 분류 → 4o-mini로 충분 (1/20 비용)
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": [
                    {"type": "text", "text": "이 이미지를 분류하고 진단해주세요."},
                    {"type": "image_url", "image_url": {"url": s3_url}}
                ]}
            ],
            response_format={"type": "json_object"},
            max_tokens=800,
            timeout=30.0
        )
        
        content = response.choices[0].message.content
        result = json.loads(content)

        # Map LLM result to VisualResponse
        # IRRELEVANT 처리
        if result.get("type") == "IRRELEVANT":
             return VisualResponse(
                status="ERROR", # 클라이언트에서 경고창을 띄우기 위해 ERROR로 처리하거나 별도 처리
                analysis_type="LLM_GENERAL",
                category="IRRELEVANT",
                description="차량과 관련 없는 이미지입니다.",
                recommendation="차량 사진을 업로드해주세요.",
                processed_image_url=s3_url
            )

        return VisualResponse(
            status=result.get("status", "WARNING"),
            analysis_type="LLM_GENERAL",
            category=result.get("sub_type", "ETC"),
            description=result.get("description", ""),
            recommendation=result.get("recommendation", ""),
            processed_image_url=s3_url
        )
        
    except Exception as e:
        print(f"[LLM General Error] {e}")
        return VisualResponse(
            status="ERROR", 
            analysis_type="LLM_GENERAL", 
            category="ERROR", 
            description="이미지 분석 서비스를 사용할 수 없습니다.", 
            processed_image_url=s3_url
        )

# ---------------------------------------------------------
# 2. 청각 전문 진단 (GPT-4o Audio)
# ---------------------------------------------------------
async def analyze_audio_with_llm(s3_url: str, audio_bytes: Optional[bytes] = None) -> AudioResponse:
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
        if audio_bytes is None:
            async with httpx.AsyncClient(timeout=10.0) as httpx_client:
                audio_response = await httpx_client.get(s3_url)
                audio_response.raise_for_status()
                audio_data = base64.b64encode(audio_response.content).decode('utf-8')
        else:
            audio_data = base64.b64encode(audio_bytes).decode('utf-8')

        # [Correct] Audio Input via 'chat.completions.create'
        response = await client.chat.completions.create(
            model="gpt-4o-audio-preview",
            modalities=["text", "audio"],
            audio={"voice": "alloy", "format": "wav"},
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": SYSTEM_PROMPT + "\n\n이 소리를 진단하고 반드시 JSON 포맷으로 응답하세요."},
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": audio_data,
                                "format": "wav"
                            }
                        }
                    ]
                }
            ]
        )
        
        content = response.choices[0].message.audio.transcript

        
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
        return AudioResponse(
            status="ERROR",
            analysis_type="LLM_AUDIO",
            category="UNKNOWN_AUDIO",
            detail=AudioDetail(diagnosed_label="Error", description="오디오 분석 실패"),
            confidence=0.0,
            is_critical=False
        )


# ---------------------------------------------------------
# 3. 도메인 전용 자연어 해석 함수 (Pipelines)
# ---------------------------------------------------------

async def interpret_dashboard_warnings(detections: List[Dict]) -> Dict[str, str]:
    """
    YOLO가 감지한 경고등 목록을 바탕으로 운전 가이드 생성
    """
    PROMPT = f"""
    차량 계기판에서 다음 경고등이 감지되었습니다:
    {json.dumps(detections, ensure_ascii=False, indent=2)}
    
    운전자에게 알려줄 내용을 작성해주세요:
    1. 각 경고등의 의미와 위험도
    2. 즉시 조치가 필요한지 여부
    3. 권장하는 조치 사항
    
    JSON 형식으로 응답:
    {{"description": "종합 설명", "recommendation": "권장 조치"}}
    """
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": PROMPT}],
            response_format={"type": "json_object"},
            max_tokens=600
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"[LLM Dashboard Error] {e}")
        return {"description": "계기판 경고등 분석 중 오류가 발생했습니다.", "recommendation": "안전한 곳에 정차 후 수동 점검 바랍니다."}


async def generate_exterior_report(mappings: List[Dict]) -> Dict[str, str]:
    """
    감지된 부위별 파손 정보를 자연스러운 한글 문장으로 변환
    """
    PROMPT = f"""
    차량 외관 분석 결과:
    {json.dumps(mappings, ensure_ascii=False, indent=2)}
    
    운전자에게 알려줄 내용을 자연스러운 한국어로 작성:
    1. 발견된 파손 요약
    2. 수리 권장 사항 (판금, 도색, 교체 등)
    3. 주행 안전상 지장 유무
    
    JSON: {{"description": "...", "recommendation": "..."}}
    """
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": PROMPT}],
            response_format={"type": "json_object"},
            max_tokens=600
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"[LLM Exterior Error] {e}")
        return {"description": "외관 파손 분석 결과를 처리할 수 없습니다.", "recommendation": "가까운 정비소에서 육안 검사를 권장합니다."}


async def interpret_tire_status(status_list: List[Dict]) -> Dict[str, str]:
    """
    타이어의 마모, 균열, 펑크 등에 대한 전문가 조언 생성
    """
    PROMPT = f"""
    타이어 분석 결과:
    {json.dumps(status_list, ensure_ascii=False, indent=2)}
    
    운전자에게 알려줄 내용:
    1. 타이어 상태 요약 (마모 상태 등)
    2. 안전 관련 주의사항 (제동거리, 미끄러짐 위험)
    3. 권장 조치 (교체 주기 확인 등)
    
    JSON: {{"description": "...", "recommendation": "..."}}
    """
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": PROMPT}],
            response_format={"type": "json_object"},
            max_tokens=500
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"[LLM Tire Error] {e}")
        return {"description": "타이어 상태 정보를 처리하는 도중 오류가 발생했습니다.", "recommendation": "공기압 및 트레드 상태를 수동으로 확인하십시오."}