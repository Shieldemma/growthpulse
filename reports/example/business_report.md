# GrowthPulse - Business Report

> **SYNTHETIC DATA.** Every number below comes from a simulated SaaS company (fixed seed). It demonstrates the method and is **not evidence about any real company or market.**

_Generated 2026-10-16 from the local warehouse; data through 2025-12-28._

**How to read this report:** sections are labelled **FACT** (calculated directly from the data), **ESTIMATE** (model output with uncertainty) and **RECOMMENDATION** (a rule applied to the first two; assumptions listed).

## Executive summary (5-minute read)

- **Scale:** $1,658,498 of paid media acquired 3,301 paying customers through paid channels (8,242 paying customers in total, including organic/owned). _FACT_
- **Efficiency:** best paid channel on lifetime economics is **paid_search** (projected 36-month gross-profit LTV : fully loaded CAC = 4.1); weakest is **display** (0.5). _ESTIMATE (36-month projection)_
- **Below the 1.5:1 hurdle:** affiliate, paid_social, display. _ESTIMATE_
- **EXP-001 (Paid social lookalike holdout):** Positive incremental effect detected (CI excludes zero). Attributed ROAS 1.22 vs incremental ROAS 0.22 (first-payment revenue). _ESTIMATE_
- **EXP-002 (Display prospecting holdout):** Inconclusive: no significant effect. The data cannot distinguish zero from effects up to about +10% relative. Attributed ROAS 1.38 vs incremental ROAS -0.01 (first-payment revenue). _ESTIMATE_
- **EXP-003 (Affiliate coupon pilot (small)):** Inconclusive: no significant effect. The data cannot distinguish zero from effects up to about +61% relative. Attributed ROAS 1.73 vs incremental ROAS 0.44 (first-payment revenue). _ESTIMATE_
- **Budget:** the MMM suggests reallocating the same weekly budget (paid search +$1,625/wk, paid social -$1,803/wk, display +$904/wk, affiliate -$726/wk) for an estimated $613/week more new MRR (90% interval -$162 to $1,037; 91% of bootstrap draws beat current). Treat as a **test hypothesis**, not a certainty. _RECOMMENDATION_
  - **Conflict - do not add display spend yet:** the MMM suggests more display, but unit economics rule says 'Cut or re-test'; its holdout experiment showed no significant lift. Evidence that is causal (experiments) and economics outrank the MMM here; re-test before acting.
- **Biggest caveat:** attribution credit, MMM contributions and experiments answer different questions and will disagree. Only the experiments are causal, and only for what was tested.

## 1. FACTS - observed in the (synthetic) data

### 1.1 Channel performance (customers attributed by first touch; revenue = net of refunds)

| Channel | Spend | New customers | CPC | CAC (paid media) | CAC (fully loaded) | 12-mo revenue / customer | ROAS (12-mo) | 12-mo retention |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| paid_search | $665,201 | 1,950 | $8.53 | $341 | $479 | $1,223 | 3.56 | 56% |
| paid_social | $537,076 | 656 | $6.85 | $819 | $1,116 | $768 | 0.95 | 46% |
| display | $255,095 | 230 | $2.58 | $1,109 | $1,509 | $642 | 0.60 | 34% |
| affiliate | $201,126 | 465 | $5.87 | $433 | $576 | $512 | 1.22 | 29% |
| email | $0 | 616 | n/a | n/a | n/a | $1,135 | n/a | 66% |
| direct | $0 | 1,677 | n/a | n/a | n/a | $1,402 | n/a | 65% |
| organic_search | $0 | 2,020 | n/a | n/a | n/a | $1,271 | n/a | 61% |
| referral | $0 | 628 | n/a | n/a | n/a | $1,370 | n/a | 68% |

CAC (paid media) = media spend / new paying customers. CAC (fully loaded) additionally includes team, tools, agency and creative costs allocated to paid channels in proportion to media spend. ROAS and 12-month figures use only cohorts observed for a full 12 months. **ROAS is revenue per ad dollar - it is not profit and it does not prove the ads caused the revenue.**

### 1.2 Customer quality

- direct: 12-month revenue per customer $1,402, 12-month retention 65%, estimated monthly churn (months 3-12) 3.0%.
- referral: 12-month revenue per customer $1,370, 12-month retention 68%, estimated monthly churn (months 3-12) 2.5%.
- organic_search: 12-month revenue per customer $1,271, 12-month retention 61%, estimated monthly churn (months 3-12) 3.2%.
- paid_search: 12-month revenue per customer $1,223, 12-month retention 56%, estimated monthly churn (months 3-12) 3.7%.
- email: 12-month revenue per customer $1,135, 12-month retention 66%, estimated monthly churn (months 3-12) 2.4%.
- paid_social: 12-month revenue per customer $768, 12-month retention 46%, estimated monthly churn (months 3-12) 4.9%.
- display: 12-month revenue per customer $642, 12-month retention 34%, estimated monthly churn (months 3-12) 7.5%.
- affiliate: 12-month revenue per customer $512, 12-month retention 29%, estimated monthly churn (months 3-12) 7.9%.

