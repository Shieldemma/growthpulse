"""Generates the business report AND the recommendation table from CALCULATED results only.

Nothing here hardcodes a conclusion such as 'increase channel X': every recommendation is produced by a rule applied to
numbers in the warehouse, and the rule + thresholds are printed next to it so a reader can challenge them.
"""
from __future__ import annotations

import json
import math
from datetime import date

import numpy as np
import pandas as pd

from . import metrics as M
from . import paths

# Decision thresholds (documented in docs/methodology.md). Change them and the recommendations change.
HURDLE_STRONG = 3.0      # gross-profit LTV : fully loaded CAC
HURDLE_MIN = 1.5
PAYBACK_OK_MONTHS = 12
MIN_PROB_BETTER = 0.80   # MMM scenario must beat current with at least this bootstrap probability to be recommended as a TEST


def usd(x, d=0):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "n/a"
    return f"-${abs(x):,.{d}f}" if x < 0 else f"${x:,.{d}f}"


def pct(x, d=0):
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{d}%}"


def num(x, d=2):
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:,.{d}f}"


def load_inputs(con, gross_margin: float = 0.80) -> dict:
    q = lambda s: con.sql(s).df()
    d = {
        "perf": q(f"select * from {paths.MARTS}.mart_marketing_performance where attribution_model = 'first_touch'"),
        "unit": q(f"select * from {paths.MARTS}.mart_channel_unit_economics where attribution_model = 'first_touch'"),
        "ret": q(f"select * from {paths.MARTS}.mart_customer_retention"),
        "attr": q(f"select * from {paths.MARTS}.mart_attribution_comparison"),
        "funnel": q(f"select * from {paths.MARTS}.mart_growth_funnel"),
        "exp": q(f"select * from {paths.ANALYTICS}.experiment_results order by experiment_id"),
        "mmm_sum": q(f"select * from {paths.ANALYTICS}.mmm_channel_summary"),
        "mmm_scen": q(f"select * from {paths.ANALYTICS}.mmm_budget_scenarios"),
        "mmm_cmp": q(f"select * from {paths.ANALYTICS}.mmm_model_comparison"),
        "mmm_diag": q(f"select * from {paths.ANALYTICS}.mmm_diagnostics"),
        "mmm_meta": q(f"select * from {paths.ANALYTICS}.mmm_meta"),
        "gross_margin": gross_margin,
    }
    return d


def retention_curves(ret: pd.DataFrame) -> pd.DataFrame:
    g = ret.groupby(["acquisition_channel", "months_since_start"]).agg(
        observed=("customers_observed", "sum"), retained=("customers_retained", "sum"),
        revenue=("net_revenue_usd", "sum")).reset_index()
    g["retention"] = M.retention_rate(g.retained, g.observed)
    g["revenue_per_observed_customer"] = M.safe_divide(g.revenue, g.observed)
    return g


def channel_economics(inp: dict) -> pd.DataFrame:
    gm = inp["gross_margin"]
    perf = M.aggregate_performance(inp["perf"], by=["channel_name"], window="m12", gross_margin=gm)  # data_end = last spend date
    un = inp["unit"]
    el = un[un.is_eligible_m12 == 1].groupby("channel_name").agg(
        spend=("spend_usd", "sum"), overhead=("overhead_allocated_usd", "sum"), cust=("new_customers", "sum"))
    el["cac_loaded_m12cohorts"] = (el.spend + el.overhead) / el.cust.replace(0, np.nan)
    el.loc[el.spend <= 0, "cac_loaded_m12cohorts"] = np.nan
    out = perf.merge(el[["cac_loaded_m12cohorts"]], left_on="channel_name", right_index=True, how="left")
    out = out.rename(columns={"cac": "cac_paid_media", "cac_loaded_m12cohorts": "cac_fully_loaded"})
    curves = retention_curves(inp["ret"])
    haz, proj, pay = [], [], []
    for _, r in out.iterrows():
        c = curves[curves.acquisition_channel == r.channel_name].set_index("months_since_start")
        h = M.monthly_hazard_from_retention(c.retention)
        late = c.loc[3:12]
        mrev = M.safe_divide(late.revenue.sum(), late.retained.sum() if "retained" in late else np.nan)
        haz.append(h)
        proj.append(M.projected_ltv(mrev, gm, h, 36, 0.10, 12, r.revenue_per_customer_window)
                    if not math.isnan(h) and not math.isnan(r.revenue_per_customer_window) else np.nan)
        cum = (c.revenue_per_observed_customer * gm).cumsum()
        pay.append(M.payback_months(cum, r.cac_fully_loaded))
    out["monthly_churn_hazard_m3_12"] = haz
    out["projected_gp_ltv_36m"] = proj
    out["payback_months_loaded"] = pay
    out["ltv_cac_projected_loaded"] = M.ltv_cac_ratio(out.projected_gp_ltv_36m, out.cac_fully_loaded)
    out["ltv_cac_projected_paid_media"] = M.ltv_cac_ratio(out.projected_gp_ltv_36m, out.cac_paid_media)
    return out


