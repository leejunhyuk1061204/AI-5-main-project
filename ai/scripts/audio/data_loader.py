# ai/scripts/audio/data_loader.py
"""
📦 공통 데이터 로딩 모듈 — Multi-Task 2-Head 지원

[Label Structure]
- abnormal: 0 (정상), 1 (비정상)
- type_label: starter=0, engine=1, brake=2, normal=-100 (ignore)
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

from ai.app.services.audio.audio_preprocessing import preprocess_array
from ai.scripts.audio.config import (
    TRAIN_DATA_DIR, TEST_DATA_DIR, TYPE_LABELS, type2id,
    COMMON_CONFIG, DEVICE, IS_RUNPOD
)

# ──────────── 전처리 유틸 ────────────

def highpass_filter(y, sr, cutoff=50):
    b, a = scipy.signal.butter(4, cutoff, 'highpass', fs=sr)
    return scipy.signal.filtfilt(b, a, y)

def apply_spec_augment(mel, time_mask_max=20, freq_mask_max=10):
    """SpecAugment (강화: time=20, freq=10)"""
    n_mels, n_steps = mel.shape
    mel = mel.copy()
    f = np.random.randint(0, freq_mask_max)
    f0 = np.random.randint(0, n_mels - f)
    mel[f0:f0+f, :] = 0
    t = np.random.randint(0, time_mask_max)
    t0 = np.random.randint(0, n_steps - t)
    mel[:, t0:t0+t] = 0
    return mel

def apply_waveform_aug(y, sr):
    """Waveform Augmentation (강화: Noise 70%, Pitch 50%±3, Stretch 40% 0.85~1.15)"""
    y = y.copy()
    
    # 1. Additive White Noise
    if np.random.rand() < 0.7:
        noise_level = np.random.uniform(0.001, 0.01)
        noise = np.random.randn(len(y)) * noise_level * np.max(np.abs(y))
        y = y + noise
        
    # 2. Random Pitch Shift (±3 semitones)
    if np.random.rand() < 0.5:
        n_steps = np.random.uniform(-3, 3)
        y = librosa.effects.pitch_shift(y, sr=sr, n_steps=n_steps)
        
    # 3. Time Stretch (0.85 ~ 1.15)
    if np.random.rand() < 0.4:
        rate = np.random.uniform(0.85, 1.15)
        y_stretched = librosa.effects.time_stretch(y, rate=rate)
        y = librosa.util.fix_length(y_stretched, size=len(y))
        
    return y

# ──────────── 데이터 목록 로딩 ────────────

def get_data_list(base_dir):
    """base_dir에서 Multi-Task 레이블로 데이터 목록 생성"""
    print(f"📂 Scanning: {base_dir}", flush=True)
    data_list = []

    # Audio extensions to support
    EXTENSIONS = (".wav", ".m4a", ".mp3", ".ogg", ".flac")

    # Normal
    normal_dir = os.path.join(base_dir, "normal")
    if os.path.exists(normal_dir):
        for f in os.listdir(normal_dir):
            if f.lower().endswith(EXTENSIONS):
                data_list.append({
                    "path": os.path.join(normal_dir, f),
                    "type": "normal",    # → type_label = -100
                    "abnormal": 0
                })

    # Abnormal subtypes
    abnormal_dir = os.path.join(base_dir, "abnormal")
    if os.path.exists(abnormal_dir):
        for cls in ["starter", "engine", "brake"]:
            cls_dir = os.path.join(abnormal_dir, cls)
            if os.path.exists(cls_dir):
                for f in os.listdir(cls_dir):
                    if f.lower().endswith(EXTENSIONS):
                        data_list.append({
                            "path": os.path.join(cls_dir, f),
                            "type": cls,     # → type_label = type2id[cls]
                            "abnormal": 1
                        })

    counts = Counter([x['type'] for x in data_list])
    print(f"📊 Data count: {dict(counts)} (total: {len(data_list)})", flush=True)
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
    def __init__(self, data_list, arch, feature_extractor=None, is_training=False, desc="Dataset"):
        print(f"🛠️  [{desc}] Processing {len(data_list)} items...", flush=True)
        self.is_training = is_training

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
        # Leak Test의 경우 '양쪽 모두' 적용을 권장하므로 is_training에 의존
        if self.is_training:
            # 1. Waveform Aug (Noise, Pitch, Stretch)
            y = apply_waveform_aug(y, sr)
            
            # 2. Gain Aug
            gain = np.random.uniform(0.7, 1.3)
            y = y * gain
            
            # 3. Re-calculate Mel from augmented waveform
            mel_raw = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=128, fmax=8000, power=1.0)
            mel_pcen = librosa.pcen(mel_raw, sr=sr)
            mel = (mel_pcen - mel_pcen.mean()) / (mel_pcen.std() + 1e-6)
            
            # 4. SpecAugment
            mel = apply_spec_augment(mel)
        else:
            mel = item["mel"]

        # type_label: abnormal만 분류, normal=-100 (ignore)
        lbl_t = type2id[item["type"]] if item["type"] in type2id else -100

        return {
            "ast_input": item["ast_input"] if item["ast_input"] is not None else torch.zeros(1),
            "mel_input": torch.tensor(mel, dtype=torch.float32),
            "raw_audio": torch.tensor(y, dtype=torch.float32),
            "type_label": torch.tensor(lbl_t, dtype=torch.long),
            "abnormal_label": torch.tensor(item["abnormal"], dtype=torch.float32),
        }


# ──────────── DataLoader 생성 ────────────

def create_dataloaders(arch, feature_extractor=None, batch_size=None, samples_per_class=None):
    """결합 계층화 분할(Class+Source) 및 샘플수 균형 조정(Balancing) 지원"""
    if batch_size is None:
        batch_size = 32 if IS_RUNPOD else COMMON_CONFIG["batch_size"]
    
    if samples_per_class is None:
        samples_per_class = COMMON_CONFIG.get("samples_per_class", 0)

    # 1. 모든 데이터 수집 및 메타 데이터 생성
    all_data = get_data_list(TRAIN_DATA_DIR) + get_data_list(TEST_DATA_DIR)
    
    for item in all_data:
        # 출처 및 그룹 태깅
        fname = os.path.basename(item["path"]).lower()
        item["source"] = "site" if "visc_" in fname else "youtube"
        
        # Group ID 추출: 같은 유튜브 영상에서 나온 조각들은 하나의 그룹으로 묶음
        if item["source"] == "site":
            # 현장 데이터는 각 파일이 개별 기록이므로 파일명을 그룹 아이디로 (또는 필요시 세션별 묶음)
            item["group_id"] = fname
        else:
            # 유튜브: type_ID_seg_clip.wav 또는 normal_idle_X_clip.wav
            parts = fname.split("_")
            if "normal_idle" in fname:
                # [normal, idle, 1, 01.wav] -> normal_idle_1
                item["group_id"] = "_".join(parts[:3]) if len(parts) >= 3 else fname
            else:
                # [brake, id, 01, 001.wav] -> id
                # 유튜브 ID는 보통 2번째 파트 (id)
                item["group_id"] = parts[1] if len(parts) >= 2 else fname

        # 계층화 키 생성: {type}_{source} (정상: normal_site, 결함: engine_youtube 등)
        item["stratify_key"] = f"{item['type']}_{item['source']}"

    # 2. 그룹 계층화 분할 (Group Stratified Split)
    def robust_group_split(data, train_ratio=0.7, val_ratio=0.1):
        """유튜브 원본 그룹(Video ID) 단위로 데이터를 분할하여 Leakage 방지"""
        group_map = {} # gid -> skey
        for x in data:
            gid = x["group_id"]
            if gid not in group_map:
                group_map[gid] = x["stratify_key"]
        
        unique_gids = list(group_map.keys())
        unique_keys = [group_map[gid] for gid in unique_gids]
        
        train_gids, val_gids, test_gids = [], [], []
        
        for key in set(unique_keys):
            g_in_key = [gid for gid in unique_gids if group_map[gid] == key]
            n_g = len(g_in_key)
            np.random.seed(42)
            np.random.shuffle(g_in_key)
            
            if n_g == 1:
                # 1개뿐이면 Train에만 배치
                train_gids.append(g_in_key[0])
                continue
            elif n_g == 2:
                # 2개면 Train + Val (검증 가능하도록)
                train_gids.append(g_in_key[0])
                val_gids.append(g_in_key[1])
                continue
                
            n_tr = max(1, int(n_g * train_ratio))
            n_va = max(1, int(n_g * val_ratio))
            # val에 최소 1개 보장
            if n_va == 0 and n_g - n_tr >= 2:
                n_va = 1
            
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

    # 3. 데이터셋 균형 조정 (Train 세트 전용)
    if samples_per_class > 0:
        balanced_train = []
        train_class_keys = sorted(set([x["type"] for x in train_data]))
        
        print(f"⚖️  Balancing Train set to {samples_per_class} samples per class...", flush=True)
        
        for cls in train_class_keys:
            cls_data = [x for x in train_data if x["type"] == cls]
            if not cls_data:
                continue
            
            if len(cls_data) >= samples_per_class:
                # 1) Undersampling (샘플이 많은 경우 무작위 선택)
                np.random.seed(42)
                indices = np.random.choice(len(cls_data), samples_per_class, replace=False)
                balanced_train.extend([cls_data[i] for i in indices])
            else:
                # 2) Augmentation-based Oversampling (샘플이 적은 경우 복제)
                # (Dataset 클래스 내의 실시간 Augmentation 덕분에 각각의 복제본은 다른 변형으로 학습됨)
                multiplier = samples_per_class // len(cls_data)
                remainder = samples_per_class % len(cls_data)
                balanced_train.extend(cls_data * multiplier)
                balanced_train.extend(cls_data[:remainder])
        
        train_final = balanced_train
        print(f"✅ Training set balanced: {len(train_data)} -> {len(train_final)} clips")
    else:
        # 기존 오버샘플링 (단순 {type}_{source} 비율 맞추기)
        train_keys = [x["stratify_key"] for x in train_data]
        counts_train = Counter(train_keys)
        max_count = max(counts_train.values())
        
        balanced_train = []
        for key in sorted(set(train_keys)):
            group = [x for x in train_data if x["stratify_key"] == key]
            resampled_group = group * (max_count // len(group))
            resampled_group += group[:(max_count % len(group))]
            balanced_train.extend(resampled_group)
        
        train_final = balanced_train
        print(f"⚖️  Training set oversampled: {len(train_data)} -> {len(train_final)}")

    # Dataset 생성
    train_ds = AudioDataset(train_final, arch, feature_extractor, is_training=True, desc="Train")
    val_ds = AudioDataset(val_data, arch, feature_extractor, is_training=False, desc="Valid")
    test_ds = AudioDataset(test_data, arch, feature_extractor, is_training=False, desc="Test")

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

    # Class Weights (Type Head) - Original Train 분포 기준
    type_counts = Counter([x['type'] for x in train_data if x['type'] in TYPE_LABELS])
    if any(type_counts[l] == 0 for l in TYPE_LABELS):
        weights = torch.ones(len(TYPE_LABELS), device=DEVICE)
    else:
        min_count = min(type_counts.values())
        weights = torch.tensor([min_count / (type_counts[l] + 1e-6) for l in TYPE_LABELS], device=DEVICE).float()

    return train_loader, val_loader, test_loader, weights