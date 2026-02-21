#!/usr/bin/env python3
# ai/scripts/audio/analyze_all_classes.py
"""
[파일 용도] 모든 클래스(Normal, Starter, Engine, Brake)에 대한 전처리 전후 비교 분석
4가지 클래스의 대표 샘플을 자동으로 찾아 4행 그리드로 시각화합니다.
"""

import sys
import os
import glob
import random
import numpy as np
import librosa
import librosa.display
import matplotlib.pyplot as plt

# 프로젝트 루트 추가
sys.path.insert(0, os.getcwd())

# 전처리 함수 임포트
from ai.app.services.audio.audio_preprocessing import preprocess_array
from ai.scripts.audio.config import TRAIN_DATA_DIR

def load_audio(path, sr=16000):
    y, _ = librosa.load(path, sr=sr)
    return y

def compute_mel_spectrogram(audio, sr=16000):
    mel_spec = librosa.feature.melspectrogram(y=audio, sr=sr, n_mels=128, fmax=8000)
    mel_spec_db = librosa.power_to_db(mel_spec, ref=np.max)
    return mel_spec_db

def find_sample_for_class(class_name):
    """
    클래스별 샘플 파일 찾기
    1. ai/data/audio/train/{class_name}/*.wav
    2. ai/data/audio/train/abnormal/{class_name}/*.wav (구조에 따라)
    """
    # 1. Direct path (e.g. train/normal)
    pattern1 = os.path.join(TRAIN_DATA_DIR, class_name, "*.wav")
    files = glob.glob(pattern1)
    
    # 2. Abnormal subfolder (e.g. train/abnormal/engine)
    if not files:
        pattern2 = os.path.join(TRAIN_DATA_DIR, "abnormal", class_name, "*.wav")
        files = glob.glob(pattern2)
        
    # 3. Fallback (recursively search)
    if not files:
        pattern3 = os.path.join(TRAIN_DATA_DIR, "**", f"*{class_name}*.wav")
        files = glob.glob(pattern3, recursive=True)
        
    if files:
        choice = random.choice(files)
        print(f"✅ Found {class_name}: {os.path.basename(choice)}")
        return choice
    else:
        print(f"❌ Could not find sample for {class_name}")
        return None

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Analyze 4 audio classes (Normal, Starter, Engine, Brake)")
    parser.add_argument("--normal", help="Path to Normal audio file", default=None)
    parser.add_argument("--starter", help="Path to Starter audio file", default=None)
    parser.add_argument("--engine", help="Path to Engine audio file", default=None)
    parser.add_argument("--brake", help="Path to Brake audio file", default=None)
    args = parser.parse_args()

    classes = ["normal", "starter", "engine", "brake"]
    sr = 16000
    
    fig, axes = plt.subplots(4, 2, figsize=(15, 12))
    plt.subplots_adjust(hspace=0.4, wspace=0.2)
    
    manual_paths = {
        "normal": args.normal,
        "starter": args.starter,
        "engine": args.engine,
        "brake": args.brake
    }

    for i, cls in enumerate(classes):
        # 0. User Provided Path?
        path = manual_paths[cls]
        
        if path:
            if not os.path.exists(path):
                print(f"⚠️  Provided path not found for {cls}: {path}")
                path = None # Fallback to auto-find
            else:
                print(f"✅ Using User Provided File for {cls}: {path}")

        # 1. Auto Find (Fallback)
        if path is None:
            path = find_sample_for_class(cls)
        
        if path is None:
            # Skip checking if file not found
            continue
            
        # 1. Load Raw
        raw_audio = load_audio(path, sr)
        
        # 2. Preprocess
        # Normal은 speech masking 적용, 결함은 미적용 (실제 학습 로직 반영)
        label_name = cls if cls == "normal" else "abnormal" # preprocess_array logic
        # OR explicitly pass label name to trigger condition
        # preprocess_array uses: is_normal = (label_name.lower() == "normal")
        proc_audio, _ = preprocess_array(raw_audio, sr, label_name=cls)
        
        # 3. Plot - Waveform Comparison
        ax_wave = axes[i, 0]
        ax_wave.set_title(f"{cls.capitalize()} - Waveform Comparison")
        librosa.display.waveshow(raw_audio, sr=sr, ax=ax_wave, alpha=0.5, label="Raw Signal", color='skyblue')
        librosa.display.waveshow(proc_audio, sr=sr, ax=ax_wave, alpha=0.7, label="Filtered (80-7500Hz)", color='red')
        ax_wave.legend(loc='upper right')
        ax_wave.set_xlabel("Time")
        ax_wave.set_ylim(-1, 1)

        # 4. Plot - Filtered Spectrogram
        ax_spec = axes[i, 1]
        ax_spec.set_title(f"{cls.capitalize()} - Filtered Spectrogram")
        mel_db = compute_mel_spectrogram(proc_audio, sr)
        img = librosa.display.specshow(mel_db, x_axis='time', y_axis='mel', sr=sr, fmax=8000, ax=ax_spec)
        fig.colorbar(img, ax=ax_spec, format='%+2.0f dB')
        
    output_file = "audio_analysis_all.png"
    plt.tight_layout()
    plt.savefig(output_file, dpi=150)
    print(f"\n🖼️  Analysis saved to {output_file}")
    # plt.show() # Uncomment if running locally with GUI

if __name__ == "__main__":
    random.seed(42) # For reproducibility
    main()
