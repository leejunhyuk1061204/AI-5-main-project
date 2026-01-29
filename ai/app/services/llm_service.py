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
from typing import Optional, List, Dict, Any
from openai import AsyncOpenAI
from ai.app.schemas.visual_schema import VisualResponse
from ai.app.schemas.audio_schema import AudioResponse, AudioDetail

# OpenAI 클라이언트 생성 및 키 체크
def _get_api_key():
    return os.getenv("OPENAI_API_KEY")

def is_llm_ready():
    """API 키가 있고 유효한 형식인지 체크"""
    key = _get_api_key()
    return key is not None and key.startswith("sk-") and len(key) > 20

client = None
def _get_client():
    global client
    if client is None:
        api_key = _get_api_key()
        client = AsyncOpenAI(api_key=api_key or "MISSING_KEY")
    return client

# 최종 Mock/Fallback 판정: 명시적 MOCK 설정 OR API 키 없음
def should_use_fallback():
    explicit_mock = os.getenv("MOCK_LLM", "false").lower() == "true"
    return explicit_mock or not is_llm_ready()

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
    
    if should_use_fallback():
        reason = "MOCK" if os.getenv("MOCK_LLM", "false").lower() == "true" else "Local"
        print(f"[LLM {reason}] suggest_anomaly_label (URL): {part_name}")
        return {
            "defect_category": "UNKNOWN",
            "defect_label": "Analysis_Unavailable",
            "description_ko": f"{part_name} 부품의 AI 정밀 분석이 불가능합니다. ({reason} 모드 - 실제 LLM 연결 필요)",
            "severity": "WARNING",
            "recommended_action": "AI 서버 설정을 확인하거나 육안으로 점검하십시오."
        }
    
    try:
        response = await _get_client().chat.completions.create(
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
    heatmap_base64: Optional[str], # Heatmap 재도입 (Optional)
    bbox: Optional[List[int]],     # BBox 정보 (Optional)
    part_name: str,
    anomaly_score: float
) -> dict:
    """
    [Path A: Engine Detect - Base64 버전]
    URL 대신 Base64 인코딩된 이미지를 직접 전달합니다.
    (heatmap이 있으면 우선적으로 참고하고, 없으면 bbox 텍스트 힌트를 사용)
    """
    bbox_desc = f"이미지 내 좌표 정보(BBox): {bbox}" if bbox else "좌표 정보 없음"
    heatmap_desc = "2. 두 번째 이미지: 이상 부위가 붉게 표시된 Heatmap Overlay (참고용)" if heatmap_base64 else "(Heatmap 이미지 없음)"

    SYSTEM_PROMPT = f"""
    당신은 'Car-Sentry 엔진룸 결함 분석 전문가'입니다.
    
    분석 대상: {part_name}
    이상 점수: {anomaly_score:.2f}
    관심 영역: {bbox_desc}

    [입력 이미지 설명]
    1. 첫 번째 이미지: 부품 원본 Crop
    {heatmap_desc}

    [임무]
    - Anomaly Detector가 이미 이 부품을 '이상(Anomaly)'으로 판정했습니다.
    - 당신의 역할은 '어떤 종류의 결함인지' 설명하는 것입니다.
    - Heatmap 이미지가 제공되면 붉은 영역을 중심으로, 없다면 {bbox_desc} 영역 근처의 시각적 특징을 분석하세요.

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
        "defect_label": "구체적_라벨명",
        "description_ko": "한글 설명",
        "severity": "MINOR|WARNING|CRITICAL",
        "recommended_action": "권장 조치",
        "is_mock": false
    }}
    """
    
    if should_use_fallback():
        reason = "MOCK" if os.getenv("MOCK_LLM", "false").lower() == "true" else "Local"
        print(f"[LLM {reason}] suggest_anomaly_label: {part_name}")
        return {
            "defect_category": "UNKNOWN",
            "defect_label": "Analysis_Unavailable",
            "description_ko": f"{part_name} 부품의 AI 정밀 분석이 불가능합니다. ({reason} 모드 - 실제 LLM 연결 필요)",
            "severity": "WARNING",
            "recommended_action": "AI 서버 설정을 확인하거나 육안으로 점검하십시오.",
            "is_mock": True
        }

    try:
        # 메시지 구성
        user_content = [{"type": "text", "text": "이 부품의 이상 영역을 분석해주세요."}]
        
        # 1. 원본 이미지 추가
        user_content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{crop_base64}"}
        })
        
        # 2. 히트맵 이미지 추가 (있을 때만)
        if heatmap_base64:
            user_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{heatmap_base64}"}
            })

        response = await _get_client().chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content}
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


