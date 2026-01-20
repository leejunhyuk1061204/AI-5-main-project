# ai/scripts/train_lstm_ae.py
import os
import json
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader


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
    npz_path = "data/processed/lstm_ae/train.npz"
    out_dir = "ai/weights"
    os.makedirs(out_dir, exist_ok=True)

    batch_size = 64
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
        total = 0.0
        for x in dl:
            x = x.to(device)
            loss = loss_fn(model(x), x)
            opt.zero_grad()
            loss.backward()
            opt.step()
            total += loss.item()
        print(f"[epoch {ep:02d}] loss={total/len(dl):.6f}")

    torch.save(model.state_dict(), f"{out_dir}/lstm_ae_v0.pt")
    print("[OK] model saved")


if __name__ == "__main__":
    main()
