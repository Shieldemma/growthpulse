"""End-to-end MMM run: prepare -> split -> tune -> compare -> final fit -> uncertainty -> budgets."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import budget, model
from .data import MEDIA, TARGET, TEST_WEEKS, prepare


def run_mmm(weekly: pd.DataFrame, n_boot: int = 300, test_weeks: int = TEST_WEEKS) -> dict[str, pd.DataFrame]:
    df = prepare(weekly)
    ev = model.evaluate_models(df, test_weeks)
    spec = ev["spec"]
    fb, X, coef, b, fitted = model.final_fit(df, spec)
    boot = model.block_bootstrap(df, X, coef, b, fitted, n_boot=n_boot)
    summary = model.channel_summary(df, X, coef, boot, spec, fb)
    comp = model.contributions(X, coef, b)
    last52 = df.tail(52)
    current = np.array([last52[m].mean() for m in MEDIA])
    scen = budget.scenarios(current, coef, spec.decay, fb.scales_, boot)
    curves = budget.response_curves({m: float(df[m].max()) for m in MEDIA}, coef, spec.decay, fb.scales_, boot)
    # marginal return at current spend (extra weekly MRR per extra $1 of weekly spend, steady state)
    mr = budget.marginal_return(current, np.array([coef[m] for m in MEDIA]),
                                np.array([spec.decay[m] for m in MEDIA]), np.array([fb.scales_[m] for m in MEDIA]))
    summary["current_weekly_spend_usd"] = current
    summary["marginal_weekly_mrr_per_extra_usd"] = mr
    diag = model.diagnostics(df, X, fitted, n_params=X.shape[1] + 1)
    sens = model.sensitivity(df, spec)
    data_out = df[["week_start", TARGET]].copy()
    data_out["fitted"] = fitted
    data_out["residual"] = data_out[TARGET] - fitted
    data_out["is_test_period"] = (df.week_index >= len(df) - test_weeks).astype(int)
    contrib_w = comp.copy()
    contrib_w.insert(0, "week_start", df.week_start.values)
    params = pd.DataFrame({"term": list(coef.index) + ["intercept"], "coefficient": list(coef.values) + [b]})
    cmp_ = ev["comparison"]
    cmp_["chosen_for_decisions"] = [False, ev["chosen"] == "baseline", ev["chosen"] == "improved"]
    return {"mmm_fit": data_out, "mmm_model_comparison": cmp_, "mmm_channel_summary": summary,
            "mmm_contrib_weekly": contrib_w, "mmm_budget_scenarios": scen, "mmm_response_curves": curves,
            "mmm_diagnostics": diag, "mmm_sensitivity": sens, "mmm_params": params,
            "mmm_tuning_log": ev["tuning_log"],
            "mmm_meta": pd.DataFrame([{"chosen": ev["chosen"], "decision_rule": ev["decision_rule"],
                                       "train_weeks": ev["train_weeks"], "test_weeks": ev["test_weeks"],
                                       "n_bootstrap": n_boot, "total_weeks_used": len(df)}])}
