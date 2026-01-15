# app/services/hertz.py
import librosa
import soundfile as sf
import io
import os

def process_to_16khz(audio_input):
    """
    모든 음성 데이터를 16,000Hz(16kHz) 모노(Mono) 파일로 변환합니다.
    YAMNet, AST 모델 및 대부분의 Audio LLM이 요구하는 표준 규격입니다.
    """
    try:
        # 1. 파일 로드 및 16kHz로 리샘플링 (sr=16000)
        # librosa는 자동으로 오디오를 로드하며 지정된 속도로 변환합니다.
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