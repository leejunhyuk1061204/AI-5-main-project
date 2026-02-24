#!/usr/bin/env python3
# ai/scripts/audio/verify_preprocessing.py
"""
[파일 용도] 전처리(Preprocessing) 효과 검증 (A/B Test)

[목적]
원본 오디오와 전처리된 오디오의 Mel-Spectrogram을 시각적으로 비교하여
엔진 Harmonic 보존, Transient 유지, 음성 제거 효과를 검증합니다.

[사용법]
python ai/scripts/audio/verify_preprocessing.py --input ai/data/audio/processed/abnormal/engine/sample.wav
"""
import argparse
import sys
import os

# 프로젝트 루트 추가
sys.path.insert(0, os.getcwd())

import numpy as np
import librosa
import librosa.display
import matplotlib.pyplot as plt
from pathlib import Path


def load_audio(path: str, sr: int = 16000):
    """오디오 로드"""
    audio, _ = librosa.load(path, sr=sr)
    return audio


def get_preprocessed_audio(raw_audio: np.ndarray, sr: int = 16000):
    """동기 방식으로 전처리 파이프라인 실행"""
    from ai.app.services.audio.audio_preprocessing import preprocess_array
    
    # Single Source of Truth 기능 호출
    audio, _ = preprocess_array(
        raw_audio, sr,
        top_db=20,     # 검증 기본값
        min_gain=0.2,   # 검증 기본값
        base_attenuation=0.3
    )
    return audio


def compute_mel_spectrogram(audio: np.ndarray, sr: int = 16000):
    """Mel-Spectrogram 계산"""
    mel_spec = librosa.feature.melspectrogram(y=audio, sr=sr, n_mels=128)
    mel_spec_db = librosa.power_to_db(mel_spec, ref=np.max)
    return mel_spec_db


def plot_comparison(raw_audio, proc_audio, sr, output_path):
    """A/B 비교 플롯 생성"""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    # Waveform 비교
    axes[0, 0].set_title("Original Waveform")
    librosa.display.waveshow(raw_audio, sr=sr, ax=axes[0, 0], color='blue')
    
    axes[0, 1].set_title("Preprocessed Waveform")
    librosa.display.waveshow(proc_audio, sr=sr, ax=axes[0, 1], color='green')
    
    # Mel-Spectrogram 비교
    raw_mel = compute_mel_spectrogram(raw_audio, sr)
    proc_mel = compute_mel_spectrogram(proc_audio, sr)
    
    axes[1, 0].set_title("Original Mel-Spectrogram")
    img1 = librosa.display.specshow(raw_mel, x_axis='time', y_axis='mel', sr=sr, ax=axes[1, 0])
    fig.colorbar(img1, ax=axes[1, 0], format='%+2.0f dB')
    
    axes[1, 1].set_title("Preprocessed Mel-Spectrogram")
    img2 = librosa.display.specshow(proc_mel, x_axis='time', y_axis='mel', sr=sr, ax=axes[1, 1])
    fig.colorbar(img2, ax=axes[1, 1], format='%+2.0f dB')
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    print(f"[Verify] A/B 비교 이미지 저장: {output_path}")
    plt.show()


def compute_metrics(raw_audio, proc_audio, sr=16000):
    """품질 지표 계산"""
    # RMS 변화율
    raw_rms = np.sqrt(np.mean(raw_audio**2))
    proc_rms = np.sqrt(np.mean(proc_audio**2))
    rms_change = (proc_rms - raw_rms) / (raw_rms + 1e-8) * 100
    
    # Zero Crossing Rate (Transient 지표)
    raw_zcr = np.mean(librosa.feature.zero_crossing_rate(raw_audio))
    proc_zcr = np.mean(librosa.feature.zero_crossing_rate(proc_audio))
    zcr_change = (proc_zcr - raw_zcr) / (raw_zcr + 1e-8) * 100
    
    # Spectral Centroid (주파수 특성 변화)
    raw_centroid = np.mean(librosa.feature.spectral_centroid(y=raw_audio, sr=sr))
    proc_centroid = np.mean(librosa.feature.spectral_centroid(y=proc_audio, sr=sr))
    centroid_change = (proc_centroid - raw_centroid) / (raw_centroid + 1e-8) * 100
    
    # [추가] HNR Proxy: 저역(100~1000Hz) 에너지 / 전대역 에너지 비율
    def compute_hnr_proxy(audio, sr):
        """엔진 Harmonic 보존 지표: 저역 에너지 비율"""
        stft = np.abs(librosa.stft(audio))
        freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
        
        # 100Hz~1000Hz 대역 인덱스
        low_bin = np.argmax(freqs >= 100)
        high_bin = np.argmax(freqs >= 1000)
        
        low_energy = np.sum(stft[low_bin:high_bin, :] ** 2)
        total_energy = np.sum(stft ** 2) + 1e-8
        
        return low_energy / total_energy
    
    raw_hnr = compute_hnr_proxy(raw_audio, sr)
    proc_hnr = compute_hnr_proxy(proc_audio, sr)
    hnr_change = (proc_hnr - raw_hnr) / (raw_hnr + 1e-8) * 100
    
    print("\n" + "="*50)
    print("📊 A/B 검증 지표")
    print("="*50)
    print(f"RMS 에너지 변화:       {rms_change:+.2f}%")
    print(f"Zero Crossing Rate:   {zcr_change:+.2f}%")
    print(f"Spectral Centroid:    {centroid_change:+.2f}%")
    print(f"HNR Proxy (100~1kHz): {hnr_change:+.2f}%")
    print("="*50)
    
    # 품질 판정
    print("\n🔬 품질 판정:")
    if abs(centroid_change) < 10:
        print("  ✅ Harmonic 보존 양호 (Centroid 변화 10% 미만)")
    else:
        print("  ❌ Harmonic 손실 가능성 (Centroid 변화 10% 초과)")
    
    if abs(zcr_change) < 15:
        print("  ✅ Transient 보존 양호 (ZCR 변화 15% 미만)")
    else:
        print("  ⚠️ Transient 변화 주의 (ZCR 변화 15% 초과)")
    
    # [수정] HNR 비대칭 판정: 증가는 개선, 감소는 손실
    if hnr_change < -10:
        print("  ❌ 엔진 Harmonic 손실 가능성 (HNR 감소)")
    elif hnr_change > 40:
        print("  ⚠️ Harmonic 과강조 가능성 (필터 과함)")
    else:
        print("  ✅ 엔진 Harmonic 보존 또는 개선")



def main():
    parser = argparse.ArgumentParser(description="A/B 전처리 검증")
    parser.add_argument("--input", "-i", required=True, help="입력 오디오 파일 경로")
    parser.add_argument("--output", "-o", default=None, help="출력 이미지 경로 (기본: input_comparison.png)")
    args = parser.parse_args()
    
    input_path = args.input
    if not os.path.exists(input_path):
        print(f"[Error] 파일을 찾을 수 없습니다: {input_path}")
        sys.exit(1)
    
    output_path = args.output or str(Path(input_path).stem) + "_comparison.png"
    
    print(f"[Verify] 원본 로드: {input_path}")
    raw_audio = load_audio(input_path)
    
    print(f"[Verify] 전처리 수행 중...")
    proc_audio = get_preprocessed_audio(raw_audio)
    
    # 지표 계산
    compute_metrics(raw_audio, proc_audio)
    
    # 시각화
    plot_comparison(raw_audio, proc_audio, 16000, output_path)


if __name__ == "__main__":
    main()
