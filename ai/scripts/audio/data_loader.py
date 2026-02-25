# ai/scripts/audio/data_loader.py
"""
[파일 용도] 오디오 데이터 로더 (Dataset & DataLoader)
PyTorch의 Dataset 클래스를 상속받아 오디오 파일을 로드하고, 전처리(Mel Spectrogram 변환 등)를 수행합니다.
Method A (계층적 분류)를 위한 라벨링 처리 및 데이터 증강(Augmentation) 로직도 포함되어 있습니다.
"""
import os
import pickle
import hashlib
import numpy as np
import librosa
import scipy.signal
import torch
import concurrent.futures
from collections import Counter
from sklearn.model_selection import train_test_split
import random
from audiomentations import Compose, AddGaussianSNR, TimeStretch, PitchShift, Gain, ClippingDistortion, AddBackgroundNoise, AddShortNoises

from ai.app.services.audio.audio_preprocessing import preprocess_array
from ai.scripts.audio.config import (
    TRAIN_DATA_DIR, TEST_DATA_DIR, NOISE_DATA_DIR, TYPE_LABELS, type2id,
    COMMON_CONFIG, DEVICE, IS_RUNPOD
)

# ──────────── 전처리 유틸 ────────────

def highpass_filter(y, sr, cutoff=50):
    b, a = scipy.signal.butter(4, cutoff, 'highpass', fs=sr)
    return scipy.signal.filtfilt(b, a, y)

# ── Advanced Augmentation Settings (audiomentations) ──

def get_augmentation_pipeline(intensity="medium"):
    """
    [v4.0] Advanced Augmentation Pipeline using audiomentations.
    Addresses shortcut learning (shortcut to recording environment) and destructive fine-tuning.
    Refined parameters based on DCASE/MIMII best practices.
    """
    # [v4.5] Noise Augmentation (Aggressively Expand 300 samples -> 3000+)
    noise_augment = Compose([
        TimeStretch(min_rate=0.75, max_rate=1.25, p=0.8),          # ±25%
        PitchShift(min_semitones=-5, max_semitones=5, p=0.7),      # ±5 semitones
        Gain(min_gain_db=-10, max_gain_db=10, p=1.0),              # ±10dB
        AddGaussianSNR(min_snr_db=10, max_snr_db=30, p=0.5),       # White noise on background noise
    ], p=1.0)

    if intensity == "high":
        return Compose([
            # 1. Background Noise + Self-Augmentation (The Core Breaker)
            AddBackgroundNoise(
                sounds_path=NOISE_DATA_DIR, 
                min_snr_db=12, 
                max_snr_db=27, 
                p=0.5,
                noise_transform=noise_augment 
            ) if os.path.exists(NOISE_DATA_DIR) else AddGaussianSNR(p=0.0),
            
            # 2. Pitch Shift (Key change) - reduced range
            PitchShift(min_semitones=-4, max_semitones=4, p=0.3),
            
            # 3. Time Stretch (Speed change)
            TimeStretch(min_rate=0.82, max_rate=1.18, p=0.2),
            
            # 4. Gain (Volume change)
            Gain(min_gain_db=-6, max_gain_db=6, p=0.3),
            ClippingDistortion(min_percentile_threshold=0, max_percentile_threshold=20, p=0.25),
        ])
    else: # medium (default for training)
        return Compose([
            AddBackgroundNoise(
                sounds_path=NOISE_DATA_DIR, 
                min_snr_db=15, 
                max_snr_db=35, 
                p=0.4,
                noise_transform=noise_augment
            ) if os.path.exists(NOISE_DATA_DIR) else AddGaussianSNR(p=0.0),

            AddGaussianSNR(min_snr_db=15, max_snr_db=40, p=0.3),
            TimeStretch(min_rate=0.9, max_rate=1.1, p=0.2),
            PitchShift(min_semitones=-1.5, max_semitones=1.5, p=0.3),
            Gain(min_gain_db=-6, max_gain_db=6, p=0.3),
            ClippingDistortion(min_percentile_threshold=0, max_percentile_threshold=10, p=0.2),
        ])

AUGMENTER = None # Global instance initialized in Dataset

# Augmentation Parameters for SpecAugment
AUG_PARAMS = {
    "high": {"freq_mask": 30, "time_mask": 40},
    "medium": {"freq_mask": 20, "time_mask": 30},
    "low": {"freq_mask": 10, "time_mask": 15},
}

