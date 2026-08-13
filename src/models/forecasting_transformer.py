"""Temporal-attention Transformer for CPR/CDR (prepayment/default speed)
forecasting, conditioned on a macro path (rate incentive, HPI growth,
unemployment) plus pool seasoning/credit state.

This is the core "AI on the desk's actual forecasting problem" piece:
given a window of macro history, predict next-month prepay & default
hazard for the pool.
"""
from __future__ import annotations

import math

import numpy as np
import torch
import torch.nn as nn

FEATURES = ["rate_incentive", "hpi_growth", "unemployment", "season_ramp", "credit_score_z"]
N_FEATURES = len(FEATURES)
WINDOW = 12


class PositionalEncoding(nn.Module):
    def __init__(self, d_model: int, max_len: int = 128):
        super().__init__()
        pe = torch.zeros(max_len, d_model)
        pos = torch.arange(0, max_len).unsqueeze(1).float()
        div = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(pos * div)
        pe[:, 1::2] = torch.cos(pos * div)
        self.register_buffer("pe", pe.unsqueeze(0))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + self.pe[:, : x.size(1)]


class CPRCDRTransformer(nn.Module):
    def __init__(self, d_model: int = 32, n_heads: int = 4, n_layers: int = 2, window: int = 12):
        super().__init__()
        self.window = window
        # input features span 3 orders of magnitude (hpi_growth ~1e-3 vs
        # unemployment ~5); without standardisation the projection cannot
        # recover the small-magnitude credit drivers.
        self.register_buffer("feat_mean", torch.zeros(N_FEATURES))
        self.register_buffer("feat_std", torch.ones(N_FEATURES))
        self.input_proj = nn.Linear(N_FEATURES, d_model)
        self.pos_enc = PositionalEncoding(d_model, max_len=window + 1)
        layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=n_heads, dim_feedforward=64,
            dropout=0.1, batch_first=True,
        )
        self.encoder = nn.TransformerEncoder(layer, num_layers=n_layers)
        self.head = nn.Sequential(
            nn.Linear(d_model, 16), nn.ReLU(), nn.Linear(16, 2),  # -> (cpr, cdr)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = (x - self.feat_mean) / self.feat_std
        h = self.input_proj(x)
        h = self.pos_enc(h)
        h = self.encoder(h)
        last = h[:, -1, :]
        out = self.head(last)
        return torch.sigmoid(out) * torch.tensor([0.5, 0.15])  # cap cpr<=0.5, cdr<=0.15


def _synthetic_macro_path(rng: np.random.Generator, months: int) -> np.ndarray:
    rate_incentive = np.cumsum(rng.normal(0, 0.15, months)).clip(-2, 3)
    hpi_growth = np.cumsum(rng.normal(0.002, 0.01, months)).clip(-0.3, 0.3)
    unemployment = 4.0 + np.cumsum(rng.normal(0, 0.1, months)).clip(-2, 6)
    return np.stack([rate_incentive, hpi_growth, unemployment], axis=1)


def true_hazards(macro: np.ndarray, season_ramp: np.ndarray, credit_z: np.ndarray):
    """Ground-truth data-generating process for CPR/CDR."""
    rate_inc, hpi, unemp = macro[:, 0], macro[:, 1], macro[:, 2]
    cpr = np.clip(0.08 + 0.06 * np.clip(rate_inc, 0, None) * season_ramp
                  - 0.02 * (unemp > 6), 0.01, 0.45)
    cdr = np.clip(0.010 + 0.10 * np.clip(-hpi, 0, None)
                  + 0.008 * np.clip(unemp - 5, 0, None)
                  - 0.004 * credit_z, 0.001, 0.12)
    return cpr, cdr


def make_training_set(n_seq: int = 800, window: int = WINDOW, seed: int = 7):
    rng = np.random.default_rng(seed)
    X, Y = [], []
    for _ in range(n_seq):
        macro = _synthetic_macro_path(rng, window + 1)
        season_ramp = np.linspace(rng.uniform(0.1, 0.6), 1.0, window + 1)
        credit_z = np.full(window + 1, rng.normal(0, 1))
        feats = np.concatenate([macro, season_ramp[:, None], credit_z[:, None]], axis=1)
        cpr, cdr = true_hazards(macro, season_ramp, credit_z)
        X.append(feats[:-1])
        Y.append([cpr[-1], cdr[-1]])
    return (torch.tensor(np.array(X), dtype=torch.float32),
            torch.tensor(np.array(Y), dtype=torch.float32))


def _r2(pred: np.ndarray, target: np.ndarray) -> float:
    ss_res = ((pred - target) ** 2).sum()
    ss_tot = ((target - target.mean()) ** 2).sum()
    return float(1 - ss_res / ss_tot) if ss_tot > 0 else float("nan")


def train_forecaster(epochs: int = 400, window: int = WINDOW, verbose: bool = True) -> CPRCDRTransformer:
    """CPR and CDR live on very different scales (CPR sd ~10x CDR sd). A plain
    MSE is dominated by CPR, so the model minimises loss by emitting a constant
    CDR and ignoring the credit features. Targets are therefore standardised
    per-head so both tasks contribute comparable gradient signal."""
    model = CPRCDRTransformer(window=window)
    X, Y = make_training_set(n_seq=2000, window=window)
    Xv, Yv = make_training_set(n_seq=400, window=window, seed=1234)

    flat = X.reshape(-1, N_FEATURES)
    model.feat_mean.copy_(flat.mean(dim=0))
    model.feat_std.copy_(flat.std(dim=0).clamp(min=1e-6))

    target_sd = Y.std(dim=0)
    opt = torch.optim.Adam(model.parameters(), lr=3e-3)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs)
    batch_size = 256

    model.train()
    for ep in range(epochs):
        perm = torch.randperm(len(X))
        epoch_loss = 0.0
        for i in range(0, len(X), batch_size):
            idx = perm[i: i + batch_size]
            opt.zero_grad()
            pred = model(X[idx])
            loss = (((pred - Y[idx]) / target_sd) ** 2).mean()
            loss.backward()
            opt.step()
            epoch_loss += loss.item()
        sched.step()
        if verbose and (ep % 100 == 0 or ep == epochs - 1):
            n_batches = max(1, (len(X) + batch_size - 1) // batch_size)
            print(f"  [forecaster] epoch {ep:3d}  scaled_mse={epoch_loss/n_batches:.5f}")

    model.eval()
    with torch.no_grad():
        pv = model(Xv).numpy()
    yv = Yv.numpy()
    model.validation = {
        "cpr_r2": round(_r2(pv[:, 0], yv[:, 0]), 4),
        "cdr_r2": round(_r2(pv[:, 1], yv[:, 1]), 4),
        "cpr_mae": round(float(np.abs(pv[:, 0] - yv[:, 0]).mean()), 5),
        "cdr_mae": round(float(np.abs(pv[:, 1] - yv[:, 1]).mean()), 5),
        "cdr_pred_sd": round(float(pv[:, 1].std()), 5),
        "cdr_true_sd": round(float(yv[:, 1].std()), 5),
    }
    if verbose:
        v = model.validation
        print(f"  [forecaster] holdout R^2 — CPR {v['cpr_r2']:.3f} | CDR {v['cdr_r2']:.3f}")
        print(f"  [forecaster] CDR pred sd {v['cdr_pred_sd']:.5f} vs true sd "
              f"{v['cdr_true_sd']:.5f}  (sd collapse check)")
    return model


def forecast_next(model: CPRCDRTransformer, macro_window: np.ndarray, season_ramp: np.ndarray,
                   credit_z: np.ndarray) -> tuple[float, float]:
    feats = np.concatenate([macro_window, season_ramp[:, None], credit_z[:, None]], axis=1)
    x = torch.tensor(feats, dtype=torch.float32).unsqueeze(0)
    with torch.no_grad():
        cpr, cdr = model(x).squeeze(0).tolist()
    return cpr, cdr