async def call_openai_vision(s3_url: str, prompt: str) -> Dict[str, Any]:
    """
    [범용 Vision API 호출 함수]
    
    이미지 URL과 커스텀 프롬프트를 받아 GPT-4o Vision으로 분석합니다.
    타이어 마모도 측정, 부품 상태 확인 등 다양한 용도로 사용됩니다.
    
    Args:
        s3_url: 분석할 이미지의 S3 URL
        prompt: LLM에게 전달할 분석 지시 프롬프트
    
    Returns:
        LLM이 반환한 JSON 파싱 결과 (dict)
    
    Example:
        result = await call_openai_vision(
            s3_url="s3://bucket/tire.jpg",
            prompt="타이어 마모도를 측정하세요..."
        )
        # result: {"wear_level_pct": 45, "status": "FAIR", ...}
    """
    if should_use_fallback():
        reason = "MOCK" if os.getenv("MOCK_LLM", "false").lower() == "true" else "Local"
        print(f"[LLM {reason}] call_openai_vision")
        # 타이어 분석 등에서 공통으로 쓰이는 JSON 구조 대응
        return {
            "wear_level_pct": 20,
            "wear_status": "GOOD",
            "critical_issues": None,
            "description": f"이미지 데이터 분석 결과가 양호합니다. ({reason} 분석 모드)",
            "recommendation": "안전 주행을 위해 정기적인 점검을 유지하십시오.",
            "is_replacement_needed": False
        }

    try:
        response = await _get_client().chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": [
                    {"type": "text", "text": "이 이미지를 분석해주세요."},
                    {"type": "image_url", "image_url": {"url": s3_url}}
                ]}
            ],
            response_format={"type": "json_object"},
            max_tokens=1000,
            timeout=30.0
        )
        
        content = response.choices[0].message.content
        result = json.loads(content)
        return result
        
    except json.JSONDecodeError as e:
        print(f"[LLM Vision] JSON 파싱 오류: {e}")
        return {"status": "ERROR", "error": "JSON 파싱 실패"}
    except Exception as e:
        print(f"[LLM Vision Error] {e}")
        return {"status": "ERROR", "error": str(e)}