def recommend(econ: pd.DataFrame, inp: dict) -> pd.DataFrame:
    rows = []
    exp = inp["exp"]
    exp_by_channel = {r.channel_id.replace("ch_", ""): r for _, r in exp.iterrows()}
    mmm = inp["mmm_sum"].set_index("channel")
    for _, r in econ[econ.spend_usd > 0].iterrows():
        ch, ratio, pb = r.channel_name, r.ltv_cac_projected_loaded, r.payback_months_loaded
        evidence = [f"projected 36-month gross-profit LTV {usd(r.projected_gp_ltv_36m)} vs fully loaded CAC {usd(r.cac_fully_loaded)} "
                    f"(ratio {num(ratio, 1)}); payback {('%.0f months' % pb) if not math.isnan(pb) else 'not reached in observed data'}"]
        if math.isnan(ratio):
            action, rule = "Investigate", "ratio not computable"
        elif ratio >= HURDLE_STRONG and (not math.isnan(pb) and pb <= PAYBACK_OK_MONTHS):
            action, rule = "Scale candidate (test first)", f"ratio >= {HURDLE_STRONG} and payback <= {PAYBACK_OK_MONTHS} months"
        elif ratio >= HURDLE_MIN:
            action, rule = "Maintain / optimise", f"{HURDLE_MIN} <= ratio < {HURDLE_STRONG} or slow payback"
        elif ratio >= 1.0:
            action, rule = "Reduce / fix", f"1 <= ratio < {HURDLE_MIN}: barely covers its cost over its lifetime"
        else:
            action, rule = "Cut or re-test", "ratio < 1: loses money on a lifetime basis even before overhead risk"
        caveat = []
        e = exp_by_channel.get(ch)
        if e is not None:
            if not e.significant:
                caveat.append(f"experiment {e.experiment_id}: no significant lift (rel. lift {pct(e.rel_lift, 1)}, 95% CI {pct(e.rel_lift_ci_low)} to {pct(e.rel_lift_ci_high)}); "
                              f"attributed ROAS {num(e.attributed_roas)} but incremental ROAS {num(e.incremental_roas)}")
                if action.startswith("Scale"):
                    action = "Hold - verify incrementality"
                    rule += "; downgraded because the holdout test did not show lift"
            else:
                caveat.append(f"experiment {e.experiment_id}: significant lift (rel. {pct(e.rel_lift, 1)}, 95% CI {pct(e.rel_lift_ci_low)} to {pct(e.rel_lift_ci_high)}); "
                              f"incremental ROAS on first payment {num(e.incremental_roas)} vs attributed {num(e.attributed_roas)}")
        if ch in mmm.index:
            m = mmm.loc[ch]
            caveat.append(f"MMM contribution share {pct(m.share_of_revenue, 1)} (90% interval {pct(m.share_p05, 1)} to {pct(m.share_p95, 1)})")
            if m.share_of_draws_at_zero > 0.25:
                caveat.append("MMM cannot distinguish this channel's effect from zero")
        rows.append({"channel": ch, "recommended_action": action, "rule_triggered": rule,
                     "evidence": "; ".join(evidence), "caveats": "; ".join(caveat)})
    return pd.DataFrame(rows)


