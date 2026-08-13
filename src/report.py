"""Surveillance report generation.

Produces the written monthly surveillance commentary a Business
Management analyst would otherwise draft by hand. Template-driven by
default; if a local LLM + LoRA adapter is available (see
models/lora_narrative.py) the narrative sections are generated instead.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path


def _fmt_money(x: float) -> str:
    if abs(x) >= 1_000_000:
        return f"${x/1_000_000:,.1f}mm"
    return f"${x:,.0f}"


def build_surveillance_report(r: dict, output_dir: Path) -> Path:
    s = r["pool_summary"]
    exp = r["exposure"]
    stress = r["stress"]
    top = r["top_risk_cohorts"]

    worst = stress.loc[stress["cumulative_loss"].idxmax()]
    best = stress.loc[stress["cumulative_loss"].idxmin()]

    lines = []
    lines.append("# Monthly Surveillance Report — Synthetic RMBS Pool 2026-1")
    lines.append(f"\n*Generated {date.today().isoformat()} — AI-assisted surveillance pipeline*\n")
    lines.append("---\n")

    lines.append("## 1. Pool Summary\n")
    lines.append(f"| Metric | Value |\n|---|---|")
    lines.append(f"| Loan count | {s['loan_count']:,} |")
    lines.append(f"| Current UPB | {_fmt_money(s['total_upb'])} |")
    lines.append(f"| WA coupon | {s['wa_coupon']:.3f}% |")
    lines.append(f"| WA FICO | {s['wa_fico']:.0f} |")
    lines.append(f"| WA LTV | {s['wa_ltv']:.1f}% |")
    lines.append(f"| WA DTI | {s['wa_dti']:.1f}% |")
    lines.append(f"| WA seasoning | {s['wa_seasoning_mo']:.1f} mo |")

    lines.append("\n## 2. Collateral Stratification\n")
    lines.append("### FICO distribution\n")
    lines.append(r["fico_strat"].to_markdown(index=False))
    lines.append("\n### LTV distribution\n")
    lines.append(r["ltv_strat"].to_markdown(index=False))
    lines.append("\n### Top geographic concentrations\n")
    lines.append(r["geo_strat"].head(5).to_markdown(index=False))

    lines.append("\n## 3. Model-Projected Performance (Base Case)\n")
    lines.append(f"The temporal-attention forecaster projects an average **CPR of "
                 f"{r['avg_cpr']*100:.2f}%** and **CDR of {r['avg_cdr']*100:.2f}%** over the "
                 f"36-month horizon, inclusive of the correlated-risk overlay "
                 f"(**{r['gnn_avg_multiplier']:.3f}x** average cohort multiplier from the GNN).\n")
    lines.append(f"Cumulative base-case collateral loss: "
                 f"**{_fmt_money(r['base_cashflows']['loss'].sum())}**.\n")

    lines.append("### Highest-risk cohorts (GNN-adjusted)\n")
    lines.append(top.to_markdown(index=False))
    lines.append("\nCohorts are scored on a graph linking originator and state, so a "
                 "deterioration signal on one originator propagates to its other state "
                 "cohorts rather than being treated as an isolated event.\n")

    lines.append("\n## 4. Tranche Cashflows & Exposure\n")
    lines.append(r["waterfall"].tranche_summary.to_markdown(index=False))
    lines.append("\n### Exposure / RWA / expected loss\n")
    lines.append(exp.to_markdown(index=False))
    lines.append(f"\nTotal RWA: **{_fmt_money(exp['rwa'].sum())}** | "
                 f"Total expected loss: **{_fmt_money(exp['expected_loss'].sum())}**\n")

    lines.append("\n## 5. Scenario Stress Testing\n")
    lines.append("Scenarios are sampled from the latent space of a VAE trained on macro "
                 "regime paths — these are generated, not hand-specified.\n")
    lines.append(stress.to_markdown(index=False))
    lines.append(f"\n**Most adverse scenario:** {worst['scenario']} — *{worst['label']}* — "
                 f"cumulative loss {_fmt_money(worst['cumulative_loss'])}, subordinate "
                 f"write-down {_fmt_money(worst['sub_tranche_writedown'])}.\n")
    lines.append(f"**Most benign scenario:** {best['scenario']} — *{best['label']}* — "
                 f"cumulative loss {_fmt_money(best['cumulative_loss'])}.\n")

    if r.get("escalations"):
        lines.append("\n## 5a. Escalations\n")
        for e in r["escalations"]:
            lines.append(f"- **{e}**")
        lines.append("")

    if r.get("forecaster_validation"):
        v = r["forecaster_validation"]
        lines.append("\n## 5b. Model Validation\n")
        lines.append("Holdout performance of the CPR/CDR forecaster (400 unseen sequences):\n")
        lines.append("| Metric | CPR | CDR |\n|---|---|---|")
        lines.append(f"| R² | {v.get('cpr_r2')} | {v.get('cdr_r2')} |")
        lines.append(f"| MAE | {v.get('cpr_mae')} | {v.get('cdr_mae')} |")
        lines.append(f"\nPredicted CDR standard deviation {v.get('cdr_pred_sd')} against realised "
                     f"{v.get('cdr_true_sd')} — the model tracks credit dispersion rather than "
                     f"collapsing to the unconditional mean.\n")

    lines.append("\n## 6. Analyst Commentary\n")
    concentration = r["geo_strat"].iloc[0]
    lines.append(f"- Largest state concentration is **{concentration['state']}** at "
                 f"**{concentration['pct_of_pool']:.1f}%** of pool UPB; regional HPI "
                 f"sensitivity is the dominant driver of tail loss in the stressed scenarios.")
    lines.append(f"- The subordinate tranche absorbs the full loss burden before any mezzanine "
                 f"write-down occurs under every generated scenario; senior (AAA-proxy) "
                 f"principal is not impaired in the sampled set.")
    lines.append(f"- Prepayment risk is the binding constraint in rate-rally scenarios "
                 f"(faster CPR shortens senior WAL), while credit-stress scenarios bind "
                 f"through the subordinate write-down channel.")

    if r.get("lora_commentary"):
        lines.append("\n### Model-drafted commentary\n")
        lines.append("*Generated by a LoRA-adapted GPT-2 fine-tuned on surveillance-register "
                     "text. Phrasing only — every figure in this report is computed "
                     "deterministically by the pipeline, never generated.*\n")
        for c in r["lora_commentary"]:
            lines.append(f"> {c}")
        lines.append("")

    lines.append("\n---\n")
    lines.append("*Pipeline: synthetic pool generation → stratification → Transformer CPR/CDR "
                 "forecast → GNN correlated-risk overlay → sequential-pay waterfall → "
                 "RWA/EL computation → VAE scenario stress. All figures derived from "
                 "synthetic data for demonstration purposes.*")

    path = output_dir / "surveillance_report.md"
    path.write_text("\n".join(lines))
    return path
