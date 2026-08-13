"""Correctness tests for the analytical core.

The ML layers are stochastic, but the cashflow/waterfall mechanics must
be exactly right — these assert the structural invariants a desk relies on.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src import stratification, waterfall
from src.cashflow_engine import project_pool_cashflows
from src.pool_generator import generate_pool


@pytest.fixture(scope="module")
def pool():
    return generate_pool(n_loans=300, seed=1)


def test_pool_balances_are_sane(pool):
    assert (pool["current_balance"] <= pool["orig_balance"] + 1e-6).all()
    assert (pool["current_balance"] > 0).all()
    assert (pool["remaining_term_mo"] > 0).all()


def test_stratification_percentages_sum_to_100(pool):
    for strat in (stratification.fico_stratification(pool),
                  stratification.ltv_stratification(pool),
                  stratification.geographic_stratification(pool)):
        assert strat["pct_of_pool"].sum() == pytest.approx(100.0, abs=0.1)


def test_stratification_loan_counts_reconcile(pool):
    assert stratification.fico_stratification(pool)["loan_count"].sum() == len(pool)
    assert stratification.ltv_stratification(pool)["loan_count"].sum() == len(pool)


def test_cashflow_balance_declines_monotonically():
    cf = project_pool_cashflows(1_000_000, 6.0, 360,
                                 np.full(24, 0.08), np.full(24, 0.02))
    assert cf["ending_balance"].is_monotonic_decreasing
    assert cf["ending_balance"].iloc[-1] < 1_000_000


def test_zero_default_produces_zero_loss():
    cf = project_pool_cashflows(1_000_000, 6.0, 360,
                                 np.full(12, 0.08), np.zeros(12))
    assert cf["loss"].sum() == pytest.approx(0.0, abs=1e-6)


def test_higher_cdr_produces_higher_loss():
    low = project_pool_cashflows(1_000_000, 6.0, 360, np.full(24, 0.08), np.full(24, 0.01))
    high = project_pool_cashflows(1_000_000, 6.0, 360, np.full(24, 0.08), np.full(24, 0.05))
    assert high["loss"].sum() > low["loss"].sum()


def test_waterfall_never_overpays_tranche_principal():
    """Total principal to each tranche must not exceed its original balance."""
    upb = 1_000_000.0
    cf = project_pool_cashflows(upb, 6.0, 360, np.full(120, 0.15), np.full(120, 0.01))
    tranches = waterfall.build_capital_structure(upb)
    originals = {t.name: t.balance for t in tranches}
    wf = waterfall.run_waterfall(cf, tranches)
    for _, row in wf.tranche_summary.iterrows():
        assert row["total_principal"] <= originals[row["tranche"]] + 1e-6


def test_losses_hit_subordinate_before_senior():
    """Structural invariant: the senior tranche must not be written down
    while subordinate balance remains outstanding."""
    upb = 1_000_000.0
    cf = project_pool_cashflows(upb, 6.0, 360, np.zeros(36), np.full(36, 0.04))
    tranches = waterfall.build_capital_structure(upb)
    senior_orig = tranches[0].balance
    wf = waterfall.run_waterfall(cf, tranches)
    sched = wf.schedule
    sub_last = sched[sched["tranche"] == "B (Subordinate)"]["ending_balance"].iloc[-1]
    senior = wf.tranche_summary[wf.tranche_summary["tranche"] == "A (Senior)"].iloc[0]
    if sub_last > 0:
        written_down = senior_orig - senior["final_balance"] - senior["total_principal"]
        assert written_down == pytest.approx(0.0, abs=1e-6)


def test_tranche_balances_never_negative():
    upb = 1_000_000.0
    cf = project_pool_cashflows(upb, 6.0, 360, np.full(60, 0.1), np.full(60, 0.06))
    wf = waterfall.run_waterfall(cf, waterfall.build_capital_structure(upb))
    assert (wf.schedule["ending_balance"] >= -1e-6).all()


def test_capital_structure_sums_to_pool():
    upb = 5_000_000.0
    assert sum(t.balance for t in waterfall.build_capital_structure(upb)) == pytest.approx(upb, rel=1e-9)
