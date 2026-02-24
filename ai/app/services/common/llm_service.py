# ai/app/services/llm_service.py
"""
AI 분석 결과 해석 및 리포트 생성 서비스 (LLM)

[역할]
1. 전문가급 진단: YOLO, PatchCore 등의 수치적 결과를 사람이 이해할 수 있는 자연어로 변환합니다.
2. 멀티 모달 분석: 시각(Vision)과 청각(Audio) 데이터를 모두 처리하며, 복합적인 상황을 추론합니다.
3. 범용 분석(Fallback): 전용 AI 모델이 없거나 확신도가 낮을 때 GPT-5가 직접 사진을 보고 판단합니다.

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
from ai.app.services.audio.hertz import convert_bytes_to_16khz

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

def strip_markdown(content: str) -> str:
    """Markdown 코드 블록(```json ... ```) 제거 헬퍼"""
    if not content: return ""
    # ```json ... ``` 또는 ``` ... ``` 블록 제거
    content = re.sub(r'```(?:json)?\s*(.*?)\s*```', r'\1', content, flags=re.DOTALL)
    return content.strip()

# ---------------------------------------------------------
# 1. 시각 전문 진단 (GPT-5 Vision)
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

    [결함 분류 기준]
    - LEAK: 누유, 액체 흔적 (오일, 냉각수)
    - CORROSION: 녹, 산화, 부식
    - PHYSICAL: 균열, 찌그러짐, 파손
    - WEAR: 벨트 마모, 호스 경화
    - UNKNOWN: 특징 불명확

    [출력 형식 - JSON만]
    {{
        "defect_category": "LEAK|CORROSION|PHYSICAL|WEAR|UNKNOWN",
        "defect_label": "구체적_라벨명",
        "severity": "MINOR|WARNING|CRITICAL"
    }}
    """
    
    if should_use_fallback():
        reason = "MOCK" if os.getenv("MOCK_LLM", "false").lower() == "true" else "Local"
        print(f"[LLM {reason}] suggest_anomaly_label (URL): {part_name}")
        return {
            "defect_category": "UNKNOWN",
            "defect_label": "Analysis_Unavailable",
            "severity": "WARNING",
            "is_mock": True
        }
    
    try:
        response = await _get_client().chat.completions.create(
            model="gpt-4o", # [Stability] gpt-5 unstable. Use 4o.
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": [
                    {"type": "text", "text": "이 부품의 이상 영역을 분석해주세요."},
                    {"type": "image_url", "image_url": {"url": crop_url}}, # Presigned URL
                    {"type": "image_url", "image_url": {"url": heatmap_url}} # Presigned URL
                ]}
            ],
            response_format={"type": "json_object"},
            max_completion_tokens=500,
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
            "recommended_action": "육안 점검 권장",
            "is_mock": True
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

    [판단 기준]
    1. **NORMAL (정상)**: 먼지나 일반적인 사용감 정도.
    2. **ANOMALY (이상)**: 누유, 파손, 부식 등 명확한 결함.

    [결함 분류 기준]
    - LEAK: 누유, 액체 흔적
    - CORROSION: 녹, 산화, 부식
    - PHYSICAL: 균열, 찌그러짐, 파손
    - WEAR: 벨트 마모, 호스 경화
    - UNKNOWN: 특징 불명확

    [절대 규칙]
    1. 정상이면 defect_category를 "NORMAL"로 설정.
    2. 반드시 아래 JSON 형식으로만 응답.

    [출력 형식 - JSON만]
    {{
        "defect_category": "NORMAL|LEAK|CORROSION|PHYSICAL|WEAR|UNKNOWN",
        "defect_label": "구체적_라벨명",
        "severity": "NORMAL|MINOR|WARNING|CRITICAL"
    }}
    """
    
    if should_use_fallback():
        reason = "MOCK" if os.getenv("MOCK_LLM", "false").lower() == "true" else "Local"
        print(f"[LLM {reason}] suggest_anomaly_label: {part_name}")
        return {
            "defect_category": "UNKNOWN",
            "defect_label": "Analysis_Unavailable",
            "severity": "WARNING",
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
            model="gpt-4o", # [High Reliability] Vision + JSON Complex Task -> 4o 권장
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content}
            ],
            response_format={"type": "json_object"},
            max_completion_tokens=500,
            timeout=30.0
        )
        content = response.choices[0].message.content
        
         # [Guard] Empty Check
        if not content or content.strip() == "":
            print(f"[LLM Anomaly Base64] Error: Empty response from LLM")
            return {
                "defect_category": "UNKNOWN",
                "defect_label": "Analysis_Failed",
                "severity": "WARNING",
                "is_mock": True
            }

        return json.loads(content)
        
    except json.JSONDecodeError as e:
        print(f"[LLM Anomaly Base64] JSON Parsing Failed. Raw: {content}")
        return {
            "defect_category": "UNKNOWN",
            "defect_label": "Analysis_Failed",
            "severity": "WARNING",
            "is_mock": True
        }
    except Exception as e:
        print(f"[LLM Anomaly Base64 Error] {e}")
        return {
            "defect_category": "UNKNOWN",
            "defect_label": "Analysis_Failed",
            "severity": "WARNING",
            "is_mock": True
        }


async def call_openai_vision(s3_url: str, prompt: str) -> Dict[str, Any]:
    """
    [범용 Vision API 호출 함수]
    
    이미지 URL과 커스텀 프롬프트를 받아 GPT-5 Vision으로 분석합니다.
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
        return {
            "wear_level_pct": 20,
            "wear_status": "GOOD",
            "critical_issues": None,
            "description": f"이미지 데이터 분석 결과가 양호합니다. ({reason} 분석 모드)",
            "recommendation": "안전 주행을 위해 정기적인 점검을 유지하십시오.",
            "is_replacement_needed": False,
            "is_mock": True
        }

    try:
        response = await _get_client().chat.completions.create(
            model="gpt-4o", # [Stability] gpt-5 unstable. Use 4o.
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": [
                    {"type": "text", "text": "이 이미지를 분석해주세요."},
                    {"type": "image_url", "image_url": {"url": s3_url}}
                ]}
            ],
            response_format={"type": "json_object"},
            max_completion_tokens=1000,
            timeout=30.0
        )
        
        content = response.choices[0].message.content
        result = json.loads(content)
        return result
        
    except json.JSONDecodeError as e:
        print(f"[LLM Vision] JSON 파싱 오류: {e}")
        return {"status": "ERROR", "error": "JSON 파싱 실패", "is_mock": True}
    except Exception as e:
        print(f"[LLM Vision Error] {e}")
        return {"status": "ERROR", "error": str(e), "is_mock": True}

