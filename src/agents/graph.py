"""LangGraph orchestration of the surveillance pipeline.

Each analytical stage is a node with typed state passed between them,
so the pipeline is inspectable, resumable, and individually cacheable
rather than one monolithic script. Conditional edges route to an
escalation node when loss metrics breach desk thresholds.

Run: python -m src.agents.graph
"""
from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any, TypedDict

import numpy as np
import pandas as pd
from langgraph.graph import END, START, StateGraph

from src import cache, exposure, stratification, waterfall
from src.cashflow_engine import project_pool_cashflows
from src.models import gnn_risk, scenario_vae
from src.models.forecasting_transformer import forecast_next, train_forecaster
from src.pool_generator import generate_pool
from src.report import build_surveillance_report

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "output"
HORIZON = 36
LOSS_ESCALATION_THRESHOLD = 0.02  # cumulative loss / UPB


class SurveillanceState(TypedDict, total=False):
    seed: int
    pool: Any
    summary: dict
    fico_strat: Any
    ltv_strat: Any
    geo_strat: Any
    forecaster: Any
    cohorts: Any
    gnn_avg_multiplier: float
    base_cashflows: Any
    waterfall: Any
    exposure: Any
    stress: Any
    avg_cpr: float
    avg_cdr: float
    escalations: list[str]
    lora_commentary: list[str]
    log: Annotated[list[str], lambda a, b: a + b]


def _macro_to_cpr_cdr(model, macro_path: np.ndarray, summary: dict, horizon: int):
    window = 12
    if len(macro_path) < horizon + window:
        pad = np.repeat(macro_path[-1:], horizon + window - len(macro_path), axis=0)
        macro_path = np.concatenate([macro_path, pad], axis=0)
    fico_z = (summary["wa_fico"] - 715) / 55
    cprs, cdrs = [], []
    for t in range(horizon):
        season_ramp = np.clip((summary["wa_seasoning_mo"] + np.arange(t, t + window)) / 30, 0, 1.0)
        cpr, cdr = forecast_next(model, macro_path[t: t + window], season_ramp,
                                  np.full(window, fico_z, dtype=float))
        cprs.append(cpr)
        cdrs.append(cdr)
    return np.array(cprs), np.array(cdrs)


# ---------------------------------------------------------------- nodes

def ingest_node(state: SurveillanceState) -> dict:
    pool = generate_pool(n_loans=2000, seed=state.get("seed", 42))
    summary = stratification.pool_summary(pool)
    return {"pool": pool, "summary": summary,
            "log": [f"ingest: {summary['loan_count']} loans, UPB ${summary['total_upb']:,.0f}"]}


def stratify_node(state: SurveillanceState) -> dict:
    pool = state["pool"]
    OUTPUT_DIR.mkdir(exist_ok=True)
    fico = stratification.fico_stratification(pool)
    ltv = stratification.ltv_stratification(pool)
    geo = stratification.geographic_stratification(pool)
    pool.to_csv(OUTPUT_DIR / "loan_tape.csv", index=False)
    fico.to_csv(OUTPUT_DIR / "strat_fico.csv", index=False)
    ltv.to_csv(OUTPUT_DIR / "strat_ltv.csv", index=False)
    geo.to_csv(OUTPUT_DIR / "strat_geography.csv", index=False)
    return {"fico_strat": fico, "ltv_strat": ltv, "geo_strat": geo,
            "log": [f"stratify: tapes written, top state {geo.iloc[0]['state']} "
                    f"{geo.iloc[0]['pct_of_pool']:.1f}%"]}


def forecast_node(state: SurveillanceState) -> dict:
    key = cache.make_key("forecaster", {"v": 3})
    model = cache.get(key)
    cached = model is not None
    if not cached:
        model = train_forecaster(epochs=300, verbose=False)
        cache.set(key, model)
    v = getattr(model, "validation", {})
    return {"forecaster": model,
            "log": [f"forecast: {'cache hit' if cached else 'trained'} "
                    f"(CPR R2 {v.get('cpr_r2')}, CDR R2 {v.get('cdr_r2')})"]}


