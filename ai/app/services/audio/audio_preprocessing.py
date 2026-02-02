# ai/app/services/audio/audio_preprocessing.py
"""
오디오 전처리 파이프라인 (Audio Preprocessing Pipeline)

[목표]
기계음 분석에 방해가 되는 요소(사람 목소리, 빗소리 등)를 제거하면서,
엔진의 Harmonic 및 Transient 특성은 보존합니다.

[파이프라인]
raw audio → resample(16kHz) → RMS silence trim → band-pass filter
→ VAD (speech ratio) → speech soft masking → spectral gating → feature extraction
"""
import numpy as np
import librosa
from scipy.signal import butter, sosfilt
from typing import Tuple, Optional
import io
import soundfile as sf


# =============================================================================
# 1. RMS 기반 Silence Trim
# =============================================================================
def trim_silence_rms(audio: np.ndarray, sr: int, top_db: int = 25) -> np.ndarray:
    """
    RMS 에너지 기반으로 앞뒤 무음 구간 제거.
    librosa.effects.trim의 내부 로직과 유사.
    """
    trimmed, _ = librosa.effects.trim(audio, top_db=top_db)
    print(f"[Preprocess] Silence Trim: {len(audio)} → {len(trimmed)} samples")
    return trimmed


# =============================================================================
# 2. Band-Pass Filter (약하게 적용)
# =============================================================================
def apply_bandpass_filter(
    audio: np.ndarray, sr: int, 
    low_freq: int = 80, high_freq: int = 7500, order: int = 3
) -> np.ndarray:
    """
    차량 결함음 주파수 대역(80Hz~7.5kHz)만 통과시키는 Band-pass 필터.
    - 80Hz 이하: 저역 잡음, 진동 노이즈 제거
    - 7.5kHz 이상: 고역 히스 노이즈 제거 (Nyquist=8kHz 미만으로 설정)
    - Order=3: 약하게 적용하여 Harmonic 손실 방지
    """
    nyquist = sr / 2
    low = low_freq / nyquist
    high = min(high_freq / nyquist, 0.99)  # Wn < 1.0 보장
    
    # SOS 필터 사용 (안정성 향상)
    sos = butter(order, [low, high], btype='band', output='sos')
    filtered = sosfilt(sos, audio)
    
    print(f"[Preprocess] Band-pass Applied: {low_freq}Hz ~ {high_freq}Hz (Order: {order})")
    return filtered.astype(np.float32)


# =============================================================================
# 3. VAD (Voice Activity Detection) 및 Speech Ratio 계산
# =============================================================================
def calculate_speech_ratio(audio: np.ndarray, sr: int) -> Tuple[float, np.ndarray]:
    """
    간단한 에너지 기반 VAD로 음성 구간 비율 계산.
    webrtcvad 대신 librosa 기반으로 구현하여 의존성 최소화.
    
    Returns:
        speech_ratio: 전체 오디오 중 음성(고에너지) 구간의 비율 (0.0 ~ 1.0)
        vad_mask: 프레임별 음성 활동 여부 (1=speech, 0=non-speech)
    """
    # 프레임 단위 RMS 에너지 계산
    frame_length = int(sr * 0.025)  # 25ms 프레임
    hop_length = int(sr * 0.010)    # 10ms hop
    
    rms = librosa.feature.rms(y=audio, frame_length=frame_length, hop_length=hop_length)[0]
    
    # 적응형 임계값 (평균 RMS의 1.5배)
    threshold = np.mean(rms) * 1.5
    
    # VAD 마스크 생성
    vad_mask = (rms > threshold).astype(np.float32)
    
    speech_ratio = np.mean(vad_mask)
    print(f"[Preprocess] VAD Speech Ratio: {speech_ratio:.2%}")
    
    return speech_ratio, vad_mask


# =============================================================================
# 4. Speech Soft Masking
# =============================================================================
def apply_speech_soft_masking(
    audio: np.ndarray, sr: int, vad_mask: np.ndarray, 
    base_attenuation: float = 0.3
) -> np.ndarray:
    """
    VAD 마스크로 식별된 '음성 구간'의 에너지를 부드럽게 감쇠.
    목소리 주파수(300Hz~3kHz) 대역만 타겟팅하여 기계음 보존.
    
    [개선] 적응형 감쇠: VAD 확신도에 따라 감쇠 강도 조절
    - speech 확실 → 더 많이 줄임
    - 애매 → 거의 건드리지 않음 (VAD 오탐 방지)
    """
    # STFT 변환
    stft = librosa.stft(audio)
    magnitude, phase = librosa.magphase(stft)
    
    # 주파수 빈별 인덱스 계산
    freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
    speech_low_bin = np.argmax(freqs >= 300)
    speech_high_bin = np.argmax(freqs >= 3000)
    
    # VAD 마스크를 STFT 시간축에 맞게 보간
    n_frames = magnitude.shape[1]
    vad_interp = np.interp(
        np.linspace(0, len(vad_mask) - 1, n_frames),
        np.arange(len(vad_mask)),
        vad_mask
    )
    
    # Soft Masking 적용 (음성 구간 + 음성 주파수 대역만)
    # [개선] 적응형 감쇠: VAD 확신도가 높을수록 더 많이 줄임
    for i, speech_prob in enumerate(vad_interp):
        if speech_prob > 0.3:  # 약한 임계값으로 완화
            # 적응형 감쇠: speech 확실할수록 더 크게 감쇠
            adaptive_attenuation = base_attenuation + (1 - base_attenuation) * (1 - speech_prob)
            magnitude[speech_low_bin:speech_high_bin, i] *= adaptive_attenuation
    
    # Inverse STFT
    masked_stft = magnitude * phase
    masked_audio = librosa.istft(masked_stft)
    
    print(f"[Preprocess] Speech Soft Masking Applied (base_attenuation: {base_attenuation})")
    return masked_audio


