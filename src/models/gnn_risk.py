"""Graph Neural Network for correlated default risk.

A per-loan hazard model treats loans as independent. In reality, loans
sharing an originator (underwriting-quality contagion) or a state
(regional HPI / employment shock) have *correlated* default risk — the
exact tail risk that blew up 2008-vintage RMBS. This module builds a
cohort-level exposure graph (originator x state) and runs a 2-layer
GCN, implemented from first principles (no torch_geometric dependency),
to propagate risk across connected cohorts before scoring expected loss.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import torch
import torch.nn as nn


def build_cohort_graph(pool: pd.DataFrame):
    cohorts = pool.groupby(["originator", "state"]).agg(
        upb=("current_balance", "sum"),
        fico=("fico", "mean"),
        ltv=("ltv", "mean"),
        dti=("dti", "mean"),
        base_cdr=("base_cdr", "mean"),
        loan_count=("loan_id", "count"),
    ).reset_index()
    cohorts["cohort_id"] = range(len(cohorts))

    n = len(cohorts)
    adj = np.zeros((n, n), dtype=np.float32)
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            same_orig = cohorts.loc[i, "originator"] == cohorts.loc[j, "originator"]
            same_state = cohorts.loc[i, "state"] == cohorts.loc[j, "state"]
            if same_orig:
                adj[i, j] += 0.6
            if same_state:
                adj[i, j] += 0.4
    adj += np.eye(n, dtype=np.float32)  # self-loops

    deg = adj.sum(axis=1)
    d_inv_sqrt = np.diag(1.0 / np.sqrt(np.maximum(deg, 1e-6)))
    adj_norm = d_inv_sqrt @ adj @ d_inv_sqrt

    feats = cohorts[["fico", "ltv", "dti", "base_cdr"]].copy()
    feats = (feats - feats.mean()) / feats.std().replace(0, 1)
    X = torch.tensor(feats.values, dtype=torch.float32)
    A = torch.tensor(adj_norm, dtype=torch.float32)
    return cohorts, X, A


class GCNLayer(nn.Module):
    def __init__(self, in_dim: int, out_dim: int):
        super().__init__()
        self.lin = nn.Linear(in_dim, out_dim)

    def forward(self, x: torch.Tensor, a_norm: torch.Tensor) -> torch.Tensor:
        return a_norm @ self.lin(x)


class CorrelatedRiskGCN(nn.Module):
    def __init__(self, in_dim: int = 4, hidden: int = 16):
        super().__init__()
        self.gc1 = GCNLayer(in_dim, hidden)
        self.gc2 = GCNLayer(hidden, hidden)
        self.out = nn.Linear(hidden, 1)
        self.act = nn.ReLU()

    def forward(self, x: torch.Tensor, a_norm: torch.Tensor) -> torch.Tensor:
        h = self.act(self.gc1(x, a_norm))
        h = self.act(self.gc2(h, a_norm))
        risk_multiplier = 1.0 + torch.sigmoid(self.out(h)).squeeze(-1)  # 1.0x - 2.0x
        return risk_multiplier


def train_gnn(pool: pd.DataFrame, epochs: int = 80):
    """Trains against a synthetic 'stress-realized' CDR target that
    injects extra correlated loss on cohorts sharing an originator with
    a bad-vintage flag, so the GNN has a real correlation signal to learn."""
    cohorts, X, A = build_cohort_graph(pool)

    rng = np.random.default_rng(3)
    bad_originators = set(rng.choice(cohorts["originator"].unique(), size=1))
    stressed_target = cohorts["base_cdr"].values.copy()
    mask = cohorts["originator"].isin(bad_originators).values
    stressed_target[mask] *= 1.8
    same_state_bad = cohorts["state"].isin(cohorts.loc[mask, "state"].unique()).values
    stressed_target[same_state_bad & ~mask] *= 1.25
    target_multiplier = torch.tensor(stressed_target / cohorts["base_cdr"].values, dtype=torch.float32)

    model = CorrelatedRiskGCN(in_dim=X.shape[1])
    opt = torch.optim.Adam(model.parameters(), lr=1e-2)
    loss_fn = nn.MSELoss()
    model.train()
    for ep in range(epochs):
        opt.zero_grad()
        pred = model(X, A)
        loss = loss_fn(pred, target_multiplier)
        loss.backward()
        opt.step()
        if ep % 20 == 0 or ep == epochs - 1:
            print(f"  [gnn] epoch {ep:3d}  mse={loss.item():.5f}")
    model.eval()

    with torch.no_grad():
        multiplier = model(X, A).numpy()
    cohorts["gnn_risk_multiplier"] = multiplier.round(3)
    cohorts["gnn_adjusted_cdr"] = (cohorts["base_cdr"] * cohorts["gnn_risk_multiplier"]).round(4)
    return model, cohorts
