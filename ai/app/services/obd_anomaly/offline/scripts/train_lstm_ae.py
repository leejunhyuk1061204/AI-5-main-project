import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset


class LSTMAutoencoder(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int = 64, latent_dim: int = 16, num_layers: int = 1):
        super().__init__()
        self.encoder = nn.LSTM(input_dim, hidden_dim, num_layers, batch_first=True)
        self.to_latent = nn.Linear(hidden_dim, latent_dim)
        self.from_latent = nn.Linear(latent_dim, hidden_dim)
        self.decoder = nn.LSTM(hidden_dim, hidden_dim, num_layers, batch_first=True)
        self.out = nn.Linear(hidden_dim, input_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        enc_out, _ = self.encoder(x)
        h_last = enc_out[:, -1, :]
        z = self.to_latent(h_last)
        h = self.from_latent(z).unsqueeze(1).repeat(1, x.size(1), 1)
        dec_out, _ = self.decoder(h)
        return self.out(dec_out)


class WindowDataset(Dataset):
    def __init__(self, windows: np.ndarray):
        self.X = windows.astype(np.float32)

    def __len__(self) -> int:
        return int(self.X.shape[0])

    def __getitem__(self, idx: int) -> torch.Tensor:
        return torch.from_numpy(self.X[idx])


def load_samples(path: Path) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def build_windows(sample: Dict[str, Any], schema_features: List[str], window_sec: int, stride_sec: int) -> np.ndarray:
    hz = int(sample.get("sampling_hz", 1))
    data = sample["data"]
    n = min(len(data.get(feat, [])) for feat in schema_features)
    if n <= 0:
        return np.empty((0, 0, 0), dtype=np.float32)

    series = np.stack(
        [np.array(data.get(feat, [float("nan")] * n)[:n], dtype=np.float32) for feat in schema_features],
        axis=1,
    )

    wsize = window_sec * hz
    step = stride_sec * hz
    if n < wsize:
        return np.empty((0, wsize, len(schema_features)), dtype=np.float32)

    windows: List[np.ndarray] = []
    for start in range(0, n - wsize + 1, step):
        windows.append(series[start : start + wsize])
    return np.stack(windows) if windows else np.empty((0, wsize, len(schema_features)), dtype=np.float32)


def impute_nan(windows: np.ndarray) -> np.ndarray:
    out = windows.copy()
    if out.size == 0:
        return out
    for wi in range(out.shape[0]):
        for fi in range(out.shape[2]):
            col = out[wi, :, fi]
            finite = np.isfinite(col)
            fill = float(np.nanmean(col[finite])) if np.any(finite) else 0.0
            col[~finite] = fill
            out[wi, :, fi] = col
    return out


def fit_scaler(windows: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    mean = windows.mean(axis=(0, 1))
    std = windows.std(axis=(0, 1))
    std = np.where(std == 0, 1.0, std)
    return mean.astype(np.float32), std.astype(np.float32)


def apply_scaler(windows: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    return ((windows - mean.reshape(1, 1, -1)) / std.reshape(1, 1, -1)).astype(np.float32)


def main() -> None:
    start_dt = datetime.now()
    start_ts = start_dt.timestamp()
    print(f"[START] train_lstm_ae at {start_dt.strftime('%Y-%m-%d %H:%M:%S')}")

    ap = argparse.ArgumentParser()
    ap.add_argument("--train-jsonl", required=True)
    ap.add_argument("--schema", default="app/services/obd_anomaly/models/schemas/v1/schema_core.json")
    ap.add_argument("--window-sec", type=int, default=60)
    ap.add_argument("--stride-sec", type=int, default=30)
    ap.add_argument("--epochs", type=int, default=10)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--out-model", required=True)
    ap.add_argument("--out-scaler", required=True)
    ap.add_argument("--out-report", required=True)
    args = ap.parse_args()

    schema_payload = json.loads(Path(args.schema).read_text(encoding="utf-8-sig"))
    schema_features = [f for f in schema_payload.get("features", []) if isinstance(f, str)]
    if not schema_features:
        raise ValueError("schema features empty")

    samples = load_samples(Path(args.train_jsonl))
    samples = [s for s in samples if bool(s.get("is_normal", True))]
    if not samples:
        raise ValueError("No normal samples in train split")

    all_windows: List[np.ndarray] = []
    for s in samples:
        ws = build_windows(s, schema_features, args.window_sec, args.stride_sec)
        if ws.size > 0:
            all_windows.append(ws)
    if not all_windows:
        raise ValueError("No windows generated for AE training")

    windows = np.concatenate(all_windows, axis=0)
    windows = impute_nan(windows)

    mean, std = fit_scaler(windows)
    x_train = apply_scaler(windows, mean, std)

    ds = WindowDataset(x_train)
    dl = DataLoader(ds, batch_size=args.batch_size, shuffle=True, drop_last=False)

    model = LSTMAutoencoder(input_dim=x_train.shape[-1])
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)

    opt = torch.optim.Adam(model.parameters(), lr=args.lr)
    loss_fn = nn.MSELoss()

    losses: List[float] = []
    for ep in range(1, args.epochs + 1):
        model.train()
        total = 0.0
        for batch in dl:
            batch = batch.to(device)
            recon = model(batch)
            loss = loss_fn(recon, batch)
            opt.zero_grad()
            loss.backward()
            opt.step()
            total += float(loss.item())
        ep_loss = total / max(1, len(dl))
        losses.append(ep_loss)
        print(f"[epoch {ep:02d}] loss={ep_loss:.6f}")

    Path(args.out_model).parent.mkdir(parents=True, exist_ok=True)
    # Engine loader expects callable model object (not state_dict only).
    torch.save(model.cpu(), args.out_model)

    Path(args.out_scaler).parent.mkdir(parents=True, exist_ok=True)
    scaler = {"type": "zscore", "mean": mean.tolist(), "std": std.tolist()}
    Path(args.out_scaler).write_text(json.dumps(scaler, ensure_ascii=False, indent=2), encoding="utf-8")

    report = {
        "windows": int(x_train.shape[0]),
        "features": int(x_train.shape[2]),
        "epochs": int(args.epochs),
        "final_loss": float(losses[-1] if losses else 0.0),
        "loss_curve": losses,
        "model": args.out_model,
        "scaler": args.out_scaler,
    }
    Path(args.out_report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    end_dt = datetime.now()
    elapsed_sec = end_dt.timestamp() - start_ts
    print(f"[END] train_lstm_ae at {end_dt.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"[ELAPSED] {elapsed_sec:.2f}s")
    print("[OK] lstm-ae trained")
    print(f"model={args.out_model}")
    print(f"scaler={args.out_scaler}")


if __name__ == "__main__":
    main()