# =============================================================================
# 5. Spectral Gating (약하게 적용)
# =============================================================================
def apply_spectral_gating(
    audio: np.ndarray, sr: int, 
    threshold_factor: float = 0.1,
    min_gain: float = 0.2
) -> np.ndarray:
    """
    [개선] Soft Spectral Gating: 저에너지 성분을 부드럽게 감쇠.
    - Hard gate(0 or 1)가 아닌 Soft gate 적용
    - min_gain으로 완전 제거 방지 → 엔진 Harmonic 보존
    - 빗소리, 히스 등 정적 잡음은 눌리면서 기계음은 살아있음
    """
    # STFT 변환
    stft = librosa.stft(audio)
    magnitude, phase = librosa.magphase(stft)
    
    # 프레임별 최대값의 일정 비율을 임계값으로 설정
    threshold = np.max(magnitude, axis=0) * threshold_factor
    
    # [핵심 개선] Soft Gating: 완전 제거 대신 부드러운 감쇠
    # gain = magnitude / threshold (0~1 범위로 클리핑)
    # min_gain으로 완전 제거 방지
    gain = np.clip(magnitude / (threshold + 1e-8), 0.0, 1.0)
    gain = np.maximum(gain, min_gain)  # 최소 min_gain 보장
    
    gated_magnitude = magnitude * gain
    
    # Inverse STFT
    gated_stft = gated_magnitude * phase
    gated_audio = librosa.istft(gated_stft)
    
    print(f"[Preprocess] Soft Spectral Gating Applied (min_gain: {min_gain})")
    return gated_audio


# =============================================================================
# 통합 파이프라인
# =============================================================================
async def preprocess_audio_pipeline(
    audio_bytes: bytes, 
    enable_speech_mask: bool = True,
    enable_spectral_gate: bool = True
) -> bytes:
    """
    전체 전처리 파이프라인 실행.
    
    Args:
        audio_bytes: 원본 오디오 바이트
        enable_speech_mask: 음성 마스킹 활성화 여부
        enable_spectral_gate: 스펙트럴 게이팅 활성화 여부
    
    Returns:
        전처리된 오디오 WAV 바이트
    """
    import asyncio
    loop = asyncio.get_running_loop()
    
    def _sync_pipeline(data: bytes) -> bytes:
        try:
            # 1. Load & Resample to 16kHz
            audio_stream = io.BytesIO(data)
            audio, sr = librosa.load(audio_stream, sr=16000)
            print(f"[Preprocess] Loaded Audio: {len(audio)/sr:.2f}s at {sr}Hz")
            
            # 2. RMS Silence Trim
            audio = trim_silence_rms(audio, sr)
            
            # 3. Band-pass Filter (Light)
            audio = apply_bandpass_filter(audio, sr)
            
            # 4. VAD & Speech Ratio
            speech_ratio, vad_mask = calculate_speech_ratio(audio, sr)
            
            # 5. Speech Soft Masking (조건부)
            if enable_speech_mask and speech_ratio > 0.2:
                # 음성 비율이 20% 이상일 때만 마스킹 적용
                audio = apply_speech_soft_masking(audio, sr, vad_mask)
            
            # 6. Spectral Gating (Light)
            if enable_spectral_gate:
                audio = apply_spectral_gating(audio, sr)
            
            # 7. [추가] Per-sample RMS Normalization (모델 입력 스케일 보정)
            target_rms = 0.1  # 목표 RMS 레벨
            current_rms = np.sqrt(np.mean(audio**2)) + 1e-8
            audio = audio * (target_rms / current_rms)
            print(f"[Preprocess] RMS Normalized: {current_rms:.4f} → {target_rms}")
            
            # 8. Output to WAV Bytes
            buffer = io.BytesIO()
            sf.write(buffer, audio, 16000, format='WAV')
            buffer.seek(0)
            
            print(f"[Preprocess] Pipeline Complete. Output Length: {len(audio)/sr:.2f}s")
            return buffer.getvalue()
            
        except Exception as e:
            print(f"[Preprocess Error] {e}")
            # 실패 시 원본 반환 (Graceful Degradation)
            return data
    
    return await loop.run_in_executor(None, _sync_pipeline, audio_bytes)
