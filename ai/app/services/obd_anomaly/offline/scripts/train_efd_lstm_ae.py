import argparse
import json
import os
import time
from typing import List

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset


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


class WindowDataset(Dataset):
    def __init__(self, windows: np.ndarray):
        self.X = windows

    def __len__(self):
        return int(self.X.shape[0])

    def __getitem__(self, idx):
        return torch.from_numpy(self.X[idx])


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


def zscore_normalize(windows: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mean = windows.mean(axis=(0, 1), keepdims=True)
    std = windows.std(axis=(0, 1), keepdims=True)
    std = np.where(std == 0, 1.0, std)
    return (windows - mean) / std, mean.squeeze(0).squeeze(0), std.squeeze(0).squeeze(0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--normal_jsonl", required=True)
    parser.add_argument("--out_dir", required=True)
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch_size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-3)
    args = parser.parse_args()

    start_ts = time.time()
    item = load_jsonl(args.normal_jsonl)
    windows = build_windows(item)
    windows, mean, std = zscore_normalize(windows)

    ds = WindowDataset(windows)
    dl = DataLoader(ds, batch_size=args.batch_size, shuffle=True, drop_last=True)

    input_dim = windows.shape[-1]
    model = LSTMAutoencoder(input_dim)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)

    opt = torch.optim.Adam(model.parameters(), lr=args.lr)
    loss_fn = nn.MSELoss()

    for ep in range(1, args.epochs + 1):
        total = 0.0
        print(f"[epoch {ep:02d}] start")
        for x in dl:
            x = x.to(device)
            loss = loss_fn(model(x), x)
            opt.zero_grad()
            loss.backward()
            opt.step()
            total += loss.item()
        print(f"[epoch {ep:02d}] loss={total/len(dl):.6f}")

    os.makedirs(args.out_dir, exist_ok=True)
    run_id = time.strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(args.out_dir, "runs", run_id)
    os.makedirs(run_dir, exist_ok=True)
    run_path = os.path.join(run_dir, "lstm_ae_efd.pt")
    latest_path = os.path.join(args.out_dir, "lstm_ae_efd_latest.pt")
    scaler_path = os.path.join(args.out_dir, "scaler_efd.json")
    torch.save(model.state_dict(), run_path)
    torch.save(model.state_dict(), latest_path)
    with open(scaler_path, "w", encoding="utf-8") as f:
        json.dump({"type": "zscore", "mean": mean.tolist(), "std": std.tolist()}, f, ensure_ascii=False, indent=2)

    elapsed = time.time() - start_ts
    print("[OK] model saved")
    print("run:", run_path)
    print("latest:", latest_path)
    print("scaler:", scaler_path)
    print(f"[time] {elapsed:.1f}s")


if __name__ == "__main__":
    main()
