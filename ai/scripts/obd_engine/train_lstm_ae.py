# ai/scripts/train_lstm_ae.py
import os
import json
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from datetime import datetime
import time


class NpzSequenceDataset(Dataset):
    def __init__(self, npz_path: str):
        data = np.load(npz_path)
        self.X = data["X"]

    def __len__(self):
        return int(self.X.shape[0])

    def __getitem__(self, idx):
        return torch.from_numpy(self.X[idx])


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


def main():
    start_ts = time.time()
    npz_path = "ai/data/processed/lstm_ae/train.npz"
    out_dir = "ai/weights"
    os.makedirs(out_dir, exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(out_dir, "runs", run_id)
    os.makedirs(run_dir, exist_ok=True)

    batch_size = 16
    epochs = 10
    lr = 1e-3

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print("[device]", device)

    ds = NpzSequenceDataset(npz_path)
    dl = DataLoader(ds, batch_size=batch_size, shuffle=True, drop_last=True)

    input_dim = ds[0].shape[-1]
    model = LSTMAutoencoder(input_dim).to(device)

    opt = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.MSELoss()

    for ep in range(1, epochs + 1):
        print(f"[epoch {ep:02d}] start")
        total = 0.0
        for x in dl:
            x = x.to(device)
            loss = loss_fn(model(x), x)
            opt.zero_grad()
            loss.backward()
            opt.step()
            total += loss.item()
        print(f"[epoch {ep:02d}] loss={total/len(dl):.6f}")

    run_path = os.path.join(run_dir, "lstm_ae.pt")
    latest_path = os.path.join(out_dir, "lstm_ae_latest.pt")
    torch.save(model.state_dict(), run_path)
    torch.save(model.state_dict(), latest_path)
    elapsed = time.time() - start_ts
    print("[OK] model saved")
    print("run:", run_path)
    print("latest:", latest_path)
    print(f"[time] {elapsed:.1f}s")


if __name__ == "__main__":
    main()