async def analyze_general_image(s3_url: str) -> VisualResponse:
    """
    [Path B: Fallback / 범용 분석]
    YOLO가 놓쳤거나, 별도 모델이 없는 이미지에 대한 LLM 분류.
    - DASHBOARD (계기판 경고등) 포함: 별도 YOLO 학습 없이 LLM이 분류
    - ENGINE 포함: Hard Mining용
    """
    SYSTEM_PROMPT = """
    당신은 'Car-Sentry 시각 분석 팀'의 수석 검수관입니다. 
    제공된 이미지를 분석하여 "차량 관련성"을 최우선으로 판단하고, 차량의 모든 부위(실내외)에 대해 진단을 수행하십시오.

    [분석 단계 1: 차량 관련성 판단 (Strict Filter)]
    - 이 이미지가 자동차(Vehicle)와 관련된 이미지입니까?
    - 판단 기준: 자동차의 외관, 내관, 부품, 타이어, 계기판, 자동차 키, 정비 도구 등 차량과 관련된 맥락이 조금이라도 있으면 YES.
    - 음식, 동물, 풍경, 사람 얼굴, 일반 가전제품 등 차량과 전혀 무관하면 NO.
    
    - YES -> [분석 단계 2]로 이동
    - NO -> JSON 출력의 "type"을 "IRRELEVANT"로 설정하고, description에 "차량 관련 사진이 아닙니다."라고 명시하고 종료.

    [분석 단계 2: 상세 분류 및 진단]
    다음 카테고리 중 하나로 분류하고 상태를 진단하십시오:
    1. DASHBOARD: 계기판 경고등
    2. EXTERIOR: 차량 외관 (파손 여부 확인)
    3. TIRE_WHEEL: 타이어 및 휠
    4. ENGINE: 엔진룸 내부
    5. ETC: 그 외 모든 차량 관련 요소 (실내 시트, 핸들, 네비게이션, 트렁크, 하부, 자동차 키 등)

    [진단 가이드]
    - ETC(실내 등)인 경우: "차량 실내(시트/핸들) 사진입니다. 특별한 파손은 보이지 않습니다." 처럼 설명.
    - 상태(status): 특별한 이상이 없으면 NORMAL, 파손이나 오염이 심하면 WARNING.

    [출력 형식 - JSON]
    {
        "type": "VEHICLE" | "IRRELEVANT",
        "sub_type": "DASHBOARD" | "EXTERIOR" | "TIRE" | "ENGINE" | "ETC",
        "status": "NORMAL" | "WARNING" | "CRITICAL",
        "description": "한글 설명 (차량 관련 사진이 아닙니다 or 상태 설명)",
        "recommendation": "조치 사항 (해당 없으면 빈 문자열)"
    }
    """
    if should_use_fallback():
        reason = "MOCK" if os.getenv("MOCK_LLM", "false").lower() == "true" else "Local"
        print(f"[LLM {reason}] analyze_general_image")
        return VisualResponse(
            status="NORMAL",
            analysis_type="LLM_FALLBACK",
            category="GENERAL",
            data={
                "description": f"이미지 데이터가 양호합니다. ({reason} 분석 모드)", 
                "recommendation": "차량 관리 가이드에 따라 정기 점검을 권장합니다."
            },
            confidence=0.9
        )

    try:
        response = await _get_client().chat.completions.create(
            model="gpt-4o-mini",  # [비용 절약] Path B는 단순 분류 → 4o-mini로 충분 (1/20 비용)
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
                status="ERROR",
                analysis_type="LLM_GENERAL",
                category="IRRELEVANT",
                data={
                    "description": "차량과 관련 없는 이미지입니다.",
                    "recommendation": "차량 사진을 업로드해주세요.",
                    "processed_image_url": s3_url
                }
            )

        return VisualResponse(
            status=result.get("status", "WARNING"),
            analysis_type="LLM_GENERAL",
            category=result.get("sub_type", "ETC"),
            data={
                "description": result.get("description", ""),
                "recommendation": result.get("recommendation", ""),
                "processed_image_url": s3_url if not s3_url.startswith("data:") else "data:image/jpeg;base64,...(truncated)"
            }
        )
        
    except Exception as e:
        error_msg = str(e)
        if "api_key" in error_msg.lower() or "missing_key" in error_msg.lower() or "auth" in error_msg.lower():
            detailed_desc = "[설정 오류] OpenAI API Key가 유효하지 않거나 .env에 설정되지 않았습니다. GPT 분석이 필요한 상황(저신뢰 데이터)에서 분석이 불가능합니다."
        else:
            detailed_desc = f"AI 분석 엔진 호출 실패: {error_msg}"
            
        print(f"[LLM General Error] {e}")
        return VisualResponse(
            status="ERROR", 
            analysis_type="LLM_GENERAL", 
            category="ERROR", 
            data={
                "description": detailed_desc, 
                "recommendation": "관리자에게 OpenAI API 설정을 확인해달라고 요청하세요.",
                "processed_image_url": s3_url
            }
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
    if should_use_fallback():
        reason = "MOCK" if os.getenv("MOCK_LLM", "false").lower() == "true" else "Local"
        print(f"[LLM {reason}] analyze_audio_with_llm")
        return AudioResponse(
            status="NORMAL",
            analysis_type="LLM_AUDIO",
            category="ENGINE",
            detail=AudioDetail(
                diagnosed_label="정상 구동음", 
                description=f"엔진 구동음이 규칙적이고 정상입니다. ({reason} 분석 모드)"
            ),
            confidence=0.9,
            is_critical=False
        )
   
    try:
        if audio_bytes is None:
            async with httpx.AsyncClient(timeout=10.0) as httpx_client:
                audio_response = await httpx_client.get(s3_url)
                audio_response.raise_for_status()
                audio_data = base64.b64encode(audio_response.content).decode('utf-8')
        else:
            audio_data = base64.b64encode(audio_bytes).decode('utf-8')

        # [Correct] Audio Input via 'chat.completions.create'
        response = await _get_client().chat.completions.create(
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
    if should_use_fallback():
        reason = "MOCK" if os.getenv("MOCK_LLM", "false").lower() == "true" else "Local"
        print(f"[LLM {reason}] interpret_dashboard_warnings")
        
        if not detections:
            return {
                "description": f"계기판에 특별한 경고등이 감지되지 않았습니다. ({reason} 분석 모드)",
                "recommendation": "안전 운행 하십시오."
            }
        
        # 동적 메시지 생성
        warnings = [d.get("class", "경고등") for d in detections]
        desc = f"계기판에 {', '.join(warnings)} 등이 감지되었습니다. ({reason} 분석 모드)"
        
        return {
            "description": desc,
            "recommendation": "안전 주행을 위해 가까운 시일 내에 전문가 점검을 받으십시오."
        }

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
        response = await _get_client().chat.completions.create(
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
    if should_use_fallback():
        reason = "MOCK" if os.getenv("MOCK_LLM", "false").lower() == "true" else "Local"
        print(f"[LLM {reason}] generate_exterior_report")
        
        if not mappings:
            return {
                "description": f"차량 외관 상태가 전반적으로 양호합니다. ({reason} 분석 모드)",
                "recommendation": "안전 주행을 유지하며 정기적인 세차 및 외관 관리를 권장합니다."
            }
            
        # 동적 메시지 생성
        damage_summary = []
        for m in mappings:
            part = m.get('part', '알 수 없는 부위')
            dmg = m.get('damage_type', '파손')
            damage_summary.append(f"{part} {dmg}")
            
        desc = f"차량 외관에서 {', '.join(damage_summary)} 등이 발견되었습니다. ({reason} 분석 모드)"
        
        return {
            "description": desc,
            "recommendation": "가까운 정비소에서 견적을 받아보시는 것을 권장합니다."
        }

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
        response = await _get_client().chat.completions.create(
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
    if should_use_fallback():
        reason = "MOCK" if os.getenv("MOCK_LLM", "false").lower() == "true" else "Local"
        print(f"[LLM {reason}] interpret_tire_status")
        
        issues = [s.get('class', '') for s in status_list if s.get('class') != 'normal']
        
        if not issues:
             return {
                "description": f"타이어의 상태가 마모 한계 내에 있으며 정상입니다. ({reason} 분석 모드)",
                "recommendation": "공기압 체크와 타이어 위치 교환을 주기적으로 실시하십시오."
            }
            
        desc = f"타이어에서 {', '.join(issues)} 상태가 감지되었습니다. ({reason} 분석 모드)"
        return {
            "description": desc,
            "recommendation": "타이어 전문점에서 상세 점검을 받으십시오."
        }

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
        response = await _get_client().chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": PROMPT}],
            response_format={"type": "json_object"},
            max_tokens=500
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"[LLM Tire Error] {e}")
        return {"description": "타이어 상태 정보를 처리하는 도중 오류가 발생했습니다.", "recommendation": "공기압 및 트레드 상태를 수동으로 확인하십시오."}


# ---------------------------------------------------------
# 4. Active Learning용 라벨 생성 (Training Data Generation)
# ---------------------------------------------------------

async def generate_training_labels(s3_url: str, domain: str) -> dict:
    """
    [Active Learning] 저신뢰 이미지에 대해 LLM이 정답 라벨 생성
    
    Args:
        s3_url: 이미지 S3 URL
        domain: 도메인 (engine, dashboard, tire, exterior)
    
    Returns:
        {"labels": [{"class": "...", "bbox": [...]}], "status": "..."}
    """
    DOMAIN_PROMPTS = {
        "engine": "엔진룸 부품(Battery, Oil_Cap, Radiator 등)을 찾아 바운딩 박스를 제시하세요.",
        "dashboard": "켜진 경고등(Check_Engine, Low_Tire_Pressure 등)을 식별하세요.",
        "tire": "타이어 상태(normal, worn, cracked, flat)를 판단하세요.",
        "exterior": "차량 파손 부위(scratch, dent, crack)와 위치(Front_Bumper 등)를 찾으세요."
    }
    
    PROMPT = f"""
    이 차량 이미지를 분석하여 AI 학습용 라벨을 생성하세요.
    도메인: {domain}
    
    작업 지시: {DOMAIN_PROMPTS.get(domain, "차량 관련 객체를 식별하세요.")}
    
    [출력 형식 - JSON]
    {{
        "labels": [
            {{"class": "객체명", "bbox": [x_center, y_center, width, height]}}
        ],
        "status": "NORMAL" | "WARNING" | "CRITICAL"
    }}
    
    bbox는 이미지 크기 대비 0~1 사이 비율로 표현하세요.
    """
    
    try:
        response = await _get_client().chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": [
                    {"type": "text", "text": PROMPT},
                    {"type": "image_url", "image_url": {"url": s3_url}}
                ]}
            ],
            response_format={"type": "json_object"},
            max_tokens=800,
            timeout=30.0
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"[LLM Training Labels Error] {e}")
        return {"labels": [], "status": "ERROR"}