def apply_spec_augment(mel, intensity="medium"):
    """SpecAugment (Frequency & Time Masking)"""
    p = AUG_PARAMS.get(intensity, AUG_PARAMS["medium"])
    n_mels, n_steps = mel.shape
    mel = mel.copy()
    
    # Frequency Masking
    f = np.random.randint(0, p["freq_mask"])
    f0 = np.random.randint(0, n_mels - f)
    mel[f0:f0+f, :] = 0
    
    # Time Masking
    t = np.random.randint(0, p["time_mask"])
    t0 = np.random.randint(0, n_steps - t)
    mel[:, t0:t0+t] = 0
    return mel

# ──────────── 데이터 목록 로딩 ────────────

def get_data_list(base_dir):
    """base_dir에서 데이터 목록 생성 (신규 상태별 구조 및 기존 평면 구조 모두 지원)"""
    print(f"📂 Scanning Dataset: {base_dir}", flush=True)
    data_list = []
    EXTENSIONS = (".wav", ".m4a", ".mp3", ".ogg", ".flac")

    # 1. [New Structure Check] car dataset/ (braking state, idle state, startup state)
    mapping = {
        "braking state": "brake",
        "idle state": "engine",
        "startup state": "starter"
    }
    
    found_new = False
    for state_folder, domain in mapping.items():
        state_path = os.path.join(base_dir, state_folder)
        if os.path.exists(state_path):
            found_new = True
            for sub_folder in os.listdir(state_path):
                sub_path = os.path.join(state_path, sub_folder)
                if not os.path.isdir(sub_path): continue
                is_abnormal = 0 if sub_folder.lower().startswith("normal") else 1
                for f in os.listdir(sub_path):
                    if f.lower().endswith(EXTENSIONS):
                        data_list.append({
                            "path": os.path.join(sub_path, f),
                            "type": domain,
                            "abnormal": is_abnormal,
                            "sub_class": sub_folder
                        })

    # 2. [Legacy Structure Check] normal/ abnormal/
    if not found_new:
        print("ℹ️ New structure not found. Falling back to legacy structure (normal/abnormal).", flush=True)
        # Normal
        normal_dir = os.path.join(base_dir, "normal")
        if os.path.exists(normal_dir):
            for f in os.listdir(normal_dir):
                if f.lower().endswith(EXTENSIONS):
                    data_list.append({
                        "path": os.path.join(normal_dir, f),
                        "type": "normal",
                        "abnormal": 0
                    })
        # Abnormal
        abnormal_dir = os.path.join(base_dir, "abnormal")
        if os.path.exists(abnormal_dir):
            for cls in ["starter", "engine", "brake"]:
                cls_dir = os.path.join(abnormal_dir, cls)
                if os.path.exists(cls_dir):
                    for f in os.listdir(cls_dir):
                        if f.lower().endswith(EXTENSIONS):
                            data_list.append({
                                "path": os.path.join(cls_dir, f),
                                "type": cls,
                                "abnormal": 1
                            })

    if len(data_list) == 0:
        print(f"⚠️ Warning: No audio files found in {base_dir}")

    counts = Counter([f"{x['type']}_{'abnormal' if x['abnormal'] else 'normal'}" for x in data_list])
    print(f"📊 Detailed Stats: {dict(counts)} (total: {len(data_list)})", flush=True)
    return data_list

# ──────────── 전처리 캐시 ────────────
CACHE_DIR = os.path.join(os.path.dirname(TRAIN_DATA_DIR), "cache", "preprocessed")

def _cache_key(item, arch):
    key = f"{os.path.basename(item['path'])}_{arch or 'cnn'}"
    return os.path.join(CACHE_DIR, hashlib.md5(key.encode()).hexdigest() + ".pkl")

# ──────────── 오디오 전처리 ────────────