### 1.3 Funnel (visitors who ever reached each step, all channels)

- visitors: 471,214 (-)
- pricing viewers: 245,438 (52.1% of previous step)
- signup starters: 80,714 (32.9% of previous step)
- signups: 23,834 (29.5% of previous step)
- trials: 21,912 (91.9% of previous step)
- paying customers: 8,242 (37.6% of previous step)

Largest relative drop: **signup starters -> signups**. (Recent cohorts are right-censored.)

### 1.4 Attribution comparison (paying customers credited)

| Channel | first_touch | last_touch | linear | position_based |
|---|---:|---:|---:|---:|
| affiliate | 465 | 339 | 398 | 400 |
| direct | 1,677 | 1,971 | 1,829 | 1,827 |
| display | 230 | 191 | 209 | 210 |
| email | 616 | 1,002 | 823 | 817 |
| organic_search | 2,020 | 2,136 | 2,090 | 2,084 |
| paid_search | 1,950 | 1,292 | 1,589 | 1,604 |
| paid_social | 656 | 513 | 580 | 582 |
| referral | 628 | 798 | 723 | 718 |

Credit for **email** moves by 47% depending on the rule - conclusions that depend on one attribution rule are fragile. These are rule-based credit splits, **not causal measurements.**

## 2. ESTIMATES - experiments and models

### 2.1 Incrementality experiments (randomised holdouts; synthetic)

| Experiment | Control rate | Treatment rate | Relative lift (95% CI) | p-value | Incr. ROAS | Attributed ROAS | MDE @80% power |
|---|---:|---:|---|---:|---:|---:|---:|
| EXP-001 Paid social lookalike holdout | 1.98% | 2.41% | 21.5% (9% to 35%) | 0.000 | 0.22 | 1.22 | 17% |
| EXP-002 Display prospecting holdout | 1.58% | 1.57% | -0.9% (-11% to 11%) | 0.875 | -0.01 | 1.38 | 16% |
| EXP-003 Affiliate coupon pilot (small) | 2.64% | 3.36% | 27.5% (-5% to 70%) | 0.100 | 0.44 | 1.73 | 49% |

Primary estimate is intent-to-treat (everyone assigned). Incremental ROAS uses first-payment revenue only inside a 14-day window, so it understates lifetime value; a campaign with incremental ROAS below 1 can still pay back if customers stay long enough - compare with the LTV figures above.

### 2.2 Marketing Mix Model

Held-out test performance (last 26 weeks, never used for fitting or tuning):

| Model | Test RMSE | Test MAPE | Test R2 |
|---|---:|---:|---:|
| controls_only (no media) | $1,732 | 19.1% | -0.04 |
| baseline_ols (raw spend) | $1,743 | 20.0% | -0.05 |
| improved (adstock + saturation) **(used)** | $1,521 | 17.3% | 0.20 |

Channel contributions to weekly new MRR (full period, 90% bootstrap interval):

| Channel | Share of new MRR | Avg ROI ($ new MRR per $ spend) | Lag (wks) | Carryover | Draws at zero |
|---|---|---|---:|---:|---:|
| paid_search | 26.6% (10.7% to 39.1%) | 0.41 (0.16 to 0.60) | 2 | 0.60 | 0% |
| paid_social | 8.6% (0.0% to 17.3%) | 0.16 (0.00 to 0.33) | 2 | 0.20 | 8% |
| display | 11.7% (0.0% to 28.3%) | 0.47 (0.00 to 1.14) | 0 | 0.60 | 8% |
| affiliate | 0.0% (0.0% to 34.2%) | 0.00 (0.00 to 1.76) | 0 | 0.80 | 46% |

Diagnostics needing attention: Durbin-Watson (warn); Ljung-Box p (8 lags) (warn); Breusch-Pagan p (warn). Intervals are bootstrap intervals with FIXED adstock/saturation settings; the sensitivity table in the dashboard shows how contributions move when those change. A model fitted to synthetic data demonstrates the method - it is not causal evidence.

### 2.3 Budget scenarios (MMM, fixed channel bounds 50-150% of current)

