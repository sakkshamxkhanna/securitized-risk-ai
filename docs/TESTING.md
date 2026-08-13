# Testing it yourself

Everything below runs on your machine. Nothing needs the internet except the first-time
installs (already done) and the LoRA step (downloads GPT-2 weights).

Project root: `~/Projects/securitized-risk-ai`

---

## 0. What is already running right now

The Kubernetes cluster is up from the deployment session:

```bash
kubectl -n securitized-risk get all
```

Expect: `redis` and `report-server` Deployments Running, `monthly-surveillance` CronJob
scheduled, and a completed `run-demo` Job.

Open the report in a browser:

```bash
open http://localhost:30080
```

Tabs: **report** (the full surveillance report) · **artifacts** (files the run produced) ·
**metrics** (machine-readable JSON) · **health**.

---

## 1. The fastest end-to-end check (~2 min)

```bash
cd ~/Projects/securitized-risk-ai
DISABLE_REDIS=1 SKIP_LORA=1 .venv/bin/python -m src.agents.graph
```

Watch the node-by-node log. What to look for:

| Line | What it proves |
|---|---|
| `forecast: trained (CPR R2 0.86…, CDR R2 0.97…)` | The forecaster learned both targets — no CDR collapse |
| `risk_graph: 40 cohorts, avg 1.3…x` | The GNN produced a correlated-risk multiplier |
| `stress: 5 scenarios` | The VAE generated distinct scenarios |
| `ESCALATION: …above the 2.0% desk threshold` | The conditional edge fired on a real breach |

The escalation line only appears when a scenario actually breaches. Scenarios are sampled, so
some runs stay within tolerance and the log skips straight to `report:` — that is the routing
working, not a failure.

---

## 2. Prove the tests actually test something

```bash
.venv/bin/python -m pytest tests/ -q
```

10 passing. To confirm they are not vacuous, break something on purpose:

```bash
# make losses hit the senior tranche first instead of the subordinate
sed -i '' 's/reverse_order = sorted(tr.values(), key=lambda t: -t.seniority)/reverse_order = sorted(tr.values(), key=lambda t: t.seniority)/' src/waterfall.py
.venv/bin/python -m pytest tests/ -q          # test_losses_hit_subordinate_before_senior should FAIL
git checkout src/waterfall.py                  # undo
```

If that test does not fail, the test suite is worthless — worth knowing either way.

---

## 3. Reproduce the bug that matters most

This is the one to be able to explain. Re-introduce the loss-scaling failure:

```bash
.venv/bin/python - <<'EOF'
import torch, torch.nn as nn, numpy as np
from src.models.forecasting_transformer import CPRCDRTransformer, make_training_set, _r2

X, Y = make_training_set(n_seq=2000)
Xv, Yv = make_training_set(n_seq=400, seed=1234)

for label, scaled in (("plain MSE (broken)", False), ("per-head standardised (fixed)", True)):
    torch.manual_seed(0)
    m = CPRCDRTransformer()
    flat = X.reshape(-1, X.shape[-1])
    m.feat_mean.copy_(flat.mean(0)); m.feat_std.copy_(flat.std(0).clamp(min=1e-6))
    sd = Y.std(0); opt = torch.optim.Adam(m.parameters(), lr=3e-3)
    for ep in range(150):
        opt.zero_grad()
        p = m(X)
        loss = (((p - Y) / sd) ** 2).mean() if scaled else ((p - Y) ** 2).mean()
        loss.backward(); opt.step()
    m.eval()
    with torch.no_grad(): pv = m(Xv).numpy()
    yv = Yv.numpy()
    print(f"{label:32}  CDR R2={_r2(pv[:,1], yv[:,1]):7.4f}   "
          f"CDR pred sd={pv[:,1].std():.5f} vs true {yv[:,1].std():.5f}")
EOF
```

The broken version's predicted CDR standard deviation collapses toward zero — the model is
emitting a near-constant default rate while its overall loss looks fine. That is the whole
point of reporting predicted sd against realised sd on every run.

---

## 4. Prove the Excel workbook is a model, not a screenshot

```bash
open output/surveillance_pack.xlsx
```

Then, in Excel:

1. Go to **Assumptions** → change **Loss severity (LGD)** in `B7` from `35%` to `50%`.
2. Go to **Exposure & RWA** → every **Expected loss** figure and the total have changed.
3. Go to **Loan Tape** → change any loan's FICO in column E.
4. Go to **Stratification** → the FICO bucket counts, UPB, and weighted averages have moved.

Nothing there is pasted — it is `SUMIFS`, `SUMPRODUCT`, and `INDEX`/`MATCH` over the tape.
Close without saving to reset.

To re-verify the formulas tie to the pipeline's own numbers:

```bash
SK="$HOME/Library/Application Support/Claude/local-agent-mode-sessions/skills-plugin"
# recalculate through LibreOffice, then compare every computed cell to the pipeline
soffice --headless --convert-to xlsx --outdir /tmp output/surveillance_pack.xlsx >/dev/null
```

(The full comparison script is what produced the "ALL PASS" check during the build.)

---

## 5. Open the deck

```bash
open output/surveillance_deck.pptx
```

8 slides, speaker notes on each. Slide 4 (Model-Projected Performance) and slide 8 (Method and
Limitations) are the two to be able to talk through.

---

## 6. Full Kubernetes cycle from scratch

To prove the deployment works from nothing:

```bash
kind delete cluster --name securitized-risk     # tear down
./k8s/deploy.sh                                  # rebuild everything (~3-5 min, image is cached)
kubectl -n securitized-risk create job --from=cronjob/monthly-surveillance run-$(date +%s)
kubectl -n securitized-risk logs -f -l app=surveillance --tail=100
open http://localhost:30080
```

Run a **second** job afterwards and watch the log say `forecast: cache hit` instead of
retraining — that is Redis caching across pod restarts.

---

## 7. Regenerate the Excel + deck pack

```bash
./export_pack.sh
```

---

## Shutting down / restarting

```bash
# stop (frees ~8GB RAM)
kind delete cluster --name securitized-risk
colima stop

# start again later
colima start
./k8s/deploy.sh
```

The Python pipeline (`src.agents.graph`), the tests, and `export_pack.sh` all run without
Docker or Kubernetes at all — only the cluster demo needs them.
