# Monthly Surveillance Report — Synthetic RMBS Pool 2026-1

*Generated 2026-08-13 — AI-assisted surveillance pipeline*

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

| bucket   |   loan_count |         upb |   pct_of_pool |   wa_coupon |   wa_fico |   wa_ltv |
|:---------|-------------:|------------:|--------------:|------------:|----------:|---------:|
| <620     |           79 | 1.96683e+07 |          4.02 |       6.366 |       602 |     71.2 |
| 620-659  |          225 | 5.4224e+07  |         11.09 |       6.517 |       642 |     74.1 |
| 660-699  |          461 | 1.10207e+08 |         22.54 |       6.413 |       681 |     73.2 |
| 700-739  |          564 | 1.38421e+08 |         28.31 |       6.351 |       719 |     73.8 |
| 740-779  |          434 | 1.07816e+08 |         22.05 |       6.372 |       757 |     74.8 |
| 780+     |          237 | 5.85489e+07 |         11.98 |       6.303 |       802 |     75.1 |

### LTV distribution

| bucket   |   loan_count |         upb |   pct_of_pool |   wa_coupon |   wa_fico |   wa_ltv |
|:---------|-------------:|------------:|--------------:|------------:|----------:|---------:|
| <60      |          231 | 5.89623e+07 |         12.06 |       6.406 |       711 |     53.6 |
| 60-69    |          480 | 1.1503e+08  |         23.53 |       6.427 |       712 |     65.4 |
| 70-79    |          674 | 1.65598e+08 |         33.87 |       6.341 |       717 |     75.1 |
| 80-89    |          428 | 1.02717e+08 |         21.01 |       6.359 |       717 |     84.3 |
| 90-99    |          187 | 4.65774e+07 |          9.53 |       6.446 |       722 |     94.3 |

### Top geographic concentrations

| state   |   loan_count |         upb |   pct_of_pool |
|:--------|-------------:|------------:|--------------:|
| NY      |          226 | 5.56227e+07 |         11.38 |
| FL      |          214 | 5.23906e+07 |         10.72 |
| WA      |          219 | 5.22843e+07 |         10.69 |
| GA      |          206 | 5.09593e+07 |         10.42 |
| TX      |          210 | 5.0182e+07  |         10.26 |

## 3. Model-Projected Performance (Base Case)

The temporal-attention forecaster projects an average **CPR of 9.79%** and **CDR of 1.36%** over the 36-month horizon, inclusive of the correlated-risk overlay (**1.389x** average cohort multiplier from the GNN).

Cumulative base-case collateral loss: **$5.9mm**.

### Highest-risk cohorts (GNN-adjusted)

| originator          | state   |         upb |   gnn_risk_multiplier |   gnn_adjusted_cdr |
|:--------------------|:--------|------------:|----------------------:|-------------------:|
| Meridian Home Loans | FL      | 1.38251e+07 |                 1.83  |             0.0179 |
| Meridian Home Loans | WA      | 1.17486e+07 |                 1.829 |             0.0166 |
| Meridian Home Loans | GA      | 1.38326e+07 |                 1.824 |             0.0175 |
| Meridian Home Loans | TX      | 1.11665e+07 |                 1.824 |             0.0183 |
| Meridian Home Loans | AZ      | 1.11733e+07 |                 1.816 |             0.0181 |

Cohorts are scored on a graph linking originator and state, so a deterioration signal on one originator propagates to its other state cohorts rather than being treated as an isolated event.


## 4. Tranche Cashflows & Exposure

| tranche         |   total_principal |   total_interest |   final_balance |
|:----------------|------------------:|-----------------:|----------------:|
| A (Senior)      |       1.51147e+08 |      5.00453e+07 |     2.30183e+08 |
| B (Subordinate) |       0           |      6.88008e+06 |     3.32588e+07 |
| M (Mezz)        |       0           |      1.31115e+07 |     6.84439e+07 |

