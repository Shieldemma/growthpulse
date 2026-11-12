# Methodology

> **All SaaS, marketing and experiment data in this project are SYNTHETIC.** The numbers demonstrate methods; they are not evidence about any real company. Only the optional GA4 sample (BigQuery mode) is real data - and it has no ad cost, subscriptions or CRM data.

## Fact vs. synthetic vs. estimate vs. assumption vs. causal claim

| Label | Meaning | Examples here |
|---|---|---|
| **Observed (synthetic)** | Directly calculated from the generated tables | spend, clicks, customers, payments, retention counts |
| **Synthetic data** | Produced by `src/growthpulse/datagen` with a fixed seed | every raw table |
| **Model estimate** | Output of a statistical model, with uncertainty | projected LTV, MMM contributions, experiment lift CI |
| **Assumption** | A number we chose, not measured | gross margin 80%, 10% discount rate, hurdle ratios 3:1 / 1.5:1 |
| **Causal conclusion** | Supported by randomisation | only the holdout experiments, and only for what was tested |

## The synthetic world (what the generator builds in)
Fixed seed (default 42), 156 weeks (2023-01-02 to 2025-12-28), USD. Paid media buys clicks with **diminishing returns** (clicks ~ spend^(1-gamma)); weekly budgets are flighted randomly (AR(1) noise, bursts, pauses) so channels vary independently; visitors take multi-session journeys (paid media is only an entry touch); **~14-day trials**; monthly subscriptions with **early-life-heavy churn** that differs by plan and channel; refunds; discounts for coupon/promo signups; **seasonality** and a time trend; promotions that lift conversion; a **halo** (paid social/display lift organic and direct traffic with carryover); **brand-search cannibalisation** (55% of brand clicks would have arrived organically). All parameters are in `src/growthpulse/datagen/assumptions.py`.

Not modelled: failed payments/involuntary churn, plan upgrades, annual billing, multi-currency, product-usage sessions after signup, paid retargeting journeys.

## Metrics
* **CPC** = spend / clicks. **CPA / cost per signup** = spend / signups.
* **Paid-media CAC** = media spend / new paying customers credited to paid channels.
* **Fully loaded CAC** = (media spend + non-media marketing overhead allocated to paid channels pro-rata to spend) / new paying customers. Overhead = team salaries, tools, agency fees, creative production. Organic/owned channels get no allocation, so their CAC is *n/a*.
* **ROAS** = net revenue within the window / media spend. *Not profit* (ignores margin, overhead, later churn) and *not incrementality* (credit != cause).
* **Observed LTV** = net revenue actually collected (refunds netted, dated by the original payment). Windows are the first 3 / 6 / 12 **billing cycles**; a cohort counts only if the window is fully observable, otherwise recent (right-censored) cohorts would look worse simply for being young.
* **Gross-profit LTV** = revenue LTV x gross margin (assumption).
* **Projected LTV (a model)** = 12 observed months + constant monthly churn hazard (estimated from the retention curve between months 3 and 12) to a 36-month horizon, discounted at 10%/yr.
* **Retention(k)** = customers with a payment in billing cycle k / customers for whom cycle k could already have been billed. **Churn** = 1 - retention.
* **LTV:CAC**, **payback month** (first month cumulative gross profit per customer >= CAC; *n/a* if never within the data).
* All ratios return NaN/NULL on a zero denominator (never a fake 0).

## Joins and grain
Every table documents its grain (`docs/data_dictionary.md`). Refunds are aggregated per payment *before* joining; sessions are pre-aggregated before joining to spend; the spend rows in `mart_marketing_performance` repeat per attribution model, so **always filter to one model before summing**. dbt singular tests reconcile spend, net revenue, customers and revenue across marts.

## Attribution (rule-based; not causal)
Journey = every session of the visitor in the 45 days (variable) before signup. Credit per customer sums to 1:
* **First touch** 100% to first session. **Last touch** 100% to last. **Linear** equal split.
* **Position-based (the rule-based multi-touch model)** 40% first, 40% last, 20% shared by middle touches (1 touch = 100%, 2 touches = 50/50).

Limitations: only tracked touches are visible; credit moves between models (sensitivity, not truth); direct/organic look strong in last-touch because people use them when already convinced; none of these say what would have happened *without* the channel. SQL (`int_attribution_credit`) is tested against an independent pandas implementation (`src/growthpulse/attribution.py`).

## Incrementality experiments
Three simulated randomised holdouts with known true effects (ground truth is stored in `data/raw/_ground_truth.json`, outside the warehouse, and never used by the analysis). Primary analysis = **intent-to-treat**. Tests: pooled two-proportion z-test; **Newcombe** CI for the absolute difference; **Katz** log-ratio CI for relative lift; sample-ratio-mismatch chi-square; covariate balance (SMD); contamination and compliance rates; CACE/Wald estimate for the effect on the exposed (needs the exclusion restriction); power, minimum detectable effect, required sample size. Business impact = incremental conversions x average first-payment revenue vs. spend (explicit assumptions on the page). Verified by tests that recover known effects, keep false positives near alpha, and flag invalid randomisation.

## Marketing Mix Model
* **Data:** weekly new MRR (first payments of subscriptions started that week) vs weekly spend of 4 paid channels, time trend, two Fourier seasonal pairs, promo share. 4-week burn-in dropped. Sessions/signups are *excluded* on purpose (mediators).
* **Baseline:** OLS on raw spend + controls.
* **Improved model:** geometric **adstock** (carryover), a **lag** (weeks between spend and effect; the 14-day trial makes this essential), **exponential saturation** (diminishing returns), ridge-regularised regression with media coefficients constrained >= 0.
* **No leakage:** train = all but the last 26 weeks. Hyper-parameters (lag, decay, saturation scale per channel) are chosen by expanding-window time-series CV inside the training weeks only; saturation scales are learned from training weeks only; adstock is causal. Tests prove that changing future spend/outcomes cannot change training features.
* **Decision rule:** the improved model is used only if its held-out RMSE beats the baseline by >= 2%.
* **Evaluation:** RMSE, MAE, MAPE, R2 on the held-out weeks; residual plots; Durbin-Watson, Ljung-Box, Breusch-Pagan, Jarque-Bera, VIF.
* **Uncertainty:** moving-block bootstrap of residuals (block 8 weeks) with fixed transformations -> 90% intervals for contributions, ROI, response curves, scenario outcomes. **Sensitivity:** one-at-a-time changes to decay, lag and saturation scale show how much conclusions move when those assumptions change (bootstrap intervals do not include this).
* **Budget scenarios:** maximise predicted weekly MRR (SLSQP) for a fixed total budget with each channel kept within 50-150% of the last-52-week average; variants for +10% / -20% budget and an equal split. "Probability better" = share of bootstrap draws in which the plan beats the current mix.
* **What it cannot do:** it finds associations after controlling for trend/seasonality/promotions. It becomes causal only if no important driver is omitted. Fitted to synthetic data, it demonstrates the *method*. Use experiments to calibrate it. Google's Meridian is not included (the project uses a transparent baseline first, as recommended); it could be added as an optional advanced module.

## Recommendations
`src/growthpulse/reporting.py` applies explicit rules to calculated results and prints the rule next to each recommendation. Thresholds (`HURDLE_STRONG=3`, `HURDLE_MIN=1.5`, `PAYBACK_OK_MONTHS=12`, `MIN_PROB_BETTER=0.80`) are constants at the top of that file. A channel is downgraded if its holdout test showed no significant lift. Change the data or thresholds and the recommendations change - nothing is hardcoded.
