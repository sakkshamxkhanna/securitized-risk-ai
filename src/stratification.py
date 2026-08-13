"""Stratification tape generation — the deliverable Business Management
teams produce daily for desks, trustees, and rating agencies."""
from __future__ import annotations

import numpy as np
import pandas as pd


def _wavg(df: pd.DataFrame, col: str, weight_col: str = "current_balance") -> float:
    if df[weight_col].sum() == 0:
        return float("nan")
    return float(np.average(df[col], weights=df[weight_col]))


def _bucket_strat(df: pd.DataFrame, col: str, bins: list, labels: list) -> pd.DataFrame:
    buckets = pd.cut(df[col], bins=bins, labels=labels, right=False)
    rows = []
    total_upb = df["current_balance"].sum()
    for label, group in df.groupby(buckets, observed=True):
        upb = group["current_balance"].sum()
        rows.append({
            "bucket": label,
            "loan_count": len(group),
            "upb": round(upb, 2),
            "pct_of_pool": round(100 * upb / total_upb, 2) if total_upb else 0.0,
            "wa_coupon": round(_wavg(group, "coupon"), 3) if len(group) else None,
            "wa_fico": round(_wavg(group, "fico"), 0) if len(group) else None,
            "wa_ltv": round(_wavg(group, "ltv"), 1) if len(group) else None,
        })
    return pd.DataFrame(rows)


def fico_stratification(df: pd.DataFrame) -> pd.DataFrame:
    bins = [0, 620, 660, 700, 740, 780, 900]
    labels = ["<620", "620-659", "660-699", "700-739", "740-779", "780+"]
    return _bucket_strat(df, "fico", bins, labels)


def ltv_stratification(df: pd.DataFrame) -> pd.DataFrame:
    bins = [0, 60, 70, 80, 90, 100, 200]
    labels = ["<60", "60-69", "70-79", "80-89", "90-99", "100+"]
    return _bucket_strat(df, "ltv", bins, labels)


def geographic_stratification(df: pd.DataFrame) -> pd.DataFrame:
    total_upb = df["current_balance"].sum()
    g = df.groupby("state").agg(
        loan_count=("loan_id", "count"),
        upb=("current_balance", "sum"),
    ).reset_index()
    g["pct_of_pool"] = (100 * g["upb"] / total_upb).round(2)
    return g.sort_values("upb", ascending=False).reset_index(drop=True)


def pool_summary(df: pd.DataFrame) -> dict:
    return {
        "loan_count": len(df),
        "total_upb": round(df["current_balance"].sum(), 2),
        "wa_coupon": round(_wavg(df, "coupon"), 3),
        "wa_fico": round(_wavg(df, "fico"), 0),
        "wa_ltv": round(_wavg(df, "ltv"), 1),
        "wa_dti": round(_wavg(df, "dti"), 1),
        "wa_seasoning_mo": round(_wavg(df, "seasoning_mo"), 1),
    }
