"""Report viewer — serves generated surveillance artifacts over HTTP.

Runs as a long-lived Deployment alongside the batch Job/CronJob, reading
the same PersistentVolumeClaim the pipeline writes to, so the desk can
read the latest surveillance report without shelling into a pod.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, PlainTextResponse

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
app = FastAPI(title="Securitized Products Surveillance")

PAGE = """<!doctype html>
<meta charset="utf-8"><title>{title}</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font: 15px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         max-width: 1000px; margin: 2rem auto; padding: 0 1.25rem; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; font-size: 13px; }}
  th, td {{ border: 1px solid #8884; padding: 6px 10px; text-align: left; }}
  th {{ background: #8881; }}
  code, pre {{ background: #8881; padding: 2px 5px; border-radius: 4px; }}
  blockquote {{ border-left: 3px solid #8886; margin-left: 0; padding-left: 1rem; opacity: .85; }}
  a {{ color: inherit; }}
  .nav a {{ margin-right: 1rem; }}
</style>
<div class="nav">{nav}</div>
<hr>
{body}
"""


def _md_to_html(md: str) -> str:
    """Minimal markdown renderer covering what the report emits: headings,
    tables, bold, blockquotes, list items, rules."""
    out, in_table = [], False
    for raw in md.splitlines():
        line = raw.rstrip()
        if line.startswith("|") and line.endswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(set(c) <= set("-: ") and c for c in cells):
                continue  # separator row
            tag = "th" if not in_table else "td"
            if not in_table:
                out.append("<table>")
                in_table = True
            out.append("<tr>" + "".join(f"<{tag}>{c}</{tag}>" for c in cells) + "</tr>")
            continue
        if in_table:
            out.append("</table>")
            in_table = False

        if line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            out.append(f"<h{level}>{line.lstrip('# ')}</h{level}>")
        elif line.startswith(">"):
            out.append(f"<blockquote>{line.lstrip('> ')}</blockquote>")
        elif line.startswith("- "):
            out.append(f"<li>{line[2:]}</li>")
        elif line.startswith("---"):
            out.append("<hr>")
        elif line:
            out.append(f"<p>{line}</p>")
    if in_table:
        out.append("</table>")

    html = "\n".join(out)
    while html.count("**") >= 2:
        html = html.replace("**", "<strong>", 1).replace("**", "</strong>", 1)
    while html.count("*") >= 2:
        html = html.replace("*", "<em>", 1).replace("*", "</em>", 1)
    return html


def _nav() -> str:
    return ('<a href="/">report</a><a href="/artifacts">artifacts</a>'
            '<a href="/metrics">metrics</a><a href="/healthz">health</a>')


@app.get("/healthz", response_class=PlainTextResponse)
def healthz() -> str:
    return "ok"


@app.get("/readyz", response_class=PlainTextResponse)
def readyz() -> str:
    return "ok" if OUTPUT_DIR.exists() else "output dir missing"


@app.get("/metrics")
def metrics() -> dict:
    path = OUTPUT_DIR / "run_metrics.json"
    if not path.exists():
        return {"status": "no run yet — trigger the surveillance Job"}
    return json.loads(path.read_text())


@app.get("/artifacts", response_class=HTMLResponse)
def artifacts() -> str:
    if not OUTPUT_DIR.exists():
        body = "<p>No artifacts yet.</p>"
    else:
        files = sorted(p for p in OUTPUT_DIR.iterdir() if p.is_file())
        rows = "".join(
            f"<tr><td>{p.name}</td><td>{p.stat().st_size:,} bytes</td></tr>" for p in files)
        body = (f"<h1>Artifacts</h1><table><tr><th>file</th><th>size</th></tr>{rows}</table>"
                if files else "<p>No artifacts yet — trigger the surveillance Job.</p>")
    return PAGE.format(title="Artifacts", nav=_nav(), body=body)


@app.get("/", response_class=HTMLResponse)
def report() -> str:
    path = OUTPUT_DIR / "surveillance_report.md"
    if not path.exists():
        body = ("<h1>No surveillance report yet</h1>"
                "<p>Trigger a run: <code>kubectl create job --from=cronjob/monthly-surveillance "
                "run-now -n securitized-risk</code></p>")
    else:
        body = _md_to_html(path.read_text())
    return PAGE.format(title="Surveillance Report", nav=_nav(), body=body)