async def analyze_general_image(s3_url: str) -> VisualResponse:
    """
    [Path B: Fallback / 범용 분석]
    YOLO가 놓쳤거나, 별도 모델이 없는 이미지에 대한 LLM 분류.
    - DASHBOARD (계기판 경고등) 포함: 별도 YOLO 학습 없이 LLM이 분류
    - ENGINE 포함: Hard Mining용
    """
    SYSTEM_PROMPT = """
    당신은 'Car-Sentry 시각 분석 팀'입니다. 제공된 이미지를 분류하십시오.

    [분류 기준]
    1. VEHICLE 관련: DASHBOARD, EXTERIOR, TIRE, ENGINE, ETC
    2. IRRELEVANT: 차량과 무관한 이미지

    [상태 판단]
    - NORMAL: 정상
    - WARNING: 주의 필요
    - CRITICAL: 즉시 조치 필요

    [출력 형식 - JSON만]
    {
        "type": "VEHICLE" | "IRRELEVANT",
        "sub_type": "DASHBOARD" | "EXTERIOR" | "TIRE" | "ENGINE" | "ETC",
        "status": "NORMAL" | "WARNING" | "CRITICAL"
    }
    """
    if should_use_fallback():
        reason = "MOCK" if os.getenv("MOCK_LLM", "false").lower() == "true" else "Local"
        print(f"[LLM {reason}] analyze_general_image")
        return VisualResponse(
            status="NORMAL",
            analysis_type="LLM_FALLBACK",
            category="GENERAL",
            data={},
            is_mock=True
        )

    try:
        response = await _get_client().chat.completions.create(
            model="gpt-4o",   # [High Reliability] gpt-5 unstable for JSON fallbacks. Forced to 4o.  
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": [
                    {"type": "text", "text": "이 이미지를 분류하고 진단해주세요."},
                    {"type": "image_url", "image_url": {"url": s3_url}}
                ]}
            ],
            response_format={"type": "json_object"},
            max_completion_tokens=800,
            timeout=30.0
        )
        
        content = response.choices[0].message.content
        
        # [Guard] Empty Response Check
        if not content or content.strip() == "":
            print(f"[LLM General] Empty response received.")
            return VisualResponse(
                status="ERROR",
                analysis_type="LLM_GENERAL",
                category="ERROR",
                data={},
                is_mock=True
            )

        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            print(f"[LLM General] JSON Parsing Failed. Raw: {content}")
            return VisualResponse(
                status="NORMAL",
                analysis_type="LLM_GENERAL",
                category="ETC",
                data={},
                is_mock=True
            )

        # Map LLM result to VisualResponse
        # IRRELEVANT 처리
        if result.get("type") == "IRRELEVANT":
             return VisualResponse(
                status="ERROR",
                analysis_type="LLM_GENERAL",
                category="IRRELEVANT",
                data={},
                is_mock=True
            )

        return VisualResponse(
            status=result.get("status", "WARNING"),
            analysis_type="LLM_GENERAL",
            category=result.get("sub_type", "ETC"),
            data={}
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
            data={},
            is_mock=True
        )

