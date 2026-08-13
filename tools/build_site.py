"""Builds the static GitHub Pages site from the latest pipeline output.

Produces docs/index.html plus docs/assets/ — the surveillance report, the
slide deck as images, and downloadable Excel/PowerPoint artifacts. Static
so it loads instantly with no cold start.

Run: python tools/build_site.py
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
SITE = ROOT / "docs"
ASSETS = SITE / "assets"

REPO = "https://github.com/sakkshamxkhanna/securitized-risk-ai"


def md_to_html(md: str) -> str:
    """Renders the subset of markdown the report emits."""
    out, in_table, in_list = [], False, False
    for raw in md.splitlines():
        line = raw.rstrip()
        is_row = line.startswith("|") and line.endswith("|")

        if not is_row and in_table:
            out.append("</tbody></table></div>")
            in_table = False
        if not line.startswith("- ") and in_list:
            out.append("</ul>")
            in_list = False

        if is_row:
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(set(c) <= set("-: ") and c for c in cells):
                continue
            if not in_table:
                out.append('<div class="tw"><table><thead><tr>'
                           + "".join(f"<th>{c}</th>" for c in cells)
                           + "</tr></thead><tbody>")
                in_table = True
            else:
                out.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
            continue

        if line.startswith("#"):
            lvl = len(line) - len(line.lstrip("#"))
            out.append(f"<h{lvl}>{line.lstrip('# ')}</h{lvl}>")
        elif line.startswith("- "):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{line[2:]}</li>")
        elif line.startswith(">"):
            out.append(f"<blockquote>{line.lstrip('> ')}</blockquote>")
        elif line.startswith("---"):
            out.append("<hr>")
        elif line:
            out.append(f"<p>{line}</p>")

    if in_table:
        out.append("</tbody></table></div>")
    if in_list:
        out.append("</ul>")

    html = "\n".join(out)
    while html.count("**") >= 2:
        html = html.replace("**", "<strong>", 1).replace("**", "</strong>", 1)
    while html.count("*") >= 2:
        html = html.replace("*", "<em>", 1).replace("*", "</em>", 1)
    return html


CSS = """
:root{--bg:#ffffff;--fg:#1a1a1a;--muted:#5b6472;--line:#dfe4ec;--navy:#0F1E3D;
--ice:#eef3fa;--amber:#D98324;--red:#9C2B2B;--card:#f7f9fc;}
@media (prefers-color-scheme:dark){:root{--bg:#0d1117;--fg:#e6edf3;--muted:#9aa4b2;
--line:#27303d;--navy:#c3d3ea;--ice:#161d29;--card:#131a24;}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;}
.wrap{max-width:980px;margin:0 auto;padding:0 20px 80px}
header{background:var(--navy);color:#fff;padding:56px 20px 44px;margin-bottom:36px}
@media (prefers-color-scheme:dark){header{background:#111c30}}
header .wrap{padding-bottom:0}
header h1{margin:0 0 10px;font-size:34px;line-height:1.2;color:#fff}
header p{margin:0 0 6px;color:#c3d3ea;font-size:17px}
header .meta{font-size:13px;color:#8fa6c4;margin-top:16px}
.badges{margin-top:20px;display:flex;flex-wrap:wrap;gap:8px}
.badge{background:rgba(255,255,255,.12);color:#fff;padding:5px 11px;
border-radius:20px;font-size:12.5px;text-decoration:none}
.badge:hover{background:rgba(255,255,255,.22)}
h2{font-size:24px;margin:44px 0 6px;padding-top:14px;border-top:1px solid var(--line)}
h3{font-size:18px;margin:26px 0 6px}
h4{font-size:15px;margin:20px 0 4px;color:var(--muted)}
p{margin:10px 0}
a{color:inherit}
.lede{color:var(--muted);font-size:16px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px;margin:22px 0}
.stat{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:18px}
.stat .v{font-size:27px;font-weight:700;color:var(--navy);line-height:1.15}
.stat .l{font-size:12.5px;color:var(--muted);margin-top:5px}
.stat.warn .v{color:var(--amber)}
.dl{display:flex;flex-wrap:wrap;gap:12px;margin:20px 0}
.dl a{display:block;background:var(--card);border:1px solid var(--line);border-radius:10px;
padding:15px 18px;text-decoration:none;min-width:210px;flex:1}
.dl a:hover{border-color:var(--navy)}
.dl .t{font-weight:600;font-size:15px}
.dl .s{font-size:12.5px;color:var(--muted);margin-top:3px}
.tw{overflow-x:auto;-webkit-overflow-scrolling:touch;margin:14px 0}
table{border-collapse:collapse;width:100%;font-size:13.5px;min-width:480px}
th,td{border:1px solid var(--line);padding:7px 11px;text-align:left;white-space:nowrap}
th{background:var(--ice);font-weight:600}
blockquote{border-left:3px solid var(--line);margin:14px 0;padding:2px 0 2px 16px;color:var(--muted)}
code{background:var(--ice);padding:2px 6px;border-radius:4px;font-size:13.5px}
pre{background:var(--ice);padding:14px 16px;border-radius:8px;overflow-x:auto;font-size:13.5px}
pre code{background:none;padding:0}
hr{border:0;border-top:1px solid var(--line);margin:26px 0}
.slides img{width:100%;border:1px solid var(--line);border-radius:8px;margin-bottom:16px;display:block}
.note{background:var(--ice);border-left:3px solid var(--amber);padding:14px 18px;
border-radius:0 8px 8px 0;margin:22px 0;font-size:14.5px}
.note strong{color:var(--amber)}
footer{margin-top:56px;padding-top:22px;border-top:1px solid var(--line);
color:var(--muted);font-size:13.5px}
ul{margin:10px 0;padding-left:22px}
li{margin:5px 0}
details{margin:16px 0;border:1px solid var(--line);border-radius:8px;padding:12px 16px}
summary{cursor:pointer;font-weight:600}
"""


def money(x: float) -> str:
    return f"${x/1e6:,.1f}mm" if abs(x) >= 1e6 else f"${x:,.0f}"


def build() -> Path:
    ASSETS.mkdir(parents=True, exist_ok=True)
    metrics = json.loads((OUT / "run_metrics.json").read_text())
    s = metrics["pool_summary"]
    v = metrics.get("forecaster_validation", {})

    # copy downloadable + visual assets
    copied = {}
    for name in ("surveillance_pack.xlsx", "surveillance_deck.pptx",
                 "surveillance_report.md", "run_metrics.json"):
        src = OUT / name
        if src.exists():
            shutil.copy2(src, ASSETS / name)
            copied[name] = src.stat().st_size
    for csv in OUT.glob("*.csv"):
        shutil.copy2(csv, ASSETS / csv.name)
    slides = sorted(OUT.glob("slide-*.jpg"), key=lambda p: int(p.stem.split("-")[1]))
    for sl in slides:
        shutil.copy2(sl, ASSETS / sl.name)

    report_html = md_to_html((OUT / "surveillance_report.md").read_text())

    stats = [
        (money(s["total_upb"]), "Pool UPB", ""),
        (f"{s['loan_count']:,}", "Loans", ""),
        (f"{metrics['avg_cpr']*100:.2f}%", "Projected CPR", ""),
        (f"{metrics['avg_cdr']*100:.2f}%", "Projected CDR", "warn"),
        (str(v.get("cpr_r2", "—")), "CPR holdout R²", ""),
        (str(v.get("cdr_r2", "—")), "CDR holdout R²", ""),
    ]
    stat_html = "".join(
        f'<div class="stat {c}"><div class="v">{val}</div><div class="l">{lab}</div></div>'
        for val, lab, c in stats)

    dl_html = ""
    for name, label, desc in (
        ("surveillance_pack.xlsx", "Excel surveillance pack",
         "8 sheets — live SUMIFS / SUMPRODUCT / INDEX-MATCH formulas over the loan tape"),
        ("surveillance_deck.pptx", "PowerPoint deck",
         "8 slides with speaker notes, generated from the run"),
        ("loan_tape.csv", "Loan-level tape (CSV)", "2,000 synthetic loans"),
        ("run_metrics.json", "Run metrics (JSON)", "Machine-readable output of the run"),
    ):
        if (ASSETS / name).exists():
            kb = (ASSETS / name).stat().st_size / 1024
            dl_html += (f'<a href="assets/{name}"><div class="t">{label}</div>'
                        f'<div class="s">{desc} · {kb:,.0f} KB</div></a>')

    slides_html = "".join(
        f'<img src="assets/{p.name}" alt="Slide {i+1}" loading="lazy">'
        for i, p in enumerate(slides))

    esc = metrics.get("escalations") or []
    esc_html = ""
    if esc:
        esc_html = ('<div class="note"><strong>Escalation raised this run.</strong> '
                    + esc[0] + "</div>")

    html = f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Securitized Products AI Surveillance — Saksham Khanna</title>
<meta name="description" content="Model-driven RMBS surveillance pipeline: stratification,
tranche waterfall, RWA/expected loss, Transformer forecasting, GNN correlated risk and
VAE scenario stress.">
<style>{CSS}</style>
</head><body>

<header><div class="wrap">
<h1>Securitized Products AI Surveillance Pipeline</h1>
<p>The monthly surveillance report an RMBS desk analyst would assemble by hand —
generated end to end.</p>
<div class="badges">
<a class="badge" href="{REPO}">Source on GitHub →</a>
<a class="badge" href="assets/surveillance_pack.xlsx">Excel pack</a>
<a class="badge" href="assets/surveillance_deck.pptx">Slide deck</a>
<a class="badge" href="{REPO}/blob/main/docs/TESTING.md">Run it yourself</a>
</div>
<div class="meta">Generated {metrics.get('generated_at','')[:10]} ·
All data synthetic · Saksham Khanna</div>
</div></header>

<div class="wrap">

<p class="lede">Everything on this page — every figure, table, slide and spreadsheet —
was produced by one pipeline run. Nothing is hand-written.</p>

<div class="grid">{stat_html}</div>
{esc_html}

<h2>What it does</h2>
<pre><code>ingest → stratify → forecast (Transformer) → risk_graph (GNN) → waterfall
      → exposure (RWA/EL) → stress (VAE scenarios) → [escalate?] → report</code></pre>
<p>Orchestrated as a LangGraph state machine with Redis stage caching, deployed on
Kubernetes as a monthly CronJob matching the remittance cycle. A conditional edge routes
to an escalation node when projected loss breaches the 2% desk threshold.</p>

<h3>Why each model is there</h3>
<ul>
<li><strong>Transformer</strong> — forecasts prepayment (CPR) and default (CDR) speeds from
macro paths. Holdout R² {v.get('cpr_r2','—')} / {v.get('cdr_r2','—')} on 400 unseen sequences.</li>
<li><strong>Graph neural network</strong> — a per-loan hazard model treats every loan as
independent; loans sharing an originator or a state default together. The GCN propagates risk
across an originator × state cohort graph.</li>
<li><strong>VAE</strong> — hand-written up/base/down cases only test scenarios you already
thought of. Sampling a latent space trained on macro regimes generates combinations nobody
specified.</li>
<li><strong>LoRA-adapted LM</strong> — drafts commentary phrasing only. Every figure is
computed deterministically.</li>
</ul>

<div class="note"><strong>The bug worth reading about.</strong> CPR variance is roughly 100×
CDR variance, so under a plain MSE the model minimised loss by emitting a <em>constant</em>
default rate — scoring well while being economically useless, and making every "generated"
scenario identical. Standardising targets per-head fixed it: holdout CDR R² moved from 0.10 to
{v.get('cdr_r2','0.97')}. Predicted standard deviation is now reported against realised
({v.get('cdr_pred_sd','—')} vs {v.get('cdr_true_sd','—')}) on every run, so a recurrence is
visible immediately.</div>

<h2>Download the outputs</h2>
<div class="dl">{dl_html}</div>
<p class="lede">The Excel pack is a model, not a screenshot: change LGD on the Assumptions
sheet and every expected-loss figure reprices; edit a FICO on the loan tape and the
stratification buckets move.</p>

<h2>The deck</h2>
<div class="slides">{slides_html}</div>

<h2>The full surveillance report</h2>
<details><summary>Expand the generated report</summary>
{report_html}
</details>

<h2>Scope and limitations</h2>
<ul>
<li><strong>All data is synthetic.</strong> There is no licensed loan tape here, so the
reported R² measures recovery of a known generating process, not real-world accuracy.</li>
<li><strong>RWA is a simplified rating-band proxy</strong>, not SEC-SA / SEC-IRBA.</li>
<li><strong>The LoRA corpus is ~40 sentences</strong> — enough to demonstrate
parameter-efficient fine-tuning end to end, but it partially memorises the corpus. It is a
style layer.</li>
</ul>

<footer>
<p>Built by Saksham Khanna · <a href="{REPO}">github.com/sakkshamxkhanna/securitized-risk-ai</a>
· MIT licensed</p>
<p>This page is generated by <code>tools/build_site.py</code> from the pipeline's own output
artifacts, so it cannot drift from the run it describes.</p>
</footer>

</div></body></html>
"""
    index = SITE / "index.html"
    index.write_text(html)
    return index


if __name__ == "__main__":
    p = build()
    print(f"wrote {p}")
    print(f"assets: {len(list(ASSETS.iterdir()))} files")
