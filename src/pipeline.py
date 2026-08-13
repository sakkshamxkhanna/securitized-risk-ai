"""End-to-end surveillance pipeline:

  pool -> stratification tape -> ML forecast (Transformer)
       -> correlated risk overlay (GNN) -> waterfall -> exposure/RWA
       -> VAE-generated scenario stress -> surveillance report

Run: python -m src.pipeline
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

from src import exposure, stratification, waterfall
from src.cashflow_engine import project_pool_cashflows
from src.models import gnn_risk, scenario_vae
from src.models.forecasting_transformer import forecast_next, train_forecaster
from src.pool_generator import generate_pool
from src.report import build_surveillance_report

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
HORIZON = 36


def _macro_to_cpr_cdr(model, macro_path: np.ndarray, pool_summary: dict, horizon: int):
    """Slides the transformer's 12-month lookback window forward along a
    48-month macro path to build per-period CPR/CDR vectors."""
    window = 12
    if len(macro_path) < horizon + window:
        pad = np.repeat(macro_path[-1:], horizon + window - len(macro_path), axis=0)
        macro_path = np.concatenate([macro_path, pad], axis=0)

    fico_z = (pool_summary["wa_fico"] - 715) / 55
    cprs, cdrs = [], []
    for t in range(horizon):
        macro_window = macro_path[t: t + window]
        season_ramp = np.clip(
            (pool_summary["wa_seasoning_mo"] + np.arange(t, t + window)) / 30, 0, 1.0)
        credit_z = np.full(window, fico_z, dtype=float)
        cpr, cdr = forecast_next(model, macro_window, season_ramp, credit_z)
        cprs.append(cpr)
        cdrs.append(cdr)
    return np.array(cprs), np.array(cdrs)


def run(seed: int = 42) -> dict:
    OUTPUT_DIR.mkdir(exist_ok=True)
    print("=" * 68)
    print("SECURITIZED PRODUCTS AI SURVEILLANCE PIPELINE")
    print("=" * 68)

    print("\n[1/7] Generating loan-level collateral pool...")
    pool = generate_pool(n_loans=2000, seed=seed)
    summary = stratification.pool_summary(pool)
    print(f"      {summary['loan_count']} loans | UPB ${summary['total_upb']:,.0f} | "
          f"WA FICO {summary['wa_fico']:.0f} | WA LTV {summary['wa_ltv']} | "
          f"WAC {summary['wa_coupon']}%")

    print("\n[2/7] Building stratification tapes...")
    fico_strat = stratification.fico_stratification(pool)
    ltv_strat = stratification.ltv_stratification(pool)
    geo_strat = stratification.geographic_stratification(pool)
    pool.to_csv(OUTPUT_DIR / "loan_tape.csv", index=False)
    fico_strat.to_csv(OUTPUT_DIR / "strat_fico.csv", index=False)
    ltv_strat.to_csv(OUTPUT_DIR / "strat_ltv.csv", index=False)
    geo_strat.to_csv(OUTPUT_DIR / "strat_geography.csv", index=False)
    print(f"      wrote loan_tape.csv + 3 stratification tapes -> output/")

    print("\n[3/7] Training CPR/CDR Transformer forecaster...")
    forecaster = train_forecaster(epochs=300)

    print("\n[4/7] Training correlated-risk GNN over originator x state cohorts...")
    _, cohorts = gnn_risk.train_gnn(pool)
    avg_mult = float(cohorts["gnn_risk_multiplier"].mean())
    top_risk = cohorts.nlargest(5, "gnn_risk_multiplier")[
        ["originator", "state", "upb", "gnn_risk_multiplier", "gnn_adjusted_cdr"]]
    cohorts.to_csv(OUTPUT_DIR / "cohort_risk_gnn.csv", index=False)
    print(f"      {len(cohorts)} cohorts | avg risk multiplier {avg_mult:.3f}x")
    print(f"      highest-risk cohort: {top_risk.iloc[0]['originator']} / "
          f"{top_risk.iloc[0]['state']} @ {top_risk.iloc[0]['gnn_risk_multiplier']:.2f}x")

    print("\n[5/7] Base-case projection + waterfall...")
    base_macro = np.stack([
        np.full(48, 0.3), np.full(48, 0.004), np.full(48, 4.2),
    ], axis=1)
    cpr_path, cdr_path = _macro_to_cpr_cdr(forecaster, base_macro, summary, HORIZON)
    cdr_path = cdr_path * avg_mult  # GNN correlated-risk overlay

    cashflows = project_pool_cashflows(
        summary["total_upb"], summary["wa_coupon"], 360, cpr_path, cdr_path)
    tranches = waterfall.build_capital_structure(summary["total_upb"])
    wf = waterfall.run_waterfall(cashflows, tranches)
    cashflows.to_csv(OUTPUT_DIR / "pool_cashflows_base.csv", index=False)
    wf.schedule.to_csv(OUTPUT_DIR / "waterfall_schedule_base.csv", index=False)
    print(f"      avg CPR {cpr_path.mean()*100:.2f}% | avg CDR {cdr_path.mean()*100:.2f}% | "
          f"cumulative loss ${cashflows['loss'].sum():,.0f}")

    print("\n[6/7] Exposure / RWA / expected loss...")
    pd_est = {
        "A (Senior)": float(cdr_path.mean() * 0.15),
        "M (Mezz)": float(cdr_path.mean() * 0.9),
        "B (Subordinate)": float(cdr_path.mean() * 2.5),
    }
    exp_table = exposure.compute_exposure_table(wf.tranche_summary, pd_est)
    exp_table.to_csv(OUTPUT_DIR / "exposure_rwa.csv", index=False)
    print(exp_table.to_string(index=False))

    print("\n[7/7] VAE scenario generation + stress testing...")
    vae, norm_stats = scenario_vae.train_scenario_generator(epochs=300)
    scenarios = scenario_vae.sample_scenarios(vae, norm_stats, n=5)
    stress_rows = []
    for i, path in enumerate(scenarios):
        label = scenario_vae.label_scenario(path)
        s_cpr, s_cdr = _macro_to_cpr_cdr(forecaster, path, summary, HORIZON)
        s_cdr = s_cdr * avg_mult
        s_cf = project_pool_cashflows(
            summary["total_upb"], summary["wa_coupon"], 360, s_cpr, s_cdr)
        s_wf = waterfall.run_waterfall(s_cf, waterfall.build_capital_structure(summary["total_upb"]))
        sub_final = s_wf.tranche_summary.loc[
            s_wf.tranche_summary["tranche"] == "B (Subordinate)", "final_balance"].iloc[0]
        sub_orig = summary["total_upb"] * 0.08
        writedown = max(sub_orig - sub_final - s_wf.tranche_summary.loc[
            s_wf.tranche_summary["tranche"] == "B (Subordinate)", "total_principal"].iloc[0], 0)
        stress_rows.append({
            "scenario": f"S{i+1}",
            "label": label,
            "avg_cpr_pct": round(float(s_cpr.mean() * 100), 2),
            "avg_cdr_pct": round(float(s_cdr.mean() * 100), 2),
            "cumulative_loss": round(float(s_cf["loss"].sum()), 2),
            "sub_tranche_writedown": round(float(writedown), 2),
        })
    stress = pd.DataFrame(stress_rows)
    stress.to_csv(OUTPUT_DIR / "scenario_stress.csv", index=False)
    print(stress.to_string(index=False))

    results = {
        "pool_summary": summary,
        "fico_strat": fico_strat,
        "ltv_strat": ltv_strat,
        "geo_strat": geo_strat,
        "cohorts": cohorts,
        "top_risk_cohorts": top_risk,
        "base_cashflows": cashflows,
        "waterfall": wf,
        "exposure": exp_table,
        "stress": stress,
        "avg_cpr": float(cpr_path.mean()),
        "avg_cdr": float(cdr_path.mean()),
        "gnn_avg_multiplier": avg_mult,
    }

    print("\n[+] Generating surveillance report...")
    report_path = build_surveillance_report(results, OUTPUT_DIR)
    print(f"      wrote {report_path}")

    with open(OUTPUT_DIR / "run_metrics.json", "w") as f:
        json.dump({
            "pool_summary": summary,
            "avg_cpr": results["avg_cpr"],
            "avg_cdr": results["avg_cdr"],
            "gnn_avg_multiplier": avg_mult,
            "cumulative_loss_base": float(cashflows["loss"].sum()),
            "scenarios": stress_rows,
        }, f, indent=2, default=str)

    print("\n" + "=" * 68)
    print("PIPELINE COMPLETE — artifacts in output/")
    print("=" * 68)
    return results


if __name__ == "__main__":
    run()
