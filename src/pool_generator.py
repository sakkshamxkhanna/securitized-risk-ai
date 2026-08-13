"""Synthetic RMBS/CMBS loan-level collateral pool generator.

Produces a loan-level table with the fields a securitized-products
desk actually stratifies on: FICO, LTV, DTI, coupon, seasoning,
geography, originator/servicer, property type.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

STATES = ["CA", "TX", "FL", "NY", "IL", "GA", "NC", "AZ", "OH", "WA"]
PROPERTY_TYPES = ["SFR", "Condo", "2-4 Unit", "Multifamily"]
ORIGINATORS = ["Meridian Home Loans", "Coastal Mortgage Co", "Apex Funding", "Highline Capital"]
SERVICERS = ["Summit Loan Servicing", "Northgate Servicing", "Pier Asset Mgmt"]


def generate_pool(n_loans: int = 2000, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    orig_balance = rng.lognormal(mean=12.4, sigma=0.35, size=n_loans).clip(80_000, 1_500_000)
    fico = rng.normal(715, 55, size=n_loans).clip(580, 820).round().astype(int)
    ltv = rng.normal(74, 12, size=n_loans).clip(35, 97).round(1)
    dti = rng.normal(36, 8, size=n_loans).clip(10, 55).round(1)
    coupon = rng.normal(6.4, 0.9, size=n_loans).clip(3.5, 11.0).round(3)
    seasoning = rng.integers(1, 48, size=n_loans)
    orig_term = rng.choice([180, 360], size=n_loans, p=[0.15, 0.85])
    remaining_term = (orig_term - seasoning).clip(min=1)

    # naive scheduled amortization to get a current balance from seasoning
    monthly_rate = coupon / 1200
    pmt = orig_balance * monthly_rate / (1 - (1 + monthly_rate) ** -orig_term)
    current_balance = np.zeros(n_loans)
    for i in range(n_loans):
        bal = orig_balance[i]
        r = monthly_rate[i]
        for _ in range(int(seasoning[i])):
            interest = bal * r
            principal = pmt[i] - interest
            bal = max(bal - principal, 0)
        current_balance[i] = bal

    df = pd.DataFrame({
        "loan_id": [f"L{100000 + i}" for i in range(n_loans)],
        "orig_balance": orig_balance.round(2),
        "current_balance": current_balance.round(2),
        "coupon": coupon,
        "fico": fico,
        "ltv": ltv,
        "dti": dti,
        "seasoning_mo": seasoning,
        "remaining_term_mo": remaining_term,
        "state": rng.choice(STATES, size=n_loans),
        "property_type": rng.choice(PROPERTY_TYPES, size=n_loans, p=[0.65, 0.15, 0.12, 0.08]),
        "originator": rng.choice(ORIGINATORS, size=n_loans),
        "servicer": rng.choice(SERVICERS, size=n_loans),
    })

    # baseline monthly prepay (CPR) and default (CDR) hazard, driven by
    # rate incentive, credit risk (FICO/LTV/DTI), and seasoning ramp.
    rate_incentive = (7.0 - df["coupon"]).clip(lower=-2, upper=3)
    season_ramp = (df["seasoning_mo"] / 30).clip(upper=1.0)
    df["base_cpr"] = (0.06 + 0.05 * rate_incentive.clip(lower=0) * season_ramp
                       - 0.01 * (df["fico"] < 660)).clip(0.01, 0.45)
    credit_risk = (700 - df["fico"]) / 100 + (df["ltv"] - 70) / 100 + (df["dti"] - 36) / 150
    df["base_cdr"] = (0.008 + 0.01 * credit_risk.clip(lower=0)).clip(0.001, 0.12)

    return df


if __name__ == "__main__":
    pool = generate_pool()
    print(pool.head())
    print(f"\n{len(pool)} loans | UPB ${pool['current_balance'].sum():,.0f} | "
          f"WA FICO {np.average(pool['fico'], weights=pool['current_balance']):.0f} | "
          f"WA LTV {np.average(pool['ltv'], weights=pool['current_balance']):.1f}")