async def generate_audio_labels(s3_url: str, audio_bytes: Optional[bytes] = None) -> dict:
    """
    [Active Learning] 저신뢰 오디오에 대해 LLM이 정답 라벨 생성
    
    Args:
        s3_url: 오디오 S3 URL
        audio_bytes: 이미 다운로드된 오디오 바이트 (선택)
    
    Returns:
        {"label": "진단명", "category": "카테고리", "status": "..."}
    """
    PROMPT = """
    이 차량 소리를 분석하여 AI 학습용 라벨을 생성하세요.
    
    [분류 카테고리]
    - ENGINE: 엔진 관련 (노킹, 미스파이어 등)
    - BRAKES: 브레이크 관련 (스키, 갈리는 소리)
    - SUSPENSION: 서스펜션 관련 (덜컹, 쿵쿵)
    - EXHAUST: 배기 관련 (터진 소리, 비정상 배기음)
    - NORMAL: 정상 구동음
    
    [출력 형식 - JSON]
    {
        "label": "구체적_진단명 (예: Engine_Knock)",
        "category": "카테고리명",
        "status": "NORMAL" | "FAULTY",
        "confidence": 0.0 ~ 1.0
    }
    """
    
    try:
        # 오디오 데이터 준비
        if audio_bytes is None:
            async with httpx.AsyncClient(timeout=10.0) as httpx_client:
                audio_response = await httpx_client.get(s3_url)
                audio_response.raise_for_status()
                audio_data = base64.b64encode(audio_response.content).decode('utf-8')
        else:
            audio_data = base64.b64encode(audio_bytes).decode('utf-8')
        
        response = await _get_client().chat.completions.create(
            model="gpt-4o-audio-preview",
            modalities=["text", "audio"],
            audio={"voice": "alloy", "format": "wav"},
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": PROMPT},
                        {
                            "type": "input_audio",
                            "input_audio": {"data": audio_data, "format": "wav"}
                        }
                    ]
                }
            ]
        )
        
        content = response.choices[0].message.audio.transcript
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            return json.loads(match.group())
        return {"label": "UNKNOWN", "category": "UNKNOWN", "status": "ERROR"}
        
    except Exception as e:
        print(f"[LLM Audio Labels Error] {e}")
        return {"label": "UNKNOWN", "category": "UNKNOWN", "status": "ERROR"}