"""Projects pool-level monthly cashflows using model-predicted CPR/CDR,
then feeds the waterfall.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def project_pool_cashflows(pool_upb: float, wa_coupon: float, wa_term: int,
                            cpr_path: np.ndarray, cdr_path: np.ndarray,
                            severity: float = 0.35) -> pd.DataFrame:
    """cpr_path / cdr_path are annualized rates per period."""
    periods = len(cpr_path)
    bal = pool_upb
    r = wa_coupon / 1200
    rows = []
    for t in range(periods):
        if bal <= 0:
            rows.append({"period": t + 1, "scheduled_principal": 0.0, "prepayment": 0.0,
                          "interest_collected": 0.0, "loss": 0.0, "ending_balance": 0.0})
            continue

        smm = 1 - (1 - cpr_path[t]) ** (1 / 12)     # single monthly mortality
        mdr = 1 - (1 - cdr_path[t]) ** (1 / 12)     # monthly default rate

        interest = bal * r
        n_remaining = max(wa_term - t, 1)
        pmt = bal * r / (1 - (1 + r) ** -n_remaining) if r > 0 else bal / n_remaining
        sched_principal = max(pmt - interest, 0)

        defaulted = bal * mdr
        prepaid = (bal - sched_principal - defaulted) * smm
        loss = defaulted * severity
        recovery = defaulted - loss

        bal = max(bal - sched_principal - prepaid - defaulted, 0)
        rows.append({
            "period": t + 1,
            "scheduled_principal": round(sched_principal, 2),
            "prepayment": round(prepaid + recovery, 2),
            "interest_collected": round(interest, 2),
            "loss": round(loss, 2),
            "ending_balance": round(bal, 2),
        })
    return pd.DataFrame(rows)
