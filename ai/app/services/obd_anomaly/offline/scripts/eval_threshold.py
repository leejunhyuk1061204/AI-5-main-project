import argparse
import json
import os
from typing import List

import numpy as np
import torch
import torch.nn as nn


class LSTMAutoencoder(nn.Module):
    def __init__(self, input_dim, hidden_dim=64, latent_dim=16, num_layers=1):
        super().__init__()
        self.encoder = nn.LSTM(input_dim, hidden_dim, num_layers, batch_first=True)
        self.to_latent = nn.Linear(hidden_dim, latent_dim)

        self.from_latent = nn.Linear(latent_dim, hidden_dim)
        self.decoder = nn.LSTM(hidden_dim, hidden_dim, num_layers, batch_first=True)
        self.out = nn.Linear(hidden_dim, input_dim)

    def forward(self, x):
        enc_out, _ = self.encoder(x)
        h_last = enc_out[:, -1, :]
        z = self.to_latent(h_last)

        h = self.from_latent(z).unsqueeze(1).repeat(1, x.size(1), 1)
        dec_out, _ = self.decoder(h)
        return self.out(dec_out)


def load_jsonl(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        line = f.readline().strip()
        if not line:
            raise ValueError(f"Empty jsonl: {path}")
        return json.loads(line)


def build_windows(item: dict) -> np.ndarray:
    channels = item["channels"]
    data = item["data"]
    sampling_hz = int(item["sampling_hz"])
    window_sec = int(item["window_sec"])
    stride_sec = int(item["stride_sec"])

    series = np.stack([data[ch] for ch in channels], axis=1).astype(np.float32)
    wsize = window_sec * sampling_hz
    step = stride_sec * sampling_hz
    if wsize <= 0 or step <= 0:
        raise ValueError("window_sec/stride_sec must be >= 1")

    windows: List[np.ndarray] = []
    for start in range(0, series.shape[0] - wsize + 1, step):
        w = series[start : start + wsize]
        windows.append(w)
    if not windows:
        raise ValueError("No windows created from item.")
    return np.stack(windows)


def zscore_with_ref(windows: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    std = np.where(std == 0, 1.0, std)
    return (windows - mean) / std


def recon_errors(model: nn.Module, windows: np.ndarray, device: str) -> np.ndarray:
    model.eval()
    x = torch.from_numpy(windows).to(device)
    with torch.no_grad():
        y = model(x)
        err = ((y - x) ** 2).mean(dim=(1, 2)).detach().cpu().numpy()
    return err


def auc_score(labels: np.ndarray, scores: np.ndarray) -> float:
    # Rank-based AUC (Mann-Whitney U)
    order = np.argsort(scores)
    ranks = np.empty_like(order)
    ranks[order] = np.arange(len(scores)) + 1
    pos = labels == 1
    n_pos = pos.sum()
    n_neg = len(labels) - n_pos
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    sum_ranks_pos = ranks[pos].sum()
    auc = (sum_ranks_pos - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)
    return float(auc)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--normal_jsonl", required=True)
    parser.add_argument("--fault_jsonl", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--quantile", type=float, default=0.99)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    normal_item = load_jsonl(args.normal_jsonl)
    fault_item = load_jsonl(args.fault_jsonl)

    normal_windows = build_windows(normal_item)
    fault_windows = build_windows(fault_item)

    # normalize using normal statistics
    mean = normal_windows.mean(axis=(0, 1), keepdims=True)
    std = normal_windows.std(axis=(0, 1), keepdims=True)
    normal_windows = zscore_with_ref(normal_windows, mean, std)
    fault_windows = zscore_with_ref(fault_windows, mean, std)

    input_dim = normal_windows.shape[-1]
    model = LSTMAutoencoder(input_dim)
    state = torch.load(args.model, map_location="cpu")
    model.load_state_dict(state)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)

    normal_scores = recon_errors(model, normal_windows, device)
    fault_scores = recon_errors(model, fault_windows, device)

    labels = np.concatenate([np.zeros_like(normal_scores), np.ones_like(fault_scores)])
    scores = np.concatenate([normal_scores, fault_scores])
    auc = auc_score(labels, scores)
    threshold = float(np.quantile(normal_scores, args.quantile))

    summary = {
        "auc": auc,
        "threshold": threshold,
        "quantile": args.quantile,
        "normal_windows": int(normal_scores.shape[0]),
        "fault_windows": int(fault_scores.shape[0]),
        "normal_score_mean": float(normal_scores.mean()),
        "fault_score_mean": float(fault_scores.mean()),
        "model": args.model,
        "normal_jsonl": args.normal_jsonl,
        "fault_jsonl": args.fault_jsonl,
    }

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("[OK] eval done")
    print(f"AUC: {auc:.4f}")
    print(f"threshold(q={args.quantile}): {threshold:.6f}")
    print(f"out: {args.out}")


if __name__ == "__main__":
    main()
