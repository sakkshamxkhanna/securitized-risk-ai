# Monthly Surveillance Report — Synthetic RMBS Pool 2026-1

Generated 2026-08-13 — AI-assisted surveillance pipeline

---

## 1. Pool Summary

| Metric | Value |
|---|---|
| Loan count | 2,000 |
| Current UPB | $488.9mm |
| WA coupon | 6.383% |
| WA FICO | 715 |
| WA LTV | 74.0% |
| WA DTI | 35.9% |
| WA seasoning | 24.0 mo |

## 2. Collateral Stratification

### FICO distribution

| bucket   |   loan_count | upb      |   pct_of_pool |   wa_coupon |   wa_fico |   wa_ltv |
|:---------|-------------:|:---------|--------------:|------------:|----------:|---------:|
| <620     |           79 | $19.7mm  |          4.02 |       6.366 |       602 |     71.2 |
| 620-659  |          225 | $54.2mm  |         11.09 |       6.517 |       642 |     74.1 |
| 660-699  |          461 | $110.2mm |         22.54 |       6.413 |       681 |     73.2 |
| 700-739  |          564 | $138.4mm |         28.31 |       6.351 |       719 |     73.8 |
| 740-779  |          434 | $107.8mm |         22.05 |       6.372 |       757 |     74.8 |
| 780+     |          237 | $58.5mm  |         11.98 |       6.303 |       802 |     75.1 |

### LTV distribution

| bucket   |   loan_count | upb      |   pct_of_pool |   wa_coupon |   wa_fico |   wa_ltv |
|:---------|-------------:|:---------|--------------:|------------:|----------:|---------:|
| <60      |          231 | $59.0mm  |         12.06 |       6.406 |       711 |     53.6 |
| 60-69    |          480 | $115.0mm |         23.53 |       6.427 |       712 |     65.4 |
| 70-79    |          674 | $165.6mm |         33.87 |       6.341 |       717 |     75.1 |
| 80-89    |          428 | $102.7mm |         21.01 |       6.359 |       717 |     84.3 |
| 90-99    |          187 | $46.6mm  |          9.53 |       6.446 |       722 |     94.3 |

### Top geographic concentrations

| state   |   loan_count | upb     |   pct_of_pool |
|:--------|-------------:|:--------|--------------:|
| NY      |          226 | $55.6mm |         11.38 |
| FL      |          214 | $52.4mm |         10.72 |
| WA      |          219 | $52.3mm |         10.69 |
| GA      |          206 | $51.0mm |         10.42 |
| TX      |          210 | $50.2mm |         10.26 |

## 3. Model-Projected Performance (Base Case)

The temporal-attention forecaster projects an average **CPR of 9.85%** and **CDR of 1.43%** over the 36-month horizon, inclusive of the correlated-risk overlay (**1.371x** average cohort multiplier from the GNN).

Cumulative base-case collateral loss: **$6.2mm**.

### Highest-risk cohorts (GNN-adjusted)

| originator          | state   | upb     |   gnn_risk_multiplier |   gnn_adjusted_cdr |
|:--------------------|:--------|:--------|----------------------:|-------------------:|
| Meridian Home Loans | CA      | $10.5mm |                 1.634 |             0.0174 |
| Meridian Home Loans | NY      | $11.7mm |                 1.633 |             0.0156 |
| Meridian Home Loans | WA      | $11.7mm |                 1.632 |             0.0148 |
| Meridian Home Loans | GA      | $13.8mm |                 1.626 |             0.0156 |
| Meridian Home Loans | AZ      | $11.2mm |                 1.62  |             0.0162 |

Cohorts are scored on a graph linking originator and state, so a deterioration signal on one originator propagates to its other state cohorts rather than being treated as an isolated event.


## 4. Tranche Cashflows & Exposure

| tranche         | total_principal   | total_interest   | final_balance   |
|:----------------|:------------------|:-----------------|:----------------|
| A (Senior)      | $152.3mm          | $49.9mm          | $229.0mm        |
| B (Subordinate) | $0                | $6.8mm           | $32.9mm         |
| M (Mezz)        | $0                | $13.1mm          | $68.4mm         |

### Exposure / RWA / expected loss

| tranche         | proxy_rating   | ead      |       pd |   lgd | expected_loss   |   risk_weight | rwa     |
|:----------------|:---------------|:---------|---------:|------:|:----------------|--------------:|:--------|
| A (Senior)      | AAA            | $229.0mm | 0.00215  |  0.35 | $172,316        |           0.2 | $45.8mm |
| B (Subordinate) | BB             | $32.9mm  | 0.035839 |  0.35 | $413,245        |           2.5 | $82.4mm |
| M (Mezz)        | BBB            | $68.4mm  | 0.012902 |  0.35 | $309,072        |           1   | $68.4mm |

Total RWA: **$196.6mm** | Total expected loss: **$894,633**


## 5. Scenario Stress Testing

Scenarios are sampled from the latent space of a VAE trained on macro regime paths — these are generated, not hand-specified.

| scenario   | label                                            |   avg_cpr_pct |   avg_cdr_pct | cumulative_loss   | sub_tranche_writedown   |
|:-----------|:-------------------------------------------------|--------------:|--------------:|:------------------|:------------------------|
| S1         | Credit stress (rising unemployment, HPI decline) |         11.31 |          2.91 | $12.2mm           | $12.2mm                 |
| S2         | Rate rally (elevated prepayment incentive)       |         15.75 |          1.46 | $5.8mm            | $5.8mm                  |
| S3         | Base-like                                        |          8.44 |          1.42 | $6.3mm            | $6.3mm                  |
| S4         | Base-like                                        |         11.18 |          1.52 | $6.5mm            | $6.5mm                  |
| S5         | Rate rally (elevated prepayment incentive)       |         12.32 |          1.42 | $6.0mm            | $6.0mm                  |

**Most adverse scenario:** S1 — *Credit stress (rising unemployment, HPI decline)* — cumulative loss $12.2mm, subordinate write-down $12.2mm.

**Most benign scenario:** S2 — *Rate rally (elevated prepayment incentive)* — cumulative loss $5.8mm.


## 5a. Escalations

- **ESCALATION: scenario S1 (Credit stress (rising unemployment, HPI decline)) projects cumulative loss of 2.49% of UPB, above the 2.0% desk threshold.**


## 5b. Model Validation

Holdout performance of the CPR/CDR forecaster (400 unseen sequences):

| Metric | CPR | CDR |
|---|---|---|
| R² | 0.8642 | 0.9746 |
| MAE | 0.00453 | 0.00037 |

Predicted CDR standard deviation 0.00369 against realised 0.00374 — the model tracks credit dispersion rather than collapsing to the unconditional mean.


## 6. Analyst Commentary

- Largest state concentration is **NY** at **11.4%** of pool UPB; regional HPI sensitivity is the dominant driver of tail loss in the stressed scenarios.
- The subordinate tranche absorbs the full loss burden before any mezzanine write-down occurs under every generated scenario; senior (AAA-proxy) principal is not impaired in the sampled set.
- Prepayment risk is the binding constraint in rate-rally scenarios (faster CPR shortens senior WAL), while credit-stress scenarios bind through the subordinate write-down channel.

---

*Pipeline: synthetic pool generation → stratification → Transformer CPR/CDR forecast → GNN correlated-risk overlay → sequential-pay waterfall → RWA/EL computation → VAE scenario stress. All figures derived from synthetic data for demonstration purposes.*