"""Sequential-pay tranche waterfall engine.

Given projected pool-level cashflows (scheduled principal, prepayments,
interest, losses from default), allocates cash to tranches: principal
paid sequentially senior-to-sub, interest paid pro-rata, losses absorbed
reverse-sequentially (sub tranche first).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class Tranche:
    name: str
    balance: float
    coupon: float  # annual, decimal
    seniority: int  # 1 = most senior


@dataclass
class WaterfallResult:
    schedule: pd.DataFrame  # per-period, per-tranche cashflows
    tranche_summary: pd.DataFrame


def build_capital_structure(total_upb: float) -> list[Tranche]:
    return [
        Tranche("A (Senior)", round(total_upb * 0.78, 2), 0.055, 1),
        Tranche("M (Mezz)", round(total_upb * 0.14, 2), 0.072, 2),
        Tranche("B (Subordinate)", round(total_upb * 0.08, 2), 0.095, 3),
    ]


def run_waterfall(pool_cashflows: pd.DataFrame, tranches: list[Tranche]) -> WaterfallResult:
    """pool_cashflows needs columns: period, scheduled_principal, prepayment,
    interest_collected, loss (realized default loss for the period)."""
    tr = {t.name: Tranche(t.name, t.balance, t.coupon, t.seniority) for t in tranches}
    order = sorted(tr.values(), key=lambda t: t.seniority)
    reverse_order = sorted(tr.values(), key=lambda t: -t.seniority)

    rows = []
    for _, period_row in pool_cashflows.iterrows():
        total_principal = period_row["scheduled_principal"] + period_row["prepayment"]
        interest_pool = period_row["interest_collected"]
        loss = period_row["loss"]

        # 1) losses hit subordinate-most tranche first
        for t in reverse_order:
            if loss <= 0:
                break
            hit = min(t.balance, loss)
            t.balance -= hit
            loss -= hit

        # 2) interest pro-rata to outstanding balance, capped at each tranche's accrual
        total_bal = sum(t.balance for t in order) or 1.0
        interest_paid = {}
        for t in order:
            accrued = t.balance * t.coupon / 12
            share = interest_pool * (t.balance / total_bal) if total_bal else 0
            interest_paid[t.name] = min(accrued, share)

        # 3) principal sequential senior -> sub
        principal_paid = {}
        remaining = total_principal
        for t in order:
            pay = min(t.balance, remaining)
            t.balance -= pay
            remaining -= pay
            principal_paid[t.name] = pay

        for t in order:
            rows.append({
                "period": period_row["period"],
                "tranche": t.name,
                "beginning_balance_note": None,
                "principal_paid": round(principal_paid[t.name], 2),
                "interest_paid": round(interest_paid[t.name], 2),
                "ending_balance": round(t.balance, 2),
            })

    schedule = pd.DataFrame(rows)
    summary = schedule.groupby("tranche").agg(
        total_principal=("principal_paid", "sum"),
        total_interest=("interest_paid", "sum"),
        final_balance=("ending_balance", "last"),
    ).reset_index()
    return WaterfallResult(schedule=schedule, tranche_summary=summary)