def budget_recommendation(inp: dict, recs: pd.DataFrame | None = None) -> dict:
    s = inp["mmm_scen"]
    cur = s.iloc[0]
    opt = s[s.scenario == "optimised, same budget"].iloc[0]
    chosen = inp["mmm_meta"].iloc[0].chosen
    shifts = {c: opt[f"spend_{c}"] - cur[f"spend_{c}"] for c in ["paid_search", "paid_social", "display", "affiliate"]}
    ok = opt.prob_better_than_current >= MIN_PROB_BETTER and chosen == "improved"
    # Cross-check: never recommend ADDING spend to a channel that other evidence says is weak.
    conflicts = []
    if recs is not None:
        act = recs.set_index("channel").recommended_action.to_dict()
        exp_sig = {r.channel_id.replace("ch_", ""): bool(r.significant) for _, r in inp["exp"].iterrows()}
        for ch, sh in shifts.items():
            if sh <= 0:
                continue
            why = []
            if str(act.get(ch, "")).startswith(("Cut", "Reduce")):
                why.append(f"unit economics rule says '{act[ch]}'")
            if ch in exp_sig and not exp_sig[ch]:
                why.append("its holdout experiment showed no significant lift")
            if why:
                conflicts.append((ch, "; ".join(why)))
    return {"opt": opt, "cur": cur, "shifts": shifts, "ok": ok, "chosen": chosen, "conflicts": conflicts}