def preprocess_item(item, arch=None, fe=None, use_cache=True):
    """단일 오디오 파일 전처리 (캐시 지원)"""
    # 캐시 확인
    cache_path = _cache_key(item, arch)
    if use_cache and os.path.exists(cache_path):
        try:
            with open(cache_path, "rb") as f:
                return pickle.load(f)
        except Exception:
            pass  # 캐시 손상 시 재처리

    try:
        y, sr = librosa.load(item["path"], sr=16000)
        y = highpass_filter(y, sr, cutoff=50)
        y = y / (np.mean(np.abs(y)) + 1e-6) 

        y_proc, _ = preprocess_array(y, sr, label_name="normal" if item["abnormal"] == 0 else "abnormal")

        # VAD 실패 시 원본 사용 (안정성)
        if y_proc is None or len(y_proc) == 0:
            y_proc = y

        y_proc = librosa.util.fix_length(y_proc, size=16000 * 5)  # 5초 고정

        # Mel Spectrogram
        # [v4.9] YAMNet (AudioSet) Standard Params
        if arch == "yamnet":
            # YAMNet: sr=16k, n_fft=400, hop=160 (10ms), n_mels=64
            # log-mel with offset=0.001 (AudioSet style)
            mel = librosa.feature.melspectrogram(
                y=y_proc, sr=16000, n_fft=400, hop_length=160, n_mels=64, fmin=125, fmax=7500
            )
            # Log-Mel (Stabilized)
            mel_log = np.log(mel + 0.001)
            # Normalization (YAMNet typically uses simple offset, but we standardized z-score)
            mel_norm = (mel_log - np.mean(mel_log)) / (np.std(mel_log) + 1e-6)
        else:
            # Existing CNN/PaSST Logic (128 mels)
            mel = librosa.feature.melspectrogram(y=y_proc, sr=16000, n_mels=128, fmax=8000, power=1.0)
            mel_pcen = librosa.pcen(mel, sr=16000)
            mel_norm = (mel_pcen - mel_pcen.mean()) / (mel_pcen.std() + 1e-6)

        # AST/Fusion용 Feature 미리 계산
        ast_input = None
        if arch in ["ast", "fusion"] and fe is not None:
            ast_input = fe(y_proc, sampling_rate=16000, return_tensors="pt")["input_values"].squeeze(0)

        result = {
            "audio": y_proc,
            "mel": mel_norm,
            "ast_input": ast_input,
            "type": item["type"],
            "abnormal": float(item["abnormal"]),
        }

        # 캐시 저장
        if use_cache:
            os.makedirs(CACHE_DIR, exist_ok=True)
            try:
                with open(cache_path, "wb") as f:
                    pickle.dump(result, f)
            except Exception:
                pass  # 캐시 저장 실패는 무시

        return result
    except Exception as e:
        print(f"⚠️  [Preprocess Error] {item['path']}: {e}", flush=True)
        return None


# ──────────── Dataset ────────────

