"""Exposure / RWA / expected-loss analytics per tranche.

Simplified standardized-approach style risk weighting by rating proxy
(derived from tranche seniority + realized loss coverage), the kind of
metric the JD calls out: "analyse daily exposure, risk, RWA... expected loss".
"""
from __future__ import annotations

import pandas as pd

RATING_RISK_WEIGHTS = {
    "AAA": 0.20,
    "AA": 0.20,
    "A": 0.50,
    "BBB": 1.00,
    "BB": 2.50,
    "B": 4.25,
    "Unrated": 12.50,
}


def proxy_rating(tranche_name: str) -> str:
    return {
        "A (Senior)": "AAA",
        "M (Mezz)": "BBB",
        "B (Subordinate)": "BB",
    }.get(tranche_name, "Unrated")


def compute_exposure_table(tranche_summary: pd.DataFrame, pd_estimate: dict[str, float],
                            lgd: float = 0.35) -> pd.DataFrame:
    rows = []
    for _, r in tranche_summary.iterrows():
        rating = proxy_rating(r["tranche"])
        rw = RATING_RISK_WEIGHTS[rating]
        ead = r["final_balance"]
        pd_t = pd_estimate.get(r["tranche"], 0.02)
        el = ead * pd_t * lgd
        rwa = ead * rw
        rows.append({
            "tranche": r["tranche"],
            "proxy_rating": rating,
            "ead": round(ead, 2),
            "pd": round(pd_t, 4),
            "lgd": lgd,
            "expected_loss": round(el, 2),
            "risk_weight": rw,
            "rwa": round(rwa, 2),
        })
    return pd.DataFrame(rows)
