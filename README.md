# Securitized Products AI Surveillance Pipeline

An end-to-end system that produces the monthly surveillance report a securitized-products
desk analyst would otherwise assemble by hand: loan-level collateral tape → stratification →
model-projected cashflows → tranche waterfall → exposure/RWA/expected loss → generated
scenario stress → written commentary.

The point of the project is that each ML component is solving a problem the desk actually
has, rather than being attached for its own sake.

## Pipeline

```
ingest → stratify → forecast (Transformer) → risk_graph (GNN) → waterfall
       → exposure (RWA/EL) → stress (VAE scenarios) → [escalate?] → narrative (LoRA) → report
```

Orchestrated as a LangGraph state machine (`src/agents/graph.py`) so each stage is
independently inspectable and cacheable, with a conditional edge that routes to an
escalation node when projected loss breaches the desk threshold (default 2% of UPB).

## Components

| Module | What it does |
|---|---|
| `pool_generator.py` | Synthetic RMBS loan-level pool (FICO, LTV, DTI, coupon, seasoning, geography, originator/servicer) |
| `stratification.py` | Stratification tapes by FICO / LTV / geography, balance-weighted |
| `models/forecasting_transformer.py` | Temporal-attention Transformer predicting CPR (prepayment) and CDR (default) from a macro path |
| `models/gnn_risk.py` | 2-layer GCN over an originator × state cohort graph, producing a correlated-risk multiplier |
| `models/scenario_vae.py` | VAE over macro regime paths; sampling the latent space generates stress scenarios |
| `cashflow_engine.py` | Projects monthly pool cashflows from CPR/CDR (SMM/MDR conversion, severity, recoveries) |
| `waterfall.py` | Sequential-pay tranche waterfall: pro-rata interest, sequential principal, reverse-sequential loss |
| `exposure.py` | Per-tranche EAD, PD, LGD, expected loss and standardized-approach RWA |
| `models/lora_narrative.py` | Rank-8 LoRA adapters on GPT-2, fine-tuned on surveillance-register text |
| `cache.py` | Redis-backed stage caching with in-memory fallback |

## Why a GNN

A per-loan hazard model treats every loan as independent. In reality loans sharing an
originator (common underwriting standards) or a state (regional HPI and employment shocks)
default in a correlated way — the tail risk that flat models systematically understate. The
GCN propagates risk across a cohort graph so deterioration at one originator lifts its other
state cohorts rather than being treated as an isolated event.

## Why a VAE for scenarios

Hand-specified up/base/down cases only test the scenarios you already thought of. Sampling
the latent space of a VAE trained on macro regime paths produces plausible combinations that
were never explicitly written down, which is where structural tail risk tends to hide.

## Model validation

The forecaster reports holdout metrics on 400 unseen sequences on every run:

```
CPR R² ≈ 0.86   CDR R² ≈ 0.97
CDR predicted sd ≈ 0.0036 vs realised 0.0037
```

The sd comparison is a deliberate guard against a failure this project hit during
development: CPR variance is roughly 100× CDR variance, so under a plain MSE the CDR head
contributes almost nothing to the loss and the model minimises error by emitting a constant
CDR — scoring well while being economically useless. Targets are standardised per-head so
both tasks produce comparable gradient signal, and inputs are standardised because
`hpi_growth` (~1e-3) and `unemployment` (~5.0) otherwise differ by three orders of magnitude
and the small-magnitude credit drivers are never recovered. Before the fix, holdout R² was
0.04/0.10 and every generated scenario returned an identical CDR.

## Honest scope notes

- **All data is synthetic.** There is no licensed loan tape here. The DGP is explicit in
  `pool_generator.py` and `forecasting_transformer.true_hazards`, so reported R² measures
  recovery of a known generating process, not real-world predictive accuracy.
- **The LoRA corpus is ~40 sentences.** That is enough to demonstrate parameter-efficient
  fine-tuning end-to-end (0.24% of parameters trainable) and to shift GPT-2 into desk
  register, but the model partially memorises the corpus. It is a style layer, not a
  research contribution.
- **Every number in the report is computed deterministically.** The language model controls
  phrasing only and never produces a figure.
- **RWA is a simplified standardized-approach proxy** using rating-band risk weights, not a
  full SEC-SA / SEC-IRBA implementation.

## Running it

```bash
python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m src.agents.graph      # full LangGraph pipeline
.venv/bin/python -m src.pipeline          # linear script version
.venv/bin/python -m pytest tests/ -q      # structural invariant tests
```

With Docker + Redis:

```bash
docker compose -f docker/docker-compose.yml up --build
```

Set `SKIP_LORA=1` to skip narrative generation, `DISABLE_REDIS=1` to force the in-memory cache.

## Kubernetes deployment

```bash
./k8s/deploy.sh
```

Creates a kind cluster, builds and loads the image, and applies the manifests. Requires
`colima` (or any Docker runtime), `kind`, and `kubectl` — all free and open-source.

### Workload modelling

Surveillance is a **batch** workload on a monthly remittance cycle, so it is modelled as a
`CronJob` rather than a long-running Deployment:

| Manifest | Resource | Purpose |
|---|---|---|
| `00-namespace.yaml` | Namespace | Isolation |
| `01-config.yaml` | ConfigMap + PVC | Runtime config; 1Gi volume shared between writer and reader |
| `02-redis.yaml` | Deployment + Service | Model/artifact cache, with liveness and readiness probes |
| `03-surveillance-job.yaml` | Job | Ad-hoc rerun (e.g. servicer restates a tape) |
| `04-surveillance-cronjob.yaml` | CronJob | Monthly cycle, `0 6 26 * *` Europe/London, `concurrencyPolicy: Forbid` |
| `05-report-server.yaml` | Deployment + NodePort | FastAPI report viewer on the shared PVC |

The schedule follows the 25th-of-month remittance cycle and runs on EMEA hours to match the
desk. `concurrencyPolicy: Forbid` prevents overlapping surveillance cycles. An init container
gates each run on Redis readiness — without it the job races the Redis rollout on a cold
cluster and silently degrades to the in-process cache.

### Operating it

```bash
# trigger an ad-hoc run
kubectl -n securitized-risk create job --from=cronjob/monthly-surveillance run-now

# follow it
kubectl -n securitized-risk logs -f -l app=surveillance --tail=100

# read the report / machine-readable metrics
open http://localhost:30080
curl -s http://localhost:30080/metrics | jq
```

The pipeline writes `run_metrics.json` alongside the report; `/metrics` serves it for
downstream monitoring. Redis caching is visible across runs — the second job logs
`forecast: cache hit` instead of retraining.

## Tests

`tests/test_pipeline.py` asserts the structural invariants the mechanics must satisfy —
principal never exceeds original tranche balance, the senior class is never written down
while subordinate balance remains, balances never go negative, stratification percentages
reconcile to 100%, and higher CDR strictly increases realised loss.

## Outputs

Written to `output/`: `loan_tape.csv`, `strat_{fico,ltv,geography}.csv`,
`cohort_risk_gnn.csv`, `pool_cashflows_base.csv`, `waterfall_schedule_base.csv`,
`exposure_rwa.csv`, `scenario_stress.csv`, `run_metrics.json`, and
`surveillance_report.md`.
