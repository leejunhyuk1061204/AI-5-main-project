# app/api/v1/routes/test_router.py
from fastapi import APIRouter, UploadFile, File, HTTPException
from ai.app.services.local_service import process_visual_mock, process_audio_mock
from ai.app.schemas.visual_schema import VisualResponse
from ai.app.schemas.audio_schema import AudioResponse

router = APIRouter(prefix="/test/predict", tags=["Local Test"])

@router.post("/visual", response_model=VisualResponse)
async def analyze_visual_local(file: UploadFile = File(...)):
    """
    [Local Test] 이미지 파일 직접 수신 -> Mock 응답 반환
    """
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Invalid image file type")
    
    content = await file.read()
    return await process_visual_mock(content)

@router.post("/audio", response_model=AudioResponse)
async def analyze_audio_local(file: UploadFile = File(...)):
    """
    [Local Test] 오디오 파일 직접 수신 -> Mock 응답 반환
    """
    if not file.content_type.startswith("audio/"):
        # 오디오 타입 체크 완화 (wav, mp3, m4a 등)
        pass 
    
    content = await file.read()
    return await process_audio_mock(content)