def risk_graph_node(state: SurveillanceState) -> dict:
    _, cohorts = gnn_risk.train_gnn(state["pool"], epochs=80)
    cohorts.to_csv(OUTPUT_DIR / "cohort_risk_gnn.csv", index=False)
    avg = float(cohorts["gnn_risk_multiplier"].mean())
    worst = cohorts.nlargest(1, "gnn_risk_multiplier").iloc[0]
    return {"cohorts": cohorts, "gnn_avg_multiplier": avg,
            "log": [f"risk_graph: {len(cohorts)} cohorts, avg {avg:.3f}x, "
                    f"worst {worst['originator']}/{worst['state']} {worst['gnn_risk_multiplier']:.2f}x"]}


def waterfall_node(state: SurveillanceState) -> dict:
    summary = state["summary"]
    base_macro = np.stack([np.full(48, 0.3), np.full(48, 0.004), np.full(48, 4.2)], axis=1)
    cpr, cdr = _macro_to_cpr_cdr(state["forecaster"], base_macro, summary, HORIZON)
    cdr = cdr * state["gnn_avg_multiplier"]
    cf = project_pool_cashflows(summary["total_upb"], summary["wa_coupon"], 360, cpr, cdr)
    wf = waterfall.run_waterfall(cf, waterfall.build_capital_structure(summary["total_upb"]))
    cf.to_csv(OUTPUT_DIR / "pool_cashflows_base.csv", index=False)
    wf.schedule.to_csv(OUTPUT_DIR / "waterfall_schedule_base.csv", index=False)
    return {"base_cashflows": cf, "waterfall": wf,
            "avg_cpr": float(cpr.mean()), "avg_cdr": float(cdr.mean()),
            "log": [f"waterfall: CPR {cpr.mean()*100:.2f}%, CDR {cdr.mean()*100:.2f}%, "
                    f"loss ${cf['loss'].sum():,.0f}"]}


def exposure_node(state: SurveillanceState) -> dict:
    cdr = state["avg_cdr"]
    pd_est = {"A (Senior)": cdr * 0.15, "M (Mezz)": cdr * 0.9, "B (Subordinate)": cdr * 2.5}
    table = exposure.compute_exposure_table(state["waterfall"].tranche_summary, pd_est)
    table.to_csv(OUTPUT_DIR / "exposure_rwa.csv", index=False)
    return {"exposure": table,
            "log": [f"exposure: RWA ${table['rwa'].sum():,.0f}, EL ${table['expected_loss'].sum():,.0f}"]}


def stress_node(state: SurveillanceState) -> dict:
    summary = state["summary"]
    key = cache.make_key("vae", {"v": 2})
    cached_vae = cache.get(key)
    if cached_vae:
        vae, stats = cached_vae
    else:
        vae, stats = scenario_vae.train_scenario_generator(epochs=300)
        cache.set(key, (vae, stats))

    rows = []
    for i, path in enumerate(scenario_vae.sample_scenarios(vae, stats, n=5)):
        s_cpr, s_cdr = _macro_to_cpr_cdr(state["forecaster"], path, summary, HORIZON)
        s_cdr = s_cdr * state["gnn_avg_multiplier"]
        s_cf = project_pool_cashflows(summary["total_upb"], summary["wa_coupon"], 360, s_cpr, s_cdr)
        s_wf = waterfall.run_waterfall(
            s_cf, waterfall.build_capital_structure(summary["total_upb"]))
        sub = s_wf.tranche_summary[s_wf.tranche_summary["tranche"] == "B (Subordinate)"].iloc[0]
        writedown = max(summary["total_upb"] * 0.08 - sub["final_balance"] - sub["total_principal"], 0)
        rows.append({
            "scenario": f"S{i+1}", "label": scenario_vae.label_scenario(path),
            "avg_cpr_pct": round(float(s_cpr.mean() * 100), 2),
            "avg_cdr_pct": round(float(s_cdr.mean() * 100), 2),
            "cumulative_loss": round(float(s_cf["loss"].sum()), 2),
            "sub_tranche_writedown": round(float(writedown), 2),
        })
    stress = pd.DataFrame(rows)
    stress.to_csv(OUTPUT_DIR / "scenario_stress.csv", index=False)
    return {"stress": stress,
            "log": [f"stress: {len(rows)} scenarios, worst loss "
                    f"${stress['cumulative_loss'].max():,.0f}"]}


def escalation_node(state: SurveillanceState) -> dict:
    upb = state["summary"]["total_upb"]
    worst = state["stress"].loc[state["stress"]["cumulative_loss"].idxmax()]
    ratio = worst["cumulative_loss"] / upb
    msg = (f"ESCALATION: scenario {worst['scenario']} ({worst['label']}) projects "
           f"cumulative loss of {ratio*100:.2f}% of UPB, above the "
           f"{LOSS_ESCALATION_THRESHOLD*100:.1f}% desk threshold.")
    return {"escalations": [msg], "log": [msg]}


