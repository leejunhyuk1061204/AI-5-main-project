import librosa
import soundfile as sf
import io
import shutil
import subprocess
import httpx

# ============================================================
# [핵심] ffmpeg subprocess를 직접 호출하여 임의 포맷 → WAV 변환
# librosa/soundfile의 백엔드(libsndfile)는 m4a를 지원하지 않으므로
# ffmpeg를 직접 subprocess로 호출하여 WAV bytes를 얻는 방식을 사용
# ============================================================
def _convert_with_ffmpeg_subprocess(data: bytes) -> bytes | None:
    """
    ffmpeg subprocess를 통해 임의 오디오 포맷 → 16kHz mono WAV bytes 변환.
    M4A(MP4 컨테이너)는 stdin pipe로 전달 시 seek 불가 문제가 있으므로
    임시 파일을 사용합니다.
    """
    import tempfile
    import os
    
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        print("[hertz.py] ffmpeg를 찾을 수 없습니다. ffmpeg가 시스템 PATH에 등록되어 있는지 확인하십시오.")
        return None

    # 임시 파일로 먼저 저장 (M4A/MP4는 seek가 필요하므로 stdin pipe 사용 불가)
    tmp_input = None
    try:
        suffix = ".m4a"  # ffmpeg가 포맷 힌트 없이도 인식 가능하도록
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
            f.write(data)
            tmp_input = f.name

        result = subprocess.run(
            [
                ffmpeg_path,
                "-y",
                "-i", tmp_input,   # 임시 파일에서 읽기
                "-ar", "16000",     # 샘플레이트 16kHz
                "-ac", "1",         # 모노
                "-f", "wav",        # 출력 포맷
                "pipe:1"            # stdout으로 출력
            ],
            capture_output=True,
            timeout=30
        )

        if result.returncode != 0:
            stderr_msg = result.stderr.decode("utf-8", errors="ignore")[-500:]
            print(f"[hertz.py] ffmpeg 변환 실패 (returncode={result.returncode}): {stderr_msg}")
            return None

        wav_bytes = result.stdout
        print(f"[hertz.py] ffmpeg subprocess 변환 완료: {len(wav_bytes):,} bytes WAV")
        
        if len(wav_bytes) < 1000:  # 비정상적으로 작은 경우 경고
            print(f"[hertz.py] 경고: 변환된 WAV가 너무 작습니다 ({len(wav_bytes)} bytes). 원본 파일 확인 필요.")
            return None
        
        return wav_bytes

    except subprocess.TimeoutExpired:
        print("[hertz.py] ffmpeg subprocess timeout (30s 초과)")
        return None
    except Exception as e:
        print(f"[hertz.py] ffmpeg subprocess 오류: {e}")
        return None
    finally:
        if tmp_input and os.path.exists(tmp_input):
            os.unlink(tmp_input)  # 임시 파일 정리



def _detect_format(magic: bytes) -> str:
    """매직 넘버로 오디오 포맷 감지"""
    if b"RIFF" in magic and b"WAVE" in magic:
        return "wav"
    elif b"ID3" in magic or b"\xff\xfb" in magic[:2]:
        return "mp3"
    elif b"ftypM4A" in magic or b"ftypmp42" in magic or b"ftyp" in magic:
        return "m4a"
    elif b"fLaC" in magic:
        return "flac"
    elif b"<?xml" in magic or b"<Error>" in magic:
        return "xml_error"
    return "unknown"


async def process_to_16khz(audio_input):
    """
    모든 음성 데이터를 16,000Hz(16kHz) 모노(Mono) 파일로 변환합니다. (Async Wrapper)
    """
    import asyncio
    loop = asyncio.get_running_loop()
    
    def _sync_process(inp):
        try:
            y, sr = librosa.load(inp, sr=16000)
            buffer = io.BytesIO()
            sf.write(buffer, y, 16000, format='WAV')
            buffer.seek(0)
            print(f"[hertz.py] 리샘플링 완료: 16,000Hz (WAV)")
            return buffer
        except Exception as e:
            print(f"[hertz.py] 리샘플링 중 오류 발생: {e}")
            return None

    if isinstance(audio_input, str) and audio_input.startswith("http"):
        print(f"[hertz.py] S3 URL 감지: 다운로드 시작... ({audio_input})")
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.get(audio_input)
                response.raise_for_status()
                audio_input = io.BytesIO(response.content)
            except Exception as e:
                print(f"[hertz.py] 다운로드 실패: {e}")
                return None

    return await loop.run_in_executor(None, _sync_process, audio_input)


async def convert_bytes_to_16khz(audio_bytes: bytes):
    """
    오디오 바이트 데이터를 16,000Hz(16kHz) 모노 WAV로 변환합니다. (Async Wrapper)
    WAV/FLAC은 librosa로, M4A/MP3/AAC 등은 ffmpeg subprocess로 직접 변환합니다.
    """
    import asyncio
    loop = asyncio.get_running_loop()

    def _sync_convert(data: bytes):
        magic = data[:32]
        fmt = _detect_format(magic)
        print(f"[hertz.py] 포맷 감지: {fmt.upper()} ({len(data)} bytes)")

        if fmt == "xml_error":
            print(f"[hertz.py] S3 에러 응답 감지: {data.decode('utf-8', errors='ignore')[:200]}")
            return None

        # WAV, FLAC은 libsndfile이 직접 지원 → librosa 사용
        if fmt in ("wav", "flac"):
            try:
                audio_stream = io.BytesIO(data)
                y, sr = librosa.load(audio_stream, sr=16000)
                buffer = io.BytesIO()
                sf.write(buffer, y, 16000, format='WAV')
                buffer.seek(0)
                print(f"[hertz.py] librosa 변환 완료 ({fmt.upper()} → WAV 16kHz)")
                return buffer
            except Exception as e:
                print(f"[hertz.py] librosa 변환 실패 ({fmt}): {e} → ffmpeg fallback 시도")
                # fallback to ffmpeg

        # M4A, MP3, AAC 등 → ffmpeg subprocess로 직접 변환
        print(f"[hertz.py] {fmt.upper()} 포맷 감지 → ffmpeg subprocess로 변환 시작")
        wav_bytes = _convert_with_ffmpeg_subprocess(data)
        if wav_bytes:
            return io.BytesIO(wav_bytes)
        
        print(f"[hertz.py] 모든 변환 방법 실패 (포맷: {fmt.upper()})")
        return None

    return await loop.run_in_executor(None, _sync_convert, audio_bytes)