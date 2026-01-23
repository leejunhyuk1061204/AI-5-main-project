# app/services/hertz.py
import librosa
import soundfile as sf
import io
import requests

def process_to_16khz(audio_input):
    """
    모든 음성 데이터를 16,000Hz(16kHz) 모노(Mono) 파일로 변환합니다.
    YAMNet, AST 모델 및 대부분의 Audio LLM이 요구하는 표준 규격입니다.
    """
    try:
        # [추가됨] 만약 입력값이 "http"로 시작하는 URL이라면? -> 먼저 다운로드!
        if isinstance(audio_input, str) and audio_input.startswith("http"):
            print(f"[hertz.py] S3 URL 감지: 다운로드 시작... ({audio_input})")
            response = requests.get(audio_input)
            response.raise_for_status() # 다운로드 실패 시 에러 발생
            
            # 다운로드 받은 데이터를 메모리(BytesIO)에 담음
            audio_input = io.BytesIO(response.content)
        # 1. 파일 로드 (이제 URL이 아니라 메모리에 있는 파일 데이터를 읽음)
        y, sr = librosa.load(audio_input, sr=16000)

        # 2. 결과물을 메모리 버퍼(BytesIO)에 저장
        # 서버 용량을 아끼기 위해 물리적 파일을 만들지 않고 메모리에서 처리합니다.
        buffer = io.BytesIO()
        sf.write(buffer, y, 16000, format='WAV')
        buffer.seek(0)
        
        print(f"[hertz.py] 리샘플링 완료: 16,000Hz (WAV)")
        return buffer

    except Exception as e:
        print(f"[hertz.py] 리샘플링 중 오류 발생: {e}")
        return None

def convert_bytes_to_16khz(audio_bytes: bytes):
    """
    오디오 바이트 데이터를 16,000Hz(16kHz) 모노 WAV로 변환합니다.
    (이미 메모리에 로드된 데이터를 처리)
    """
    try:
        # 바이트 데이터를 BytesIO로 감싸서 librosa로 로드
        audio_stream = io.BytesIO(audio_bytes)
        y, sr = librosa.load(audio_stream, sr=16000)

        buffer = io.BytesIO()
        sf.write(buffer, y, 16000, format='WAV')
        buffer.seek(0)
        
        print(f"[hertz.py] 바이트 데이터 리샘플링 완료")
        return buffer

    except Exception as e:
        print(f"[hertz.py] 바이트 변환 중 오류: {e}")
        return None