def narrative_node(state: SurveillanceState) -> dict:
    """Optional LoRA-drafted commentary. Skipped if peft/transformers absent
    or if SKIP_LORA is set — the report degrades to deterministic text."""
    import os
    if os.environ.get("SKIP_LORA"):
        return {"log": ["narrative: skipped (SKIP_LORA)"]}
    from src.models import lora_narrative
    key = cache.make_key("lora", {"v": 2})
    mt = cache.get(key)
    if mt is None:
        mt = lora_narrative.train_adapter(epochs=400, verbose=False)
        if mt is not None:
            cache.set(key, mt)
    if mt is None:
        return {"log": ["narrative: unavailable, using deterministic text"]}
    prompts = [
        "Surveillance commentary: prepayment speeds",
        "Surveillance commentary: the subordinate tranche",
        "Surveillance commentary: credit enhancement",
    ]
    out = []
    for p in prompts:
        c = lora_narrative.generate_commentary(mt, p)
        if c:
            out.append(f"{p.split(': ')[1].capitalize()} {c}")
    return {"lora_commentary": out, "log": [f"narrative: {len(out)} LoRA-drafted lines"]}


def report_node(state: SurveillanceState) -> dict:
    results = {
        "pool_summary": state["summary"], "fico_strat": state["fico_strat"],
        "ltv_strat": state["ltv_strat"], "geo_strat": state["geo_strat"],
        "cohorts": state["cohorts"],
        "top_risk_cohorts": state["cohorts"].nlargest(5, "gnn_risk_multiplier")[
            ["originator", "state", "upb", "gnn_risk_multiplier", "gnn_adjusted_cdr"]],
        "base_cashflows": state["base_cashflows"], "waterfall": state["waterfall"],
        "exposure": state["exposure"], "stress": state["stress"],
        "avg_cpr": state["avg_cpr"], "avg_cdr": state["avg_cdr"],
        "gnn_avg_multiplier": state["gnn_avg_multiplier"],
        "escalations": state.get("escalations", []),
        "lora_commentary": state.get("lora_commentary", []),
        "forecaster_validation": getattr(state["forecaster"], "validation", {}),
    }
    path = build_surveillance_report(results, OUTPUT_DIR)
    return {"log": [f"report: written to {path.name}"]}


def _route_after_stress(state: SurveillanceState) -> str:
    worst = state["stress"]["cumulative_loss"].max()
    return "escalate" if worst / state["summary"]["total_upb"] > LOSS_ESCALATION_THRESHOLD else "report"


def build_graph():
    g = StateGraph(SurveillanceState)
    g.add_node("ingest", ingest_node)
    g.add_node("stratify", stratify_node)
    g.add_node("forecast", forecast_node)
    g.add_node("risk_graph", risk_graph_node)
    g.add_node("waterfall", waterfall_node)
    g.add_node("exposure", exposure_node)
    g.add_node("stress", stress_node)
    g.add_node("escalate", escalation_node)
    g.add_node("narrative", narrative_node)
    g.add_node("report", report_node)

    g.add_edge(START, "ingest")
    g.add_edge("ingest", "stratify")
    g.add_edge("stratify", "forecast")
    g.add_edge("forecast", "risk_graph")
    g.add_edge("risk_graph", "waterfall")
    g.add_edge("waterfall", "exposure")
    g.add_edge("exposure", "stress")
    g.add_conditional_edges("stress", _route_after_stress,
                             {"escalate": "escalate", "report": "narrative"})
    g.add_edge("escalate", "narrative")
    g.add_edge("narrative", "report")
    g.add_edge("report", END)
    return g.compile()


def main(seed: int = 42):
    print("=" * 68)
    print("SECURITIZED PRODUCTS AI SURVEILLANCE — LangGraph orchestration")
    print(f"cache backend: {cache.backend_name()}")
    print("=" * 68)
    app = build_graph()
    final = app.invoke({"seed": seed, "log": [], "escalations": []})
    print()
    for line in final["log"]:
        print(f"  * {line}")
    if final.get("escalations"):
        print("\n  !! escalations raised:")
        for e in final["escalations"]:
            print(f"     {e}")
    print("\nartifacts -> output/")
    return final


if __name__ == "__main__":
    main()
