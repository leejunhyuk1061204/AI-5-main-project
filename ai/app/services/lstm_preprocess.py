# ai/app/services/lstm_preprocess.py
from __future__ import annotations

import os, glob, json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


@dataclass
class PreprocessConfig:
    sampling_hz: float = 10.0
    window_sec: int = 60
    stride_sec: int = 5  # 윈도우 이동 간격(초)
    timestamp_col: Optional[str] = "timestamp"  # 없으면 None
    fill_method: str = "ffill_then_bfill"
    normalize: str = "zscore"  # zscore만 지원(필요 시 확장)

    # raw CSV 컬럼명을 표준 컬럼명으로 바꾸기 위한 매핑
    rename_map: Dict[str, str] = field(default_factory=dict)

    # timestamp 포맷(알면 지정해서 파싱 경고/속도 개선)
    # OBD CSV가 보통 "HH:MM:SS.mmm"이면 "%H:%M:%S.%f"
    timestamp_format: Optional[str] = None


def _ensure_dir(p: str) -> None:
    os.makedirs(p, exist_ok=True)


def _list_csv_files(root_dir: str) -> List[str]:
    return sorted(glob.glob(os.path.join(root_dir, "**", "*.csv"), recursive=True))


def _clean_and_select(df: pd.DataFrame, signals: List[str], ts_col: Optional[str], ts_format: Optional[str]) -> pd.DataFrame:
    cols = ([ts_col] if ts_col and ts_col in df.columns else []) + [c for c in signals if c in df.columns]
    missing = [c for c in signals if c not in df.columns]
    if missing:
        raise ValueError(f"CSV에 signals 컬럼이 없습니다: {missing}\n현재 컬럼={list(df.columns)}")

    df = df[cols].copy()

    # timestamp가 있으면 정렬
    if ts_col and ts_col in df.columns:
        if ts_format:
            df[ts_col] = pd.to_datetime(df[ts_col], format=ts_format, errors="coerce")
        else:
            df[ts_col] = pd.to_datetime(df[ts_col], errors="coerce")
        df = df.dropna(subset=[ts_col]).sort_values(ts_col).reset_index(drop=True)

    # numeric 변환
    for c in signals:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    return df


def _fillna(df: pd.DataFrame, signals: List[str], method: str) -> pd.DataFrame:
    if method == "ffill_then_bfill":
        df[signals] = df[signals].ffill().bfill()
    elif method == "zero":
        df[signals] = df[signals].fillna(0.0)
    elif method == "drop":
        df = df.dropna(subset=signals)
    else:
        raise ValueError(f"Unknown fill method: {method}")
    return df


def _make_windows(arr: np.ndarray, T: int, stride: int) -> np.ndarray:
    """
    arr: (L, F)
    return: (N, T, F)
    """
    L, F = arr.shape
    if L < T:
        return np.empty((0, T, F), dtype=np.float32)

    windows = []
    for start in range(0, L - T + 1, stride):
        windows.append(arr[start:start + T])

    if not windows:
        return np.empty((0, T, F), dtype=np.float32)

    return np.stack(windows).astype(np.float32)


def build_lstm_ae_dataset(
    raw_dir: str,
    out_dir: str,
    signals: List[str],
    cfg: PreprocessConfig = PreprocessConfig(),
    max_files: Optional[int] = None,
) -> Tuple[str, str, str]:
    """
    raw_dir: 예) ai/data/obd/raw/normal
    out_dir: 예) ai/data/processed/lstm_ae
    returns: (train_npz_path, scaler_json_path, meta_json_path)
    """
    _ensure_dir(out_dir)

    files = _list_csv_files(raw_dir)
    if max_files:
        files = files[:max_files]
    if not files:
        raise FileNotFoundError(f"CSV 파일을 찾지 못했습니다: {raw_dir}")

    T = int(cfg.sampling_hz * cfg.window_sec)
    stride = int(cfg.sampling_hz * cfg.stride_sec)

    all_windows = []
    lengths = []

    for fp in files:
        df = pd.read_csv(fp)

        # 0) 컬럼명 인코딩 깨짐 정규화: "Â" 제거 (중요!)
        df.columns = [c.replace("Â", "") if isinstance(c, str) else c for c in df.columns]

        # 1) 컬럼명 표준화(매핑이 있으면 적용)
        if cfg.rename_map:
            df = df.rename(columns=cfg.rename_map)

        # 2) 필요한 컬럼만 선택 + timestamp 정렬/파싱
        df = _clean_and_select(df, signals=signals, ts_col=cfg.timestamp_col, ts_format=cfg.timestamp_format)
        df = _fillna(df, signals=signals, method=cfg.fill_method)

        arr = df[signals].to_numpy(dtype=np.float32)
        lengths.append(arr.shape[0])

        w = _make_windows(arr, T=T, stride=stride)
        if w.shape[0] > 0:
            all_windows.append(w)

    if not all_windows:
        raise ValueError("윈도우가 하나도 생성되지 않았습니다. (데이터 길이/샘플링/윈도우 설정 확인)")

    X = np.concatenate(all_windows, axis=0)  # (N, T, F)

    scaler = {}
    if cfg.normalize == "zscore":
        flat = X.reshape(-1, X.shape[-1])
        mean = flat.mean(axis=0)
        std = flat.std(axis=0)
        std = np.where(std < 1e-8, 1.0, std)

        X = (X - mean) / std

        scaler = {
            "type": "zscore",
            "mean": mean.tolist(),
            "std": std.tolist(),
            "signals": signals,
        }
    else:
        raise ValueError(f"Unknown normalize: {cfg.normalize}")

    train_npz = os.path.join(out_dir, "train.npz")
    np.savez_compressed(train_npz, X=X)

    scaler_path = os.path.join(out_dir, "scaler.json")
    with open(scaler_path, "w", encoding="utf-8") as f:
        json.dump(scaler, f, ensure_ascii=False, indent=2)

    meta = {
        "raw_dir": raw_dir,
        "num_files": len(files),
        "avg_length_rows": float(np.mean(lengths)) if lengths else 0.0,
        "sampling_hz": cfg.sampling_hz,
        "window_sec": cfg.window_sec,
        "stride_sec": cfg.stride_sec,
        "T": T,
        "F": len(signals),
        "signals": signals,
        "timestamp_col": cfg.timestamp_col,
        "timestamp_format": cfg.timestamp_format,
        "rename_map": cfg.rename_map,
    }
    meta_path = os.path.join(out_dir, "meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    return train_npz, scaler_path, meta_path