class AudioDataset(torch.utils.data.Dataset):
    def __init__(self, data_list, arch, feature_extractor=None, is_training=False, desc="Dataset", background_paths=None):
        print(f"🛠️  [{desc}] Processing {len(data_list)} items...", flush=True)
        self.is_training = is_training
        self.arch = arch # [v4.9] Store architecture for runtime augmentation
        self.background_paths = background_paths # [v4.7] List of normal file paths for mixing
        self.intensity = COMMON_CONFIG.get("aug_intensity", "medium")
        self.augmenter = get_augmentation_pipeline(self.intensity) if is_training else None

        workers = 4 if IS_RUNPOD else 2
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(preprocess_item, item, arch, feature_extractor) for item in data_list]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        self.data = [r for r in results if r is not None]
        # 캐시 히트율 출력
        n_cached = sum(1 for item in data_list if os.path.exists(_cache_key(item, arch)))
        print(f"✅ [{desc}] Ready: {len(self.data)} items (cache hit: {n_cached}/{len(data_list)})", flush=True)

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        item = self.data[idx].copy()
        y = item["audio"]
        sr = 16000
        
        # Train-only (or Forced) Augmentation
        if self.is_training:
            # [v4.7] Source Bias Mitigation: Mix Site Background into Youtube/Abnormal Samples
            # If current sample is abnormal (likely Youtube), mix in a normal (likely Site) sample as noise.
            if item['abnormal'] == 1 and self.background_paths and random.random() < 0.7: # 70% chance
                try:
                    noise_path = random.choice(self.background_paths)
                    noise, _ = librosa.load(noise_path, sr=sr)
                    
                    # Fix length to match y
                    if len(noise) < len(y):
                        noise = np.tile(noise, int(np.ceil(len(y)/len(noise))))
                    noise = noise[:len(y)]
                    
                    # Normalize noise volume to be lower than signal (SNR-like)
                    # We want background, not to overpower the defect.
                    # Target: Noise is 20% ~ 40% of the mix
                    alpha = random.uniform(0.2, 0.4) 
                    
                    # Energy matching
                    y_rms = np.sqrt(np.mean(y**2) + 1e-9)
                    n_rms = np.sqrt(np.mean(noise**2) + 1e-9)
                    if n_rms > 0:
                        noise = noise * (y_rms / n_rms) * alpha
                        
                    y = y + noise
                    # Normalize again to prevent clipping
                    max_val = np.max(np.abs(y))
                    if max_val > 1.0:
                        y = y / max_val
                        
                except Exception as e:
                    pass # Ignore mixing errors, proceed with original

            if self.augmenter:
                # 1. Advanced Waveform Aug (audiomentations)
                y = self.augmenter(samples=y, sample_rate=sr)
            
            # 2. Gain Aug (Subtle adjustment)
            gain = np.random.uniform(0.8, 1.2)
            y = y * gain
            
            # 3. Re-calculate Mel from augmented waveform
            if self.arch == "yamnet":
                # [v4.9] YAMNet Style: 64 mels, log(mel + 0.001)
                mel_raw = librosa.feature.melspectrogram(
                    y=y, sr=sr, n_fft=400, hop_length=160, n_mels=64, fmin=125, fmax=7500
                )
                mel_log = np.log(mel_raw + 0.001)
                mel = (mel_log - np.mean(mel_log)) / (np.std(mel_log) + 1e-6)
            else:
                # Default (CNN/PaSST): 128 mels, PCEN
                mel_raw = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=128, fmax=8000, power=1.0)
                mel_pcen = librosa.pcen(mel_raw, sr=sr)
                mel = (mel_pcen - mel_pcen.mean()) / (mel_pcen.std() + 1e-6)
            
            # 4. SpecAugment
            mel = apply_spec_augment(mel, intensity=self.intensity)
        else:
            mel = item["mel"]

        # type_label: abnormal만 분류, normal=-100 (ignore)
        lbl_t = type2id[item["type"]] if item["type"] in type2id else -100

        return {
            "ast_input": item["ast_input"] if item["ast_input"] is not None else torch.zeros(1),
            "mel_input": torch.tensor(mel, dtype=torch.float32),
            "raw_audio": torch.tensor(y, dtype=torch.float32),
            "type_label": torch.tensor(lbl_t, dtype=torch.long),
            "abnormal_label": torch.tensor(item["abnormal"], dtype=torch.long),
        }


# ──────────── 데이터셋 균형 조정 (Oversampling / Undersampling) ────────────
def balance_dataset(data, samples_per_cls, name="Dataset"):
    """Undersampling을 제거하고, 필요한 경우에만 Oversampling 수행 (데이터 손실 방지)"""
    if samples_per_cls <= 0:
        return data
        
    balanced_data = []
    class_keys = sorted(set([x["type"] for x in data]))
    
    print(f"⚖️  Balancing {name}: target {samples_per_cls} per class (Oversampling)...", flush=True)
    
    for cls in class_keys:
        cls_data = [x for x in data if x["type"] == cls]
        if not cls_data:
            continue
        
        n_samples = len(cls_data)
        if n_samples >= samples_per_cls:
            balanced_data.extend(cls_data)
        else:
            multiplier = samples_per_cls // n_samples
            remainder = samples_per_cls % n_samples
            balanced_data.extend(cls_data * multiplier)
            balanced_data.extend(cls_data[:remainder])
    return balanced_data

def balance_to_minimum(data, name="Dataset", target_count=30):
    """
    [Revised Strategy v3.2/v3.5]
    - 클래스별로 최대 target_count(기본 30)개의 샘플을 무작위 추출 (Undersampling).
    - 샘플이 target_count보다 적은 경우, 오버샘플링 없이 원본 전체 사용.
    - 고정 시드(42)를 사용하여 일관성 유지.
    """
    if not data:
        return []

    from collections import Counter
    # Ensure every entry has a type, fallback to 'unknown' if missing
    for x in data:
        if "type" not in x:
            x["type"] = "normal" if x.get("abnormal") == 0 else "unknown"

    counts = Counter([x["type"] for x in data])
    class_keys = sorted(counts.keys())
    
    if not class_keys:
        return []

    print(f"⚖️  Creating Balanced Subset for {name}: Target={target_count} per class...", flush=True)
    
    # 고정 시드를 사용하여 평가의 일관성 유지
    np.random.seed(42)
    
    balanced_data = []
    for cls in class_keys:
        cls_data = [x for x in data if x["type"] == cls]
        if not cls_data: continue
        
        # 원본 개수와 타겟 개수 중 작은 값을 선택 (Oversampling 방지)
        num_to_sample = min(len(cls_data), target_count)
        indices = np.random.choice(len(cls_data), num_to_sample, replace=False)
        balanced_data.extend([cls_data[i] for i in indices])
        
        print(f"   - {cls:<10}: {len(cls_data):>4} -> {num_to_sample:>4}", flush=True)
        
    print(f"✅ Balanced {name} ready (Total: {len(balanced_data)})", flush=True)
    return balanced_data