# ---------------------------------------------------------
# 2. 청각 전문 진단 (GPT-5 Audio)
# ---------------------------------------------------------
async def analyze_audio_with_llm(s3_url: str, audio_bytes: Optional[bytes] = None) -> AudioResponse:
    SYSTEM_PROMPT = """
    당신은 'Car-Sentry 소음·진동(NVH) 분석 팀'의 수석 엔지니어입니다. 
    오디오 데이터에서 기계적인 이상 징후를 소리만으로 찾아내십시오.

    [분류 Category]
    - ENGINE: 엔진 소리 (노킹, 밸브)
    - SUSPENSION: 서스펜션 (찌그덕, 덜컡)
    - BRAKES: 브레이크 (스끌, 갈림)
    - EXHAUST: 배기 (머플러)
    - TIRES_WHEELS_AUDIO: 타이어/휠 (주행 소음, 베어링)
    - BODY: 차체 (풍절음, 잡소리)
    - UNKNOWN_AUDIO: 확신없음
    
    [데이터 품질 대응]
    - 소음 과다 시 status를 "RE_RECORD_REQUIRED"로 설정.

    [출력 형식 - JSON만]
    {
        "diagnosed_label": "진단명",
        "category": "분류명",
        "status": "NORMAL" | "WARNING" | "CRITICAL" | "RE_RECORD_REQUIRED",
        "confidence": 0.0 ~ 1.0
    }
    """
    if should_use_fallback():
        reason = "MOCK" if os.getenv("MOCK_LLM", "false").lower() == "true" else "Local"
        print(f"[LLM {reason}] analyze_audio_with_llm")
        return AudioResponse(
            status="NORMAL",
            analysis_type="LLM_AUDIO",
            category="ENGINE",
            confidence=0.9,
            is_critical=False,
            detail=AudioDetail(
                diagnosed_label="NORMAL_SOUND"
            )
        )
   
    try:
        if audio_bytes is None:
            async with httpx.AsyncClient(timeout=10.0) as httpx_client:
                audio_response = await httpx_client.get(s3_url)
                audio_response.raise_for_status()
                audio_bytes = audio_response.content

        # [Fix] 확실한 WAV 변환 (m4a, mp3 대응)
        converted_buffer = await convert_bytes_to_16khz(audio_bytes)
        
        if converted_buffer:
            audio_data = base64.b64encode(converted_buffer.getvalue()).decode('utf-8')
            audio_format = "wav"
        else:
            # 변환 실패 시: 원본이 OpenAI가 확실히 지원하는 형식(wav, mp3)인지 체크
            magic = audio_bytes[:32] # Increased for more reliable ftyp detection
            if (b"RIFF" in magic and b"WAVE" in magic):
                audio_data = base64.b64encode(audio_bytes).decode('utf-8')
                audio_format = "wav"
            elif (b"ID3" in magic or b"\xff\xfb" in magic[:2]):
                audio_data = base64.b64encode(audio_bytes).decode('utf-8')
                audio_format = "mp3"
            else:
                # [Diagnostic] 어떤 포맷인지 확인하여 사용자에게 안내
                detected_fmt = "UNKNOWN"
                if b"ftypM4A" in magic or b"ftypmp42" in magic: detected_fmt = "M4A"
                elif b"fLaC" in magic: detected_fmt = "FLAC"
                
                print(f"[LLM Audio Error] 지원하지 않는 오디오 형식({detected_fmt})이며 변환에도 실패했습니다. (ffmpeg 설치/PATH 확인 필요).")
                return AudioResponse(
                    status="ERROR",
                    analysis_type="CONVERSION_FAILED",
                    category="UNKNOWN_AUDIO",
                    detail=AudioDetail(diagnosed_label="FAULTY_SOUND"),
                    confidence=0.0,
                    is_critical=False
                )

        # [Correct] Audio Input via 'chat.completions.create'
        response = await _get_client().chat.completions.create(
            model="gpt-4o-audio-preview",  # [Model Update] gpt-4o-audio-preview for audio input
            modalities=["text"], # [Optimization] Text output only
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": SYSTEM_PROMPT + "\n\n이 소리를 진단하고 반드시 JSON 포맷으로 응답하세요."},
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": audio_data,
                                "format": audio_format # [Fix] Use detected format
                            }
                        }
                    ]
                }
            ],
            timeout=45.0 # [Adjustment] Audio processing takes longer
        )
        
        content = strip_markdown(response.choices[0].message.content)

        
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group())
            except json.JSONDecodeError:
                result = {"status": "FAULTY", "diagnosed_label": "Unknown"}
        else:
            result = {"status": "FAULTY", "diagnosed_label": "Unknown"}

        current_status = result.get("status", "FAULTY")

        return AudioResponse(
            status=current_status,
            analysis_type="LLM_AUDIO",
            category=result.get("category", "ENGINE"),
            detail=AudioDetail(
                diagnosed_label="NORMAL_SOUND" if current_status == "NORMAL" else "FAULTY_SOUND"
            ),
            confidence=float(result.get("confidence", 0.8)),
            is_critical=(current_status != "NORMAL")
        )
    except Exception as e:
        print(f"[LLM Audio Error] {e}")
        return AudioResponse(
            status="ERROR",
            analysis_type="LLM_AUDIO",
            category="UNKNOWN_AUDIO",
            detail=AudioDetail(diagnosed_label="FAULTY_SOUND"),
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
                "recommendation": "안전 운행 하십시오.",
                "is_mock": True
            }
        
        # 동적 메시지 생성
        warnings = [d.get("class", "경고등") for d in detections]
        desc = f"계기판에 {', '.join(warnings)} 등이 감지되었습니다. ({reason} 분석 모드)"
        
        return {
            "description": desc,
            "recommendation": "안전 주행을 위해 가까운 시일 내에 전문가 점검을 받으십시오.",
            "is_mock": True
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
            model="gpt-4o", # [Stability] gpt-5 unstable.
            messages=[{"role": "user", "content": PROMPT}],
            response_format={"type": "json_object"},
            max_completion_tokens=600
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"[LLM Dashboard Error] {e}")
        return {"description": "계기판 경고등 분석 중 오류가 발생했습니다.", "recommendation": "안전한 곳에 정차 후 수동 점검 바랍니다.", "is_mock": True}
        


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
            dmg = m.get('damage', '파손') # [Fix] key mismatch fix
            damage_summary.append(f"{part} {dmg}")
            
        desc = f"차량 외관에서 {', '.join(damage_summary)} 등이 발견되었습니다. ({reason} 분석 모드)"
        
        return {
            "description": desc,
            "recommendation": "가까운 정비소에서 견적을 받아보시는 것을 권장합니다.",
            "is_mock": True
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
            model="gpt-4o", # [Stability] gpt-5 failures causing fallback issues. Use 4o.
            messages=[{"role": "user", "content": PROMPT}],
            response_format={"type": "json_object"},
            max_completion_tokens=600
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"[LLM Exterior Error] {e}")
        # [Fallback] LLM 실패 시에도 YOLO 감지 결과는 전달해야 함
        try:
            summary = []
            for m in mappings:
                p = m.get('part', '부위')
                d = m.get('damage', '파손')
                summary.append(f"{p} {d}")
            fallback_desc = f"{', '.join(summary)}이(가) 감지되었습니다. (AI 상세 기술 실패)"
        except:
            fallback_desc = "파손이 감지되었으나 상세 내용을 불러올 수 없습니다."
            
        return {
            "description": fallback_desc,
            "recommendation": "가까운 정비소에서 육안 검사를 권장합니다.",
            "is_mock": True
        }


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
                "recommendation": "공기압 체크와 타이어 위치 교환을 주기적으로 실시하십시오.",
                "is_mock": True
            }
            
        desc = f"타이어에서 {', '.join(issues)} 상태가 감지되었습니다. ({reason} 분석 모드)"
        return {
            "description": desc,
            "recommendation": "타이어 전문점에서 상세 점검을 받으십시오.",
            "is_mock": True
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
            model="gpt-4o", # [Stability] Standardizing to 4o
            messages=[{"role": "user", "content": PROMPT}],
            response_format={"type": "json_object"},
            max_completion_tokens=500
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"[LLM Tire Error] {e}")
        return {"description": "타이어 상태 정보를 처리하는 도중 오류가 발생했습니다.", "recommendation": "공기압 및 트레드 상태를 수동으로 확인하십시오.", "is_mock": True}


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
        "exterior": "차량의 파손 부위(scratch, dent, crack, broken_lamp)를 찾아 바운딩 박스를 그리세요. 좌표는 대략적이어도 됩니다."
    }
    
    PROMPT = f"""
    당신은 Car-Sentry 학습 데이터 생성기입니다.
    다음 도메인의 이미지를 분석하여 학습용 정답 라벨(Ground Truth)을 생성하십시오.
    
    도메인: {domain}
    상세 지시: {DOMAIN_PROMPTS.get(domain, "차량 관련 객체를 식별하세요.")}
    
    [중요 가이드]
    - Exterior(외관) 분석 시, 찌그러짐(dent), 긁힘(scratch), 깨짐(broken) 등이 보이면 반드시 박스를 생성하십시오.
    - 놓치는 것보다 과감하게 탐지하는(Recall 우선) 것이 학습 데이터 생성에 유리합니다.
    - 부품명을 정확히 모르겠으면 'Unknown_Part'나 'Damage_Area'로 라벨링하십시오.

    [절대 규칙]
    1. 반드시 아래 JSON 형식으로만 응답해야 합니다. 설명이나 마크다운(```json 등)을 포함하지 마십시오.
    2. 식별된 객체가 없거나 분석이 불가능한 경우에도 **반드시** 아래 실패 포맷을 그대로 출력하십시오.
    3. 모든 `class`명은 반드시 **영문 언더바 형식(English_With_Underscore)**으로 작성하십시오. (한글 및 공백 금지)
    
    [분석 불가능 시 출력]
    {{
        "labels": [],
        "status": "FAILED"
    }}

    [정상 출력 형식 - JSON]
    {{
        "labels": [
             {{ "part": "English_Part_Name", "damage": "English_Damage_Name", "bbox": [x1, y1, x2, y2] }}
        ],
        "status": "NORMAL" | "WARNING" | "CRITICAL"
    }}

    [예시 - Exterior]
    {{
        "labels": [
             {{ "part": "Front_Bumper", "damage": "Scratch", "bbox": [0.1, 0.2, 0.4, 0.5] }}
        ],
        "status": "WARNING"
    }}
    
    [예시 - Dashboard]
    {{
        "labels": [
             {{ "part": "Check_Engine", "damage": "Indicator_On", "bbox": [0.4, 0.4, 0.6, 0.6] }}
        ],
        "status": "WARNING"
    }}
    
    bbox는 이미지 크기 대비 0.0 ~ 1.0 사이의 정규화된 [좌측상단x, 좌측상단y, 우측하단x, 우측하단y] 좌표(Ratio)입니다.
    """
    
    try:
        response = await _get_client().chat.completions.create(
            model="gpt-4o", # [Critical] gpt-5 fails to generate coordinates reliably. Use 4o.
            messages=[
                {"role": "system", "content": PROMPT},
                {"role": "user", "content": [
                    {"type": "text", "text": "이미지 분석 및 라벨 생성"},
                    {"type": "image_url", "image_url": {"url": s3_url}}
                ]}
            ],
            response_format={"type": "json_object"},
            max_completion_tokens=1000,
            timeout=30.0
        )
        
        content = response.choices[0].message.content
        
        # [Guard 1] Empty Response Check
        if not content or content.strip() == "":
            print(f"[LLM Training Labels] Error: Empty response from LLM (Length: 0)")
            return {"labels": [], "status": "FAILED", "reason": "LLM_EMPTY_RESPONSE", "is_mock": True}

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            print(f"[LLM Training Labels] JSON Parsing Failed. Raw Content: {content}")
            return {"labels": [], "status": "FAILED", "reason": "JSON_PARSE_ERROR", "is_mock": True}
            
    except Exception as e:
        print(f"[LLM Training Labels Error] {e}")
        return {"labels": [], "status": "FAILED", "reason": str(e), "is_mock": True}


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
    Analyze this vehicle sound and generate labels for AI training.
    
    [Classification Logic]
    - Identify if the sound is NORMAL or FAULTY.
    - Status: "NORMAL" for healthy vehicle sounds, "FAULTY" for any mechanical issues.
    
    [Categories]
    - ENGINE, BRAKES, SUSPENSION, EXHAUST, BODY, UNKNOWN
    
    [Output Rules]
    1. Respond ONLY in JSON format.
    2. Respond with "NORMAL_SOUND" or "FAULTY_SOUND" for the label field.
    3. Ensure all fields are in English.
    
    [Output JSON Format]
    {
        "label": "NORMAL_SOUND" | "FAULTY_SOUND",
        "category": "ENGINE" | "BRAKES" | "SUSPENSION" | "EXHAUST" | "BODY" | "UNKNOWN",
        "status": "NORMAL" | "WARNING" | "CRITICAL",
        "confidence": 0.0 ~ 1.0,
        "reason": "Brief explanation of the sound in English"
    }
    """
    
    try:
        # 오디오 데이터 준비
        if audio_bytes is None:
            async with httpx.AsyncClient(timeout=10.0) as httpx_client:
                audio_response = await httpx_client.get(s3_url)
                audio_response.raise_for_status()
                audio_bytes = audio_response.content

        # [Fix] 확실한 WAV 변환 (Active Learning 데이터 품질 보정)
        converted_buffer = await convert_bytes_to_16khz(audio_bytes)
        if converted_buffer:
            audio_data = base64.b64encode(converted_buffer.getvalue()).decode('utf-8')
            audio_format = "wav"
        else:
            # 변환 실패 시: 원본이 OpenAI가 확실히 지원하는 형식(wav, mp3)인지 체크
            magic = audio_bytes[:32]
            if (b"RIFF" in magic and b"WAVE" in magic):
                audio_data = base64.b64encode(audio_bytes).decode('utf-8')
                audio_format = "wav"
            elif (b"ID3" in magic or b"\xff\xfb" in magic[:2]):
                audio_data = base64.b64encode(audio_bytes).decode('utf-8')
                audio_format = "mp3"
            else:
                detected_fmt = "UNKNOWN"
                if b"ftypM4A" in magic or b"ftypmp42" in magic: detected_fmt = "M4A"
                elif b"fLaC" in magic: detected_fmt = "FLAC"
                
                print(f"[LLM Audio Labels Error] 지원하지 않는 형식({detected_fmt})이며 변환에도 실패했습니다.")
                return {"label": "UNKNOWN", "category": "UNKNOWN", "status": "CONVERSION_FAILED"}
        
        # [Fix] API Parameter & Model update
        response = await _get_client().chat.completions.create(
            model="gpt-4o-audio-preview",
            modalities=["text"], # Text output only (No audio output needed for labeling)
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": PROMPT},
                        {
                            "type": "input_audio",
                            "input_audio": {"data": audio_data, "format": audio_format} # [Fix] Use detected format
                        }
                    ]
                }
            ]
        )
        
        # [Fix] Response format (gpt-4o-audio-preview with text modality returns content)
        content = response.choices[0].message.content
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            return json.loads(match.group())
        return {"label": "UNKNOWN", "category": "UNKNOWN", "status": "ERROR", "is_mock": True}
        
    except Exception as e:
        print(f"[LLM Audio Labels Error] {e}")
        return {"label": "UNKNOWN", "category": "UNKNOWN", "status": "ERROR"}