| Scenario | Weekly budget | Search | Social | Display | Affiliate | Predicted change in weekly MRR vs current (90%) | P(better) |
|---|---:|---:|---:|---:|---:|---|---:|
| current (last-52-week average) | $11,855 | $4,990 | $3,607 | $1,807 | $1,451 | $0 ($0 to $0) | 0% |
| optimised, same budget | $11,855 | $6,615 | $1,803 | $2,711 | $726 | $613 (-$162 to $1,037) | 91% |
| optimised, budget +10% | $13,041 | $7,530 | $1,803 | $2,982 | $726 | $996 ($50 to $1,572) | 95% |
| optimised, budget -20% | $9,484 | $4,768 | $1,443 | $2,693 | $580 | -$85 (-$990 to $376) | 29% |
| equal split, same budget | $10,815 | $2,964 | $2,964 | $2,711 | $2,177 | -$514 (-$1,054 to $312) | 17% |

## 3. RECOMMENDATIONS (rule-based; assumptions below)

Rules: ratio = projected 36-month gross-profit LTV : fully loaded CAC. >= 3.0 with payback <= 12 months = scale candidate; >= 1.5 = maintain; 1-1.5 = reduce/fix; < 1 = cut or re-test. A channel is downgraded if its holdout test showed no significant lift.

**affiliate -> Reduce / fix.**  
projected 36-month gross-profit LTV $655 vs fully loaded CAC $576 (ratio 1.1); payback 22 months.  
_Rule:_ 1 <= ratio < 1.5: barely covers its cost over its lifetime.  
_Caveats:_ experiment EXP-003: no significant lift (rel. lift 27.5%, 95% CI -5% to 70%); attributed ROAS 1.73 but incremental ROAS 0.44; MMM contribution share 0.0% (90% interval 0.0% to 34.2%); MMM cannot distinguish this channel's effect from zero

**display -> Cut or re-test.**  
projected 36-month gross-profit LTV $801 vs fully loaded CAC $1,509 (ratio 0.5); payback not reached in observed data.  
_Rule:_ ratio < 1: loses money on a lifetime basis even before overhead risk.  
_Caveats:_ experiment EXP-002: no significant lift (rel. lift -0.9%, 95% CI -11% to 11%); attributed ROAS 1.38 but incremental ROAS -0.01; MMM contribution share 11.7% (90% interval 0.0% to 28.3%)

**paid_search -> Scale candidate (test first).**  
projected 36-month gross-profit LTV $1,949 vs fully loaded CAC $479 (ratio 4.1); payback 6 months.  
_Rule:_ ratio >= 3.0 and payback <= 12 months.  
_Caveats:_ MMM contribution share 26.6% (90% interval 10.7% to 39.1%)

**paid_social -> Reduce / fix.**  
projected 36-month gross-profit LTV $1,149 vs fully loaded CAC $1,116 (ratio 1.0); payback 31 months.  
_Rule:_ 1 <= ratio < 1.5: barely covers its cost over its lifetime.  
_Caveats:_ experiment EXP-001: significant lift (rel. 21.5%, 95% CI 9% to 35%); incremental ROAS on first payment 0.22 vs attributed 1.22; MMM contribution share 8.6% (90% interval 0.0% to 17.3%)

**Next steps (generated from the results above):**
1. EXP-002 found no detectable lift with adequate power: challenge the display budget and re-test with a lower spend cell.
2. EXP-003 is underpowered (MDE 49%): rerun with about 8,681 users per arm before deciding.
3. Pilot the MMM-suggested reallocation in a staged way (e.g. geo split) and measure the outcome before committing the full budget; exclude the increases for display (conflicting evidence).
4. Investigate any diagnostic marked warn in section 2.2 and re-check conclusions against attribution sensitivity (section 1.4).

## 4. Assumptions

- Gross margin 80% (synthetic assumption, not observed). Fully loaded CAC allocates non-media overhead to paid channels pro-rata to media spend.
- 36-month LTV projection assumes a constant monthly churn hazard estimated from months 3-12 and a 10% annual discount rate; it is a model, not an observation.
- Customers are attributed to channels by first touch in the CAC/ROAS tables; other models are shown in 1.4.
- Experiment value uses first-payment revenue within the 14-day window; MMM outcome is new MRR booked per week.

## 5. Risks and data limitations

- All data are simulated; patterns (diminishing returns, churn, seasonality) were built in by the generator, so agreement with them proves the pipeline works, not that real markets behave this way.
- Synthetic journeys start with paid media as entry points only; real paid retargeting/multi-device journeys are messier.
- MMM uses ~150 weekly points; effects of small channels are poorly identified (see intervals). Spend was varied randomly by the generator - real budgets are usually less varied and correlated across channels.
- Recent cohorts are right-censored; ROAS/LTV only use fully observed cohorts so the newest months are excluded from those metrics.
- The GA4 sample (BigQuery mode) has no ad cost, subscriptions or CRM data, so CAC/LTV/ROAS are computed on the synthetic SaaS data only.
