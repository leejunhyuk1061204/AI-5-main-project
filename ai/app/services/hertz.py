# app/services/hertz.py
import librosa
import soundfile as sf
import io
import requests

async def process_to_16khz(audio_input):
    """
    모든 음성 데이터를 16,000Hz(16kHz) 모노(Mono) 파일로 변환합니다. (Async Wrapper)
    """
    import asyncio
    loop = asyncio.get_running_loop()
    
    # 내부 동기 함수 정의
    def _sync_process(inp):
        try:
            # URL일 경우 다운로드 (requests는 동기이므로 여기서 처리 ok)
            if isinstance(inp, str) and inp.startswith("http"):
                print(f"[hertz.py] S3 URL 감지: 다운로드 시작... ({inp})")
                response = requests.get(inp)
                response.raise_for_status()
                inp = io.BytesIO(response.content)

            # 1. Librosa 로드 (Blocking)
            y, sr = librosa.load(inp, sr=16000)

            # 2. WAV 저장
            buffer = io.BytesIO()
            sf.write(buffer, y, 16000, format='WAV')
            buffer.seek(0)
            
            print(f"[hertz.py] 리샘플링 완료: 16,000Hz (WAV)")
            return buffer
        except Exception as e:
            print(f"[hertz.py] 리샘플링 중 오류 발생: {e}")
            return None

    # 별도 스레드에서 실행
    return await loop.run_in_executor(None, _sync_process, audio_input)

async def convert_bytes_to_16khz(audio_bytes: bytes):
    """
    오디오 바이트 데이터를 16,000Hz(16kHz) 모노 WAV로 변환합니다. (Async Wrapper)
    """
    import asyncio
    loop = asyncio.get_running_loop()

    def _sync_convert(data):
        try:
            audio_stream = io.BytesIO(data)
            y, sr = librosa.load(audio_stream, sr=16000)

            buffer = io.BytesIO()
            sf.write(buffer, y, 16000, format='WAV')
            buffer.seek(0)
            
            print(f"[hertz.py] 바이트 데이터 리샘플링 완료")
            return buffer
        except Exception as e:
            print(f"[hertz.py] 바이트 변환 중 오류: {e}")
            return None

    return await loop.run_in_executor(None, _sync_convert, audio_bytes)