def build_report(con, gross_margin: float = 0.80, data_end: str = "") -> tuple[str, pd.DataFrame, pd.DataFrame]:
    inp = load_inputs(con, gross_margin)
    econ = channel_economics(inp)
    recs = recommend(econ, inp)
    bud = budget_recommendation(inp, recs)
    exp = inp["exp"]
    paid = econ[econ.spend_usd > 0].sort_values("ltv_cac_projected_loaded", ascending=False)
    free = econ[econ.spend_usd == 0]
    tot_spend, tot_cust = inp["perf"].spend_usd.sum(), inp["perf"].new_customers.sum()
    paid_cust = paid.new_customers.sum()
    best, worst = paid.iloc[0], paid.iloc[-1]
    ret = retention_curves(inp["ret"])
    r12 = ret[ret.months_since_start == 12].groupby("acquisition_channel").apply(
        lambda g: g.retained.sum() / g.observed.sum(), include_groups=False)
    att = inp["attr"].pivot(index="channel_name", columns="attribution_model", values="credited_paying_customers")
    L = []
    A = L.append
    A("# GrowthPulse - Business Report\n")
    A("> **SYNTHETIC DATA.** Every number below comes from a simulated SaaS company (fixed seed). It demonstrates the "
      "method and is **not evidence about any real company or market.**\n")
    A(f"_Generated {date.today().isoformat()} from the local warehouse; data through {data_end or 'n/a'}._\n")
    A("**How to read this report:** sections are labelled **FACT** (calculated directly from the data), **ESTIMATE** "
      "(model output with uncertainty) and **RECOMMENDATION** (a rule applied to the first two; assumptions listed).\n")
    # ---------------- executive summary
    A("## Executive summary (5-minute read)\n")
    A(f"- **Scale:** {usd(tot_spend)} of paid media acquired {num(paid_cust, 0)} paying customers through paid channels "
      f"({num(tot_cust, 0)} paying customers in total, including organic/owned). _FACT_")
    A(f"- **Efficiency:** best paid channel on lifetime economics is **{best.channel_name}** (projected 36-month gross-profit LTV : fully loaded CAC = "
      f"{num(best.ltv_cac_projected_loaded, 1)}); weakest is **{worst.channel_name}** ({num(worst.ltv_cac_projected_loaded, 1)}). _ESTIMATE (36-month projection)_")
    below = paid[paid.ltv_cac_projected_loaded < HURDLE_MIN].channel_name.tolist()
    A(f"- **Below the {HURDLE_MIN}:1 hurdle:** {', '.join(below) if below else 'none'}. _ESTIMATE_")
    for _, e in exp.iterrows():
        A(f"- **{e.experiment_id} ({e.experiment_name}):** {e.verdict} Attributed ROAS {num(e.attributed_roas)} vs incremental ROAS {num(e.incremental_roas)} (first-payment revenue). _ESTIMATE_")
    if bud["ok"]:
        sh = ", ".join(f"{k.replace('_', ' ')} {'+' if v >= 0 else '-'}{usd(abs(v))}/wk" for k, v in bud["shifts"].items())
        A(f"- **Budget:** the MMM suggests reallocating the same weekly budget ({sh}) for an estimated {usd(bud['opt'].delta_vs_current)}/week more new MRR "
          f"(90% interval {usd(bud['opt'].delta_p05)} to {usd(bud['opt'].delta_p95)}; {pct(bud['opt'].prob_better_than_current)} of bootstrap draws beat current). "
          f"Treat as a **test hypothesis**, not a certainty. _RECOMMENDATION_")
        for ch, why in bud["conflicts"]:
            A(f"  - **Conflict - do not add {ch} spend yet:** the MMM suggests more {ch}, but {why}. Evidence that is causal (experiments) and economics outrank the MMM here; re-test before acting.")
    else:
        A("- **Budget:** the MMM does not give a reliable enough signal to recommend a reallocation (improved model not justified or "
          f"only {pct(bud['opt'].prob_better_than_current)} of bootstrap draws beat the current mix). Run holdout tests first. _RECOMMENDATION_")
    A("- **Biggest caveat:** attribution credit, MMM contributions and experiments answer different questions and will disagree. Only the experiments are causal, and only for what was tested.\n")
    # ---------------- facts
    A("## 1. FACTS - observed in the (synthetic) data\n")
    A("### 1.1 Channel performance (customers attributed by first touch; revenue = net of refunds)\n")
    A("| Channel | Spend | New customers | CPC | CAC (paid media) | CAC (fully loaded) | 12-mo revenue / customer | ROAS (12-mo) | 12-mo retention |")
    A("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for _, r in econ.sort_values("spend_usd", ascending=False).iterrows():
        A(f"| {r.channel_name} | {usd(r.spend_usd)} | {num(r.new_customers, 0)} | {usd(r.cpc, 2)} | {usd(r.cac_paid_media)} | {usd(r.cac_fully_loaded)} | "
          f"{usd(r.revenue_per_customer_window)} | {num(r.roas_window)} | {pct(r.get('ret12', r12.get(r.channel_name, np.nan)))} |")
    A("\nCAC (paid media) = media spend / new paying customers. CAC (fully loaded) additionally includes team, tools, agency and creative "
      "costs allocated to paid channels in proportion to media spend. ROAS and 12-month figures use only cohorts observed for a full 12 months. "
      "**ROAS is revenue per ad dollar - it is not profit and it does not prove the ads caused the revenue.**\n")
    A("### 1.2 Customer quality\n")
    for _, r in econ.sort_values("revenue_per_customer_window", ascending=False).iterrows():
        A(f"- {r.channel_name}: 12-month revenue per customer {usd(r.revenue_per_customer_window)}, 12-month retention {pct(r12.get(r.channel_name, np.nan))}, "
          f"estimated monthly churn (months 3-12) {pct(r.monthly_churn_hazard_m3_12, 1)}.")
    A("\n### 1.3 Funnel (visitors who ever reached each step, all channels)\n")
    f = inp["funnel"][["visitors", "pricing_viewers", "signup_starters", "signups", "trials", "paying_customers"]].sum()
    steps = list(f.index)
    for i, s_ in enumerate(steps):
        prev = f"{pct(f[s_] / f[steps[i - 1]], 1)} of previous step" if i else "-"
        A(f"- {s_.replace('_', ' ')}: {num(f[s_], 0)} ({prev})")
    drop = max(range(1, len(steps)), key=lambda i: 1 - f[steps[i]] / f[steps[i - 1]])
    A(f"\nLargest relative drop: **{steps[drop - 1].replace('_', ' ')} -> {steps[drop].replace('_', ' ')}**. (Recent cohorts are right-censored.)\n")
    A("### 1.4 Attribution comparison (paying customers credited)\n")
    A("| Channel | " + " | ".join(att.columns) + " |\n|---|" + "---:|" * len(att.columns))
    for ch, r in att.iterrows():
        A(f"| {ch} | " + " | ".join(num(v, 0) for v in r.values) + " |")
    spread = (att.max(axis=1) - att.min(axis=1)) / att.mean(axis=1)
    A(f"\nCredit for **{spread.idxmax()}** moves by {pct(spread.max())} depending on the rule - conclusions that depend on one attribution rule are fragile. "
      "These are rule-based credit splits, **not causal measurements.**\n")
    # ---------------- estimates
    A("## 2. ESTIMATES - experiments and models\n")
    A("### 2.1 Incrementality experiments (randomised holdouts; synthetic)\n")
    A("| Experiment | Control rate | Treatment rate | Relative lift (95% CI) | p-value | Incr. ROAS | Attributed ROAS | MDE @80% power |")
    A("|---|---:|---:|---|---:|---:|---:|---:|")
    for _, e in exp.iterrows():
        A(f"| {e.experiment_id} {e.experiment_name} | {pct(e.rate_control, 2)} | {pct(e.rate_treatment, 2)} | {pct(e.rel_lift, 1)} ({pct(e.rel_lift_ci_low)} to {pct(e.rel_lift_ci_high)}) | "
          f"{e.p_value:.3f} | {num(e.incremental_roas)} | {num(e.attributed_roas)} | {pct(e.mde_relative)} |")
    A("\nPrimary estimate is intent-to-treat (everyone assigned). Incremental ROAS uses first-payment revenue only inside a 14-day window, so it understates lifetime value; "
      "a campaign with incremental ROAS below 1 can still pay back if customers stay long enough - compare with the LTV figures above.\n")
    A("### 2.2 Marketing Mix Model\n")
    cmp_ = inp["mmm_cmp"]
    A("Held-out test performance (last 26 weeks, never used for fitting or tuning):\n")
    A("| Model | Test RMSE | Test MAPE | Test R2 |\n|---|---:|---:|---:|")
    for _, r in cmp_.iterrows():
        A(f"| {r.model}{' **(used)**' if r.chosen_for_decisions else ''} | {usd(r.test_rmse)} | {pct(r.test_mape, 1)} | {num(r.test_r2)} |")
    A("\nChannel contributions to weekly new MRR (full period, 90% bootstrap interval):\n")
    A("| Channel | Share of new MRR | Avg ROI ($ new MRR per $ spend) | Lag (wks) | Carryover | Draws at zero |\n|---|---|---|---:|---:|---:|")
    for _, m in inp["mmm_sum"].iterrows():
        A(f"| {m.channel} | {pct(m.share_of_revenue, 1)} ({pct(m.share_p05, 1)} to {pct(m.share_p95, 1)}) | "
          f"{num(m.avg_roi)} ({num(m.avg_roi_p05)} to {num(m.avg_roi_p95)}) | {int(m.lag_weeks)} | {num(m.decay)} | {pct(m.share_of_draws_at_zero)} |")
    warn = inp["mmm_diag"][inp["mmm_diag"].status != "ok"]
    A("\nDiagnostics needing attention: " + ("; ".join(f"{r.check} ({r.status})" for _, r in warn.iterrows()) if len(warn) else "none") + ". "
      "Intervals are bootstrap intervals with FIXED adstock/saturation settings; the sensitivity table in the dashboard shows how contributions move when those change. "
      "A model fitted to synthetic data demonstrates the method - it is not causal evidence.\n")
    A("### 2.3 Budget scenarios (MMM, fixed channel bounds 50-150% of current)\n")
    A("| Scenario | Weekly budget | Search | Social | Display | Affiliate | Predicted change in weekly MRR vs current (90%) | P(better) |\n|---|---:|---:|---:|---:|---:|---|---:|")
    for _, s in inp["mmm_scen"].iterrows():
        A(f"| {s.scenario} | {usd(s.weekly_budget_usd)} | {usd(s.spend_paid_search)} | {usd(s.spend_paid_social)} | {usd(s.spend_display)} | {usd(s.spend_affiliate)} | "
          f"{usd(s.delta_vs_current)} ({usd(s.delta_p05)} to {usd(s.delta_p95)}) | {pct(s.prob_better_than_current)} |")
    A("")
    # ---------------- recommendations
    A("## 3. RECOMMENDATIONS (rule-based; assumptions below)\n")
    A(f"Rules: ratio = projected 36-month gross-profit LTV : fully loaded CAC. >= {HURDLE_STRONG} with payback <= {PAYBACK_OK_MONTHS} months = scale candidate; "
      f">= {HURDLE_MIN} = maintain; 1-{HURDLE_MIN} = reduce/fix; < 1 = cut or re-test. A channel is downgraded if its holdout test showed no significant lift.\n")
    for _, r in recs.iterrows():
        A(f"**{r.channel} -> {r.recommended_action}.**  \n{r.evidence}.  \n_Rule:_ {r.rule_triggered}.  \n_Caveats:_ {r.caveats or 'none'}\n")
    A("**Next steps (generated from the results above):**")
    steps_ = []
    for _, e in exp.iterrows():
        if not e.significant and e.mde_relative > 0.25:
            steps_.append(f"{e.experiment_id} is underpowered (MDE {pct(e.mde_relative)}): rerun with about {num(e.required_n_per_arm_for_observed_lift, 0) if not math.isnan(e.required_n_per_arm_for_observed_lift) else 'a larger sample'} users per arm before deciding.")
        elif not e.significant:
            steps_.append(f"{e.experiment_id} found no detectable lift with adequate power: challenge the {e.channel_id.replace('ch_', '')} budget and re-test with a lower spend cell.")
    if bud["ok"]:
        keep = [c for c in bud["shifts"] if c not in {x[0] for x in bud["conflicts"]}]
        steps_.append("Pilot the MMM-suggested reallocation in a staged way (e.g. geo split) and measure the outcome before committing the full budget"
                      + (f"; exclude the increases for {', '.join(x[0] for x in bud['conflicts'])} (conflicting evidence)." if bud["conflicts"] else "."))
    else:
        steps_.append("Do not reallocate budget on MMM output alone; collect more variation in spend (planned flighting) or add holdouts.")
    steps_.append("Investigate any diagnostic marked warn in section 2.2 and re-check conclusions against attribution sensitivity (section 1.4).")
    for i, s_ in enumerate(steps_, 1):
        A(f"{i}. {s_}")
    A("\n## 4. Assumptions\n")
    A(f"- Gross margin {pct(gross_margin)} (synthetic assumption, not observed). Fully loaded CAC allocates non-media overhead to paid channels pro-rata to media spend.\n"
      "- 36-month LTV projection assumes a constant monthly churn hazard estimated from months 3-12 and a 10% annual discount rate; it is a model, not an observation.\n"
      "- Customers are attributed to channels by first touch in the CAC/ROAS tables; other models are shown in 1.4.\n"
      "- Experiment value uses first-payment revenue within the 14-day window; MMM outcome is new MRR booked per week.\n")
    A("## 5. Risks and data limitations\n")
    A("- All data are simulated; patterns (diminishing returns, churn, seasonality) were built in by the generator, so agreement with them proves the pipeline works, not that real markets behave this way.\n"
      "- Synthetic journeys start with paid media as entry points only; real paid retargeting/multi-device journeys are messier.\n"
      "- MMM uses ~150 weekly points; effects of small channels are poorly identified (see intervals). Spend was varied randomly by the generator - real budgets are usually less varied and correlated across channels.\n"
      "- Recent cohorts are right-censored; ROAS/LTV only use fully observed cohorts so the newest months are excluded from those metrics.\n"
      "- The GA4 sample (BigQuery mode) has no ad cost, subscriptions or CRM data, so CAC/LTV/ROAS are computed on the synthetic SaaS data only.\n")
    return "\n".join(L), econ, recs
