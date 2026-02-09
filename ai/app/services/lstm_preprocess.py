from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import json
import numpy as np
import pandas as pd
import re


@dataclass
class PreprocessConfig:
    sampling_hz: float
    window_sec: int
    stride_sec: int
    timestamp_col: str
    timestamp_format: Optional[str] = None
    fill_method: str = "ffill"
    normalize: str = "zscore"  # zscore | minmax | none
    rename_map: Optional[Dict[str, str]] = None
    min_coverage: Optional[float] = None  # 0.0~1.0, None means no filter
    resample: str = "nearest_grid"  # nearest_grid | none


def build_lstm_ae_dataset(
    raw_dir: str,
    out_dir: str,
    signals: List[str],
    cfg: PreprocessConfig,
) -> Tuple[str, str, str]:
    raw_path = Path(raw_dir)
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    csv_files = sorted(raw_path.rglob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No csv files found under: {raw_path}")

    series_list: List[np.ndarray] = []
    lengths: List[int] = []

    for fp in csv_files:
        df = _load_csv(fp, cfg, signals)
        X = _resample_and_extract(df, cfg, signals)
        if X.size == 0:
            continue
        series_list.append(X)
        lengths.append(int(X.shape[0]))

    if not series_list:
        raise ValueError("No usable series after preprocessing.")

    # Windowing
    wsize = int(cfg.window_sec * cfg.sampling_hz)
    step = int(cfg.stride_sec * cfg.sampling_hz)
    windows = _make_windows(series_list, wsize, step, cfg.min_coverage)

    if not windows:
        raise ValueError("No windows created. Check window/stride or data length.")

    X = np.stack(windows).astype(np.float32)  # (N, T, F)

    # Normalize
    scaler, X = _normalize(X, cfg.normalize)

    # Save outputs
    train_npz = str(out_path / "train.npz")
    np.savez_compressed(train_npz, X=X)

    scaler_path = str(out_path / "scaler.json")
    with open(scaler_path, "w", encoding="utf-8") as f:
        json.dump({**scaler, "signals": signals}, f, ensure_ascii=False, indent=2)

    meta_path = str(out_path / "meta.json")
    meta = {
        "raw_dir": str(raw_path),
        "num_files": len(csv_files),
        "avg_length_rows": float(sum(lengths) / max(len(lengths), 1)),
        "sampling_hz": cfg.sampling_hz,
        "window_sec": cfg.window_sec,
        "stride_sec": cfg.stride_sec,
        "T": int(X.shape[1]),
        "F": int(X.shape[2]),
        "signals": signals,
        "timestamp_col": cfg.timestamp_col,
        "timestamp_format": cfg.timestamp_format,
        "rename_map": cfg.rename_map or {},
        "fill_method": cfg.fill_method,
        "normalize": cfg.normalize,
        "min_coverage": cfg.min_coverage,
        "resample": cfg.resample,
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    return train_npz, scaler_path, meta_path


def _normalize_colname(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def _build_normcol_index(columns: Iterable[str]) -> Dict[str, str]:
    idx: Dict[str, str] = {}
    for c in columns:
        k = _normalize_colname(c)
        if k and k not in idx:
            idx[k] = c
    return idx


def _load_csv(path: Path, cfg: PreprocessConfig, signals: List[str]) -> pd.DataFrame:
    df = pd.read_csv(path)

    if cfg.rename_map:
        norm_index = _build_normcol_index(df.columns)
        norm_map = {_normalize_colname(k): v for k, v in cfg.rename_map.items()}
        new_cols = {}
        for norm_key, target in norm_map.items():
            if norm_key in norm_index:
                new_cols[norm_index[norm_key]] = target
        if new_cols:
            df = df.rename(columns=new_cols)

    required = [cfg.timestamp_col] + signals
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in {path.name}: {missing}")

    # Ensure numeric for signal columns
    for s in signals:
        df[s] = pd.to_numeric(df[s], errors="coerce")

    # Parse timestamp
    ts = df[cfg.timestamp_col]
    if np.issubdtype(ts.dtype, np.number):
        df[cfg.timestamp_col] = pd.to_datetime(ts, unit="s", errors="coerce")
    else:
        df[cfg.timestamp_col] = pd.to_datetime(ts, format=cfg.timestamp_format, errors="coerce")

    df = df.dropna(subset=[cfg.timestamp_col])
    df = df.sort_values(cfg.timestamp_col)
    return df


def _resample_and_extract(df: pd.DataFrame, cfg: PreprocessConfig, signals: List[str]) -> np.ndarray:
    if cfg.resample == "none":
        data = df[signals].to_numpy()
        return _fill_missing(data, cfg.fill_method)

    # nearest_grid resample
    start = df[cfg.timestamp_col].iloc[0]
    end = df[cfg.timestamp_col].iloc[-1]
    if start >= end:
        return np.empty((0, len(signals)), dtype=float)

    freq = pd.to_timedelta(1 / cfg.sampling_hz, unit="s")
    grid = pd.date_range(start=start, end=end, freq=freq)
    resampled = (
        df.set_index(cfg.timestamp_col)[signals]
        .reindex(grid, method="nearest")
        .reset_index(drop=True)
    )

    data = resampled.to_numpy()
    return _fill_missing(data, cfg.fill_method)


def _fill_missing(data: np.ndarray, method: str) -> np.ndarray:
    if data.size == 0:
        return data

    df = pd.DataFrame(data)
    if method == "ffill":
        df = df.ffill()
    elif method == "bfill":
        df = df.bfill()
    elif method == "ffill_then_bfill":
        df = df.ffill().bfill()
    elif method == "zero":
        df = df.fillna(0)
    else:
        raise ValueError(f"Unknown fill_method: {method}")

    return df.to_numpy()


def _make_windows(
    series_list: Iterable[np.ndarray],
    wsize: int,
    step: int,
    min_coverage: Optional[float],
) -> List[np.ndarray]:
    windows: List[np.ndarray] = []

    for X in series_list:
        if X.shape[0] < wsize:
            continue
        for start in range(0, X.shape[0] - wsize + 1, step):
            w = X[start : start + wsize]
            if np.isnan(w).any():
                w = np.nan_to_num(w)
            if min_coverage is not None:
                valid = np.isfinite(w).sum()
                coverage = valid / float(w.size)
                if coverage < min_coverage:
                    continue
            windows.append(w)

    return windows


def _normalize(X: np.ndarray, mode: str) -> Tuple[Dict[str, List[float]], np.ndarray]:
    if mode == "none":
        return {"type": "none"}, X

    if mode == "zscore":
        mean = X.mean(axis=(0, 1))
        std = X.std(axis=(0, 1))
        std = np.where(std == 0, 1.0, std)
        Xn = (X - mean) / std
        return {"type": "zscore", "mean": mean.tolist(), "std": std.tolist()}, Xn

    if mode == "minmax":
        vmin = X.min(axis=(0, 1))
        vmax = X.max(axis=(0, 1))
        denom = np.where((vmax - vmin) == 0, 1.0, (vmax - vmin))
        Xn = (X - vmin) / denom
        return {
            "type": "minmax",
            "min": vmin.tolist(),
            "max": vmax.tolist(),
        }, Xn

    raise ValueError(f"Unknown normalize mode: {mode}")
