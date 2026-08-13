# Screen Recording Guide

## Tooling (all free)

| Tool | Use | Install |
|---|---|---|
| **OBS Studio** | Main recording — terminal + browser + mic narration | `brew install --cask obs` |
| macOS built-in | Zero-install fallback, no narration composition | `Cmd + Shift + 5` |
| **asciinema** | Terminal-only, tiny shareable files, copy-paste-able text | `brew install asciinema` |

**Recommendation:** OBS for the portfolio video. Use asciinema separately if you want an
embeddable terminal cast in the README.

### OBS one-time setup

1. **Settings → Output → Recording:** format `MP4`, encoder `Apple VT H264 Hardware`.
2. **Settings → Video:** Base and Output resolution `1920x1080`, FPS `30`.
3. **Sources → +  → macOS Screen Capture** (grant Screen Recording permission when prompted).
4. **Sources → + → Audio Input Capture** for mic narration.
5. Increase terminal font size to ~16pt before recording — 1080p compresses small text badly.

## What to record (target: 4–6 minutes)

Keep it tight. A recruiter watches the first 45 seconds; an engineer watches the middle.

### 0:00–0:30 — Frame the problem
Say what the system does before showing any code:

> "A securitized products desk produces a monthly surveillance report on its collateral
> pools — stratification tapes, projected cashflows, tranche-level exposure and RWA. This
> pipeline generates that report end to end, with the forecasting, correlated-risk, and
> scenario-generation steps handled by models rather than by hand."

### 0:30–1:15 — Architecture
Show `README.md` and walk the pipeline diagram once:
`ingest → stratify → forecast (Transformer) → risk_graph (GNN) → waterfall → exposure → stress (VAE) → escalate? → narrative (LoRA) → report`

Name why each model is there — the GNN captures correlated default that loan-level models
miss, the VAE generates scenarios nobody hand-wrote. **Do not** list the architectures
without the reason; the reason is the whole point.

### 1:15–2:15 — Deploy
```bash
./k8s/deploy.sh
```
While it runs, narrate what's being created: a namespace, Redis with health probes, a
PersistentVolumeClaim shared between the batch job and the report server, a CronJob on the
desk's monthly cycle, and the viewer Deployment.

Then show the cluster state:
```bash
kubectl -n securitized-risk get all
```

### 2:15–3:30 — Trigger a run
```bash
kubectl -n securitized-risk create job --from=cronjob/monthly-surveillance run-demo
kubectl -n securitized-risk logs -f -l app=surveillance --tail=100
```
Let the log stream play. Call out the escalation line when it appears — that's the
conditional edge in the LangGraph state machine firing on a real threshold breach.

### 3:30–4:30 — Show the output
Open `http://localhost:30080` in the browser. Scroll the report: pool summary,
stratification tapes, GNN-adjusted cohort risk, tranche waterfall, RWA/EL, scenario stress.

Pause on **Section 5b, Model Validation** and say the honest version:

> "The forecaster reports holdout R² on every run — 0.86 for prepayment, 0.97 for default.
> That section exists because this model failed silently at first: CPR variance is about
> 100× CDR variance, so under a plain MSE the model minimised loss by predicting a constant
> default rate. It scored well and was economically useless. Standardising the targets
> per-head fixed it — R² went from 0.10 to 0.97."

**This is the most valuable 30 seconds in the video.** Anyone can show a working pipeline;
showing that you caught a silent failure is what separates you.

### 4:30–5:00 — Tests and close
```bash
pytest tests/ -q
```
Note what they assert: the senior tranche is never written down while subordinate balance
remains, principal never exceeds original tranche balance, higher CDR strictly increases
loss. Close on the scope note — synthetic data, simplified RWA proxy — stated plainly.

## Recording discipline

- **Pre-pull images before recording.** `docker pull redis:7-alpine` and run `deploy.sh` once
  beforehand so the take isn't 4 minutes of image pulls.
- **Clear the terminal between sections** (`Cmd+K`) so each step reads cleanly.
- **Don't edit out the escalation or the validation section** — those are the substance.
- If you narrate the loss-scaling bug, be ready to explain it in interview. It's genuinely
  yours; you'll be asked.
- Keep the raw take. A 6-minute unedited screen recording reads as more credible than a
  heavily cut 90-second montage.

## Publishing

Upload unlisted to YouTube and link it from the README, or commit the `.mp4` with Git LFS.
Unlisted YouTube is simpler and doesn't bloat the repo.