# ──────────── DataLoader 생성 ────────────

def create_dataloaders(arch, feature_extractor=None, batch_size=None, samples_per_class=None):
    """결합 계층화 분할(Class+Source) 및 샘플수 균형 조정(Balancing) 지원"""
    if batch_size is None:
        batch_size = 32 if IS_RUNPOD else COMMON_CONFIG["batch_size"]
    
    if samples_per_class is None:
        samples_per_class = COMMON_CONFIG.get("samples_per_class", 0)

    # 1. 모든 데이터 수집 및 메타 데이터 생성
    if TRAIN_DATA_DIR == TEST_DATA_DIR:
        all_data = get_data_list(TRAIN_DATA_DIR)
    else:
        all_data = get_data_list(TRAIN_DATA_DIR) + get_data_list(TEST_DATA_DIR)
    
    if not all_data:
        raise ValueError(f"❌ No audio data found in {TRAIN_DATA_DIR}")
    
    for item in all_data:
        # 출처 및 그룹 태깅
        fname = os.path.basename(item["path"]).lower()
        item["source"] = "site" if "visc_" in fname else "youtube"
        
        # Group ID 추출: 같은 유튜브 영상에서 나온 조각들은 하나의 그룹으로 묶음
        if item["source"] == "site":
            item["group_id"] = fname
        else:
            parts = fname.split("_")
            if fname.startswith("ext_normal"):
                item["group_id"] = parts[2] if len(parts) >= 3 else fname
            elif "normal_idle" in fname:
                item["group_id"] = "_".join(parts[:3]) if len(parts) >= 3 else fname
            else:
                item["group_id"] = parts[1] if len(parts) >= 2 else fname

        # 계층화 키 생성
        item["stratify_key"] = f"{item['type']}_{item['source']}"

    # 2. 그룹 계층화 분할 (Group Stratified Split)
    def robust_group_split(data, train_ratio=0.7, val_ratio=0.1):
        """유튜브 원본 그룹(Video ID) 단위로 데이터를 분할하여 Leakage 방지 및 최소 분포 보장"""
        group_map = {} # gid -> skey
        for x in data:
            gid = x["group_id"]
            if gid not in group_map:
                group_map[gid] = x["stratify_key"]
        
        unique_gids = np.array(list(group_map.keys()))
        unique_keys = np.array([group_map[gid] for gid in unique_gids])
        
        train_gids, val_gids, test_gids = [], [], []
        
        for key in sorted(set(unique_keys)):
            g_in_key = unique_gids[unique_keys == key].tolist()
            n_g = len(g_in_key)
            np.random.seed(42)
            np.random.shuffle(g_in_key)
            
            # [Revised v3.6] Evaluation-Prioritized Split
            # 목표: Test, Val 각각 최소 30개 그룹 확보 (데이터가 충분할 경우)
            # 만약 데이터가 너무 적으면(예: 3개 미만) 기존처럼 1개씩이라도 할당
            if n_g >= 90: # 충분히 많으면 30씩 고정
                n_te = 30
                n_va = 30
            elif n_g >= 3: # 3개 이상이면 적어도 1개씩은 나누고 남은 비율로 30에 가깝게
                # Val/Test에 각각 총 데이터의 1/3까지는 우선 할당 (Train 고갈 방지 최소 마진)
                limit = n_g // 3
                n_te = min(30, limit)
                n_va = min(30, limit)
            else: # 3개 미만 (매우 희귀)
                if n_g == 1: n_te, n_va = 0, 0
                else: n_te, n_va = 1, 0
            
            n_tr = n_g - n_te - n_va
            
            train_gids.extend(g_in_key[:n_tr])
            val_gids.extend(g_in_key[n_tr : n_tr+n_va])
            test_gids.extend(g_in_key[n_tr+n_va:])
        
        # ── Group Leak 검증 (교차 오염 방지) ──
        train_set = set(train_gids)
        val_set = set(val_gids)
        test_set = set(test_gids)
        assert train_set.isdisjoint(val_set), f"❌ Train-Val Group Leak! {train_set & val_set}"
        assert train_set.isdisjoint(test_set), f"❌ Train-Test Group Leak! {train_set & test_set}"
        assert val_set.isdisjoint(test_set), f"❌ Val-Test Group Leak! {val_set & test_set}"
        print(f"✅ Group Leak Check Passed (Train: {len(train_set)}, Val: {len(val_set)}, Test: {len(test_set)} groups)", flush=True)
            
        train_out = [x for x in data if x["group_id"] in train_set]
        val_out = [x for x in data if x["group_id"] in val_set]
        test_out = [x for x in data if x["group_id"] in test_set]
        
        return train_out, val_out, test_out

    train_data, val_data, test_data = robust_group_split(all_data)

    # ──────────── 전체 샘플 분포 출력 ────────────
    print(f"🔍 Group-Level Split Analysis (Preventing Video Leakage):")
    for group_name, group_data in [("Train", train_data), ("Valid", val_data), ("Test", test_data)]:
        display_keys = [
            f"{x['type']}_{x['source']}" if x['abnormal'] == 0 else f"{x['type']}"
            for x in group_data
        ]
        counts = Counter(display_keys)
        # 그룹 개수도 함께 출력하여 밸런스 확인
        g_count = len(set([x["group_id"] for x in group_data]))
        print(f"   - {group_name} ({len(group_data)} clips, {g_count} groups): {dict(sorted(counts.items()))}")
        
        # 내부 안전성 점검
        internal_counts = Counter([x["stratify_key"] for x in group_data])
        low_samples = [k for k, v in internal_counts.items() if v < 2]
        if low_samples and group_name != "Train":
            print(f"     ⚠️  Low groups for: {low_samples}")

    # ──────────── 결함 샘플만 분포 출력 ────────────
    defect_train = [x for x in train_data if x["abnormal"] == 1]
    defect_val   = [x for x in val_data if x["abnormal"] == 1]
    defect_test  = [x for x in test_data if x["abnormal"] == 1]

    print(f"🔧 Defect-only Analysis (YouTube Source Grouping Applied):")
    for group_name, group_data in [("Train", defect_train), ("Valid", defect_val), ("Test", defect_test)]:
        counts = Counter([x["type"] for x in group_data])
        g_count = len(set([x["group_id"] for x in group_data]))
        print(f"   - {group_name} ({len(group_data)} clips, {g_count} videos): {dict(sorted(counts.items()))}")
        if len(group_data) == 0:
            print(f"     ⚠️  No defect samples in {group_name}!")

    # 3. 데이터셋 균형 조정 (Balancing)
    # [Revised Strategy - v3.2] 
    # - Train: Original distribution (samples_per_class=0 in config) + Loss Weighting
    # - Val/Test: Dual version (Original & Balanced Subset with Target 30)
    
    train_final = train_data
    val_data_final = val_data
    val_data_balanced = balance_to_minimum(val_data, name="Valid (Balanced Subset)", target_count=30)
    
    test_data_final = test_data
    test_data_balanced = balance_to_minimum(test_data, name="Test (Balanced Subset)", target_count=30)
    
    # ──────────── [v5.0] Oversampling (Balanced) ────────────
    # 목표: 모든 클래스가 ~170개 내외로 균형
    # starter(62) x3 = 186, engine(171) x1 = 171, brake(33) x5 = 165
    print(f"⚖️  Applying Oversampling (v5.0 Balanced): Starter x3, Brake x5")
    train_oversampled = []
    
    # Deterministic seed for reproduction
    rng = random.Random(42)
    
    for item in train_final:
        train_oversampled.append(item)
        if item['type'] == 'starter':
            # x3 = Original + 2 copies
            for _ in range(2): train_oversampled.append(item)
        elif item['type'] == 'brake':
            # x5 = Original + 4 copies
            for _ in range(4): train_oversampled.append(item)
            
    # Update train_final
    before_len = len(train_final)
    train_final = train_oversampled
    print(f"   before: {before_len} -> after: {len(train_final)} (Added {len(train_final) - before_len} replicas)")

    print(f"   - [Val/Test] Original for real performance, Balanced Subset (Target 30) for fair comparison.")

    # [v4.7] Collect Normal Paths for Background Mixing
    # We use ALL normal data (Train+Val+Test) as potential background sources because it's just noise.
    # Or strictly separate to avoid leaking validation noise?
    # Safer: Use only TRAIN Normal data.
    normal_train_paths = [x['path'] for x in train_data if x['abnormal'] == 0]
    print(f"🔊 Background Noise Source: {len(normal_train_paths)} normal files from Train set")

    # Dataset 생성
    train_ds = AudioDataset(train_final, arch, feature_extractor, is_training=True, desc="Train", background_paths=normal_train_paths)
    val_ds = AudioDataset(val_data_final, arch, feature_extractor, is_training=False, desc="Valid")
    test_ds = AudioDataset(test_data_final, arch, feature_extractor, is_training=False, desc="Test")

    pin = IS_RUNPOD
    nw = 4 if IS_RUNPOD else 0

    # DataLoader 생성 (shuffle/seed 통제)
    def seed_worker(worker_id):
        worker_seed = torch.initial_seed() % 2**32
        np.random.seed(worker_seed)
        import random
        random.seed(worker_seed)

    g = torch.Generator()
    g.manual_seed(42)

    train_loader = torch.utils.data.DataLoader(
        train_ds, batch_size=batch_size, shuffle=True, 
        pin_memory=pin, num_workers=nw, worker_init_fn=seed_worker, generator=g
    )
    val_loader = torch.utils.data.DataLoader(val_ds, batch_size=batch_size, pin_memory=pin, num_workers=nw)
    test_loader = torch.utils.data.DataLoader(test_ds, batch_size=batch_size, pin_memory=pin, num_workers=nw)
    
    # Balanced Subset Loaders
    val_bal_ds = AudioDataset(val_data_balanced, arch, feature_extractor, is_training=False, desc="Valid_Balanced")
    val_loader_balanced = torch.utils.data.DataLoader(val_bal_ds, batch_size=batch_size, pin_memory=pin, num_workers=nw)
    
    test_bal_ds = AudioDataset(test_data_balanced, arch, feature_extractor, is_training=False, desc="Test_Balanced")
    test_loader_balanced = torch.utils.data.DataLoader(test_bal_ds, batch_size=batch_size, pin_memory=pin, num_workers=nw)

    # Class Weights (Type Head) - Inverse Frequency (1 / count) 기반 보정
    # [Important] type_loss는 abnormal=1인 샘플만 기여하므로, abnormal 샘플만 필터링하여 가중치 계산
    defect_train = [x for x in train_data if x['abnormal'] == 1]
    type_counts = Counter([x['type'] for x in defect_train if x['type'] in TYPE_LABELS])
    total = sum(type_counts.values())
    n_classes = len(TYPE_LABELS)
    
    weights = []
    print(f"⚖️  Calculating Inverse Frequency Weights (Total: {total}):")
    # Find the maximum count for normalization
    max_val = max(type_counts.values()) if type_counts else 1.0 # Avoid division by zero if type_counts is empty
    
    for t in TYPE_LABELS:
        count = type_counts.get(t, 0) # Use .get to handle cases where a type might not be in defect_train
        if count > 0:
            inverse_freq = max_val / count
            # [v4.5] Aggressive Weighting (Starter x3.0, Brake x2.2)
            # [v4.6.1] Engine x2.5 (Fixed Zero Detection issue)
            if t == "starter":
                inverse_freq *= 3.0
            elif t == "brake":
                inverse_freq *= 2.2
            elif t == "engine":
                inverse_freq *= 2.5
            weights.append(inverse_freq)
        else:
            weights.append(1.0) # Assign a default weight if count is zero
    
    # Normalize weights to have a mean of 1
    weights = torch.FloatTensor(weights)
    if weights.sum() > 0:
        weights = weights / weights.mean() # Normalize to mean=1
    
    # Print final weights for verification
    for i, t in enumerate(TYPE_LABELS):
        count = type_counts.get(t, 0)
        print(f"   - {t}: count={count}, weight={weights[i]:.3f}")
        
    weights = torch.tensor(weights, device=DEVICE).float()

    return train_loader, val_loader, val_loader_balanced, test_loader, test_loader_balanced, weights