### Exposure / RWA / expected loss

| tranche         | proxy_rating   |         ead |     pd |   lgd |   expected_loss |   risk_weight |         rwa |
|:----------------|:---------------|------------:|-------:|------:|----------------:|--------------:|------------:|
| A (Senior)      | AAA            | 2.30183e+08 | 0.002  |  0.35 |          164112 |           0.2 | 4.60366e+07 |
| B (Subordinate) | BB             | 3.32588e+07 | 0.034  |  0.35 |          395204 |           2.5 | 8.31471e+07 |
| M (Mezz)        | BBB            | 6.84439e+07 | 0.0122 |  0.35 |          292787 |           1   | 6.84439e+07 |

Total RWA: **$197.6mm** | Total expected loss: **$852,104**


## 5. Scenario Stress Testing

Scenarios are sampled from the latent space of a VAE trained on macro regime paths — these are generated, not hand-specified.

| scenario   | label                                            |   avg_cpr_pct |   avg_cdr_pct |   cumulative_loss |   sub_tranche_writedown |
|:-----------|:-------------------------------------------------|--------------:|--------------:|------------------:|------------------------:|
| S1         | Credit stress (rising unemployment, HPI decline) |         12.52 |          3.86 |       1.55961e+07 |             1.55961e+07 |
| S2         | Credit stress (rising unemployment, HPI decline) |          7.96 |          2.28 |       9.89404e+06 |             9.89404e+06 |
| S3         | Base-like                                        |         10.37 |          1.39 |       5.99312e+06 |             5.99312e+06 |
| S4         | Rate rally (elevated prepayment incentive)       |         14.86 |          1.49 |       5.99632e+06 |             5.99632e+06 |
| S5         | Base-like                                        |          7.79 |          1.38 |       6.11999e+06 |             6.11999e+06 |

**Most adverse scenario:** S1 — *Credit stress (rising unemployment, HPI decline)* — cumulative loss $15.6mm, subordinate write-down $15.6mm.

**Most benign scenario:** S3 — *Base-like* — cumulative loss $6.0mm.


## 5a. Escalations

- **ESCALATION: scenario S1 (Credit stress (rising unemployment, HPI decline)) projects cumulative loss of 3.19% of UPB, above the 2.0% desk threshold.**


## 5b. Model Validation

Holdout performance of the CPR/CDR forecaster (400 unseen sequences):

| Metric | CPR | CDR |
|---|---|---|
| R² | 0.8636 | 0.9741 |
| MAE | 0.00465 | 0.00038 |

Predicted CDR standard deviation 0.00366 against realised 0.00374 — the model tracks credit dispersion rather than collapsing to the unconditional mean.


## 6. Analyst Commentary

- Largest state concentration is **NY** at **11.4%** of pool UPB; regional HPI sensitivity is the dominant driver of tail loss in the stressed scenarios.
- The subordinate tranche absorbs the full loss burden before any mezzanine write-down occurs under every generated scenario; senior (AAA-proxy) principal is not impaired in the sampled set.
- Prepayment risk is the binding constraint in rate-rally scenarios (faster CPR shortens senior WAL), while credit-stress scenarios bind through the subordinate write-down channel.

### Model-drafted commentary

*Generated by a LoRA-adapted GPT-2 fine-tuned on surveillance-register text. Phrasing only — every figure in this report is computed deterministically by the pipeline, never generated.*

> Prepayment speeds accelerate across cohorts, consistent with the modelled rate incentive response.
> The subordinate tranche retains significant subordination, and no principal impairment is projected under any generated scenario.
> Credit enhancement to house performance remains the core problem under the subordinate scenario.


---

*Pipeline: synthetic pool generation → stratification → Transformer CPR/CDR forecast → GNN correlated-risk overlay → sequential-pay waterfall → RWA/EL computation → VAE scenario stress. All figures derived from synthetic data for demonstration purposes.*