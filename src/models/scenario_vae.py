"""Latent-variable macro scenario generator ("world model").

Trains a VAE over historical-style macro paths (rate incentive, HPI
growth, unemployment). Sampling the latent space produces *plausible*
new macro paths the model was never explicitly shown, which are then
pushed through the forecaster -> waterfall to stress tranche cashflows.

This is what lets the pipeline answer "what happens to the B tranche
under scenarios nobody hand-wrote?" rather than only running the three
canned up/base/down cases.
"""
from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn

MACRO_DIM = 3  # rate_incentive, hpi_growth, unemployment
PATH_LEN = 48  # 36-month projection horizon + 12-month lookback window


class MacroVAE(nn.Module):
    def __init__(self, latent_dim: int = 4):
        super().__init__()
        flat = MACRO_DIM * PATH_LEN
        self.latent_dim = latent_dim
        self.enc = nn.Sequential(nn.Linear(flat, 64), nn.ReLU(), nn.Linear(64, 32), nn.ReLU())
        self.mu = nn.Linear(32, latent_dim)
        self.logvar = nn.Linear(32, latent_dim)
        self.dec = nn.Sequential(
            nn.Linear(latent_dim, 32), nn.ReLU(),
            nn.Linear(32, 64), nn.ReLU(), nn.Linear(64, flat),
        )

    def encode(self, x):
        h = self.enc(x)
        return self.mu(h), self.logvar(h)

    def reparam(self, mu, logvar):
        std = torch.exp(0.5 * logvar)
        return mu + torch.randn_like(std) * std

    def decode(self, z):
        return self.dec(z)

    def forward(self, x):
        mu, logvar = self.encode(x)
        z = self.reparam(mu, logvar)
        return self.decode(z), mu, logvar


def _sample_regime_paths(n: int, seed: int = 11) -> np.ndarray:
    """Three latent macro regimes: benign, rate-shock, credit-crunch."""
    rng = np.random.default_rng(seed)
    paths = []
    for _ in range(n):
        regime = rng.choice(["benign", "rate_shock", "credit_crunch"], p=[0.5, 0.25, 0.25])
        if regime == "benign":
            rate = np.cumsum(rng.normal(0.05, 0.1, PATH_LEN))
            hpi = np.cumsum(rng.normal(0.004, 0.006, PATH_LEN))
            unemp = 4.0 + np.cumsum(rng.normal(-0.01, 0.06, PATH_LEN))
        elif regime == "rate_shock":
            rate = np.cumsum(rng.normal(-0.25, 0.12, PATH_LEN))
            hpi = np.cumsum(rng.normal(-0.003, 0.008, PATH_LEN))
            unemp = 4.5 + np.cumsum(rng.normal(0.05, 0.08, PATH_LEN))
        else:
            rate = np.cumsum(rng.normal(0.0, 0.1, PATH_LEN))
            hpi = np.cumsum(rng.normal(-0.012, 0.01, PATH_LEN))
            unemp = 5.0 + np.cumsum(rng.normal(0.18, 0.1, PATH_LEN))
        paths.append(np.stack([rate.clip(-2, 3), hpi.clip(-0.3, 0.3), unemp.clip(2, 12)], axis=1))
    return np.array(paths, dtype=np.float32)


def train_scenario_generator(epochs: int = 300, n_paths: int = 600):
    data = _sample_regime_paths(n_paths)
    mean, std = data.mean(axis=(0, 1)), data.std(axis=(0, 1)) + 1e-6
    norm = (data - mean) / std
    X = torch.tensor(norm.reshape(len(norm), -1))

    model = MacroVAE()
    opt = torch.optim.Adam(model.parameters(), lr=2e-3)
    model.train()
    for ep in range(epochs):
        opt.zero_grad()
        recon, mu, logvar = model(X)
        recon_loss = nn.functional.mse_loss(recon, X, reduction="mean")
        kld = -0.5 * torch.mean(1 + logvar - mu.pow(2) - logvar.exp())
        loss = recon_loss + 0.02 * kld
        loss.backward()
        opt.step()
        if ep % 100 == 0 or ep == epochs - 1:
            print(f"  [scenario-vae] epoch {ep:3d}  loss={loss.item():.5f}")
    model.eval()
    return model, (mean, std)


def sample_scenarios(model: MacroVAE, norm_stats, n: int = 5, seed: int = 21) -> list[np.ndarray]:
    mean, std = norm_stats
    torch.manual_seed(seed)
    with torch.no_grad():
        z = torch.randn(n, model.latent_dim)
        out = model.decode(z).numpy().reshape(n, PATH_LEN, MACRO_DIM)
    return [(p * std + mean) for p in out]


def label_scenario(path: np.ndarray) -> str:
    hpi_mean = path[:, 1].mean()
    unemp_end = path[-1, 2]
    rate_inc = path[:, 0].mean()
    if unemp_end > 6.0 and hpi_mean < 0:
        return "Credit stress (rising unemployment, HPI decline)"
    if rate_inc > 0.5:
        return "Rate rally (elevated prepayment incentive)"
    if hpi_mean < -0.02:
        return "Housing softening"
    if unemp_end < 4.0 and hpi_mean > 0.01:
        return "Benign (tight labour, HPI growth)"
    return "Base-like"
