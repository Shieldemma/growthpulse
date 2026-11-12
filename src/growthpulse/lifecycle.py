"""Lifecycle / CRM program incrementality: short-, mid- and long-term effects of an onboarding program.

Short-term = paid conversion within 30 days. Mid/long-term = still paying at 90/180 days and cumulative revenue.
A program can raise conversion but attract lower-quality customers, so long-run value is measured separately.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy import stats

from . import experiment as E


def _rate_row(t: pd.Series, c: pd.Series, label: str, horizon: int, alpha: float) -> dict:
    n_t, n_c, x_t, x_c = len(t), len(c), int(t.sum()), int(c.sum())
    z, p = E.two_proportion_ztest(x_t, n_t, x_c, n_c)
    lo, hi = E.newcombe_diff_ci(x_t, n_t, x_c, n_c, 1 - alpha)
    rel, rlo, rhi = E.relative_lift_ci(x_t, n_t, x_c, n_c, 1 - alpha)
    return {"metric": label, "horizon_days": horizon, "kind": "rate", "control": x_c / n_c, "treatment": x_t / n_t,
            "abs_lift": x_t / n_t - x_c / n_c, "abs_ci_low": lo, "abs_ci_high": hi, "rel_lift": rel,
            "rel_ci_low": rlo, "rel_ci_high": rhi, "p_value": p, "significant": bool(p < alpha)}


def _mean_row(t: pd.Series, c: pd.Series, label: str, horizon: int, alpha: float) -> dict:
    diff = t.mean() - c.mean()
    se = math.sqrt(t.var(ddof=1) / len(t) + c.var(ddof=1) / len(c))
    zc = stats.norm.ppf(1 - alpha / 2)
    p = float(2 * (1 - stats.norm.cdf(abs(diff / se)))) if se > 0 else float("nan")
    return {"metric": label, "horizon_days": horizon, "kind": "per_user_usd", "control": c.mean(), "treatment": t.mean(),
            "abs_lift": diff, "abs_ci_low": diff - zc * se, "abs_ci_high": diff + zc * se,
            "rel_lift": diff / c.mean() if c.mean() else float("nan"),
            "rel_ci_low": (diff - zc * se) / c.mean() if c.mean() else float("nan"),
            "rel_ci_high": (diff + zc * se) / c.mean() if c.mean() else float("nan"), "p_value": p, "significant": bool(p < alpha)}


def analyze_lifecycle(users: pd.DataFrame, catalog_row: pd.Series, gross_margin: float = 0.8) -> tuple[pd.DataFrame, pd.DataFrame]:
    alpha = float(catalog_row.planned_alpha)
    t, c = users[users.assigned_group == "treatment"], users[users.assigned_group == "control"]
    rows = [_rate_row(t.paid_30d, c.paid_30d, "Paid conversion (30d)", 30, alpha),
            _rate_row(t.active_90d, c.active_90d, "Still paying (90d), per assigned user", 90, alpha),
            _rate_row(t.active_180d, c.active_180d, "Still paying (180d), per assigned user", 180, alpha),
            _mean_row(t.revenue_30d, c.revenue_30d, "Revenue per assigned user (30d)", 30, alpha),
            _mean_row(t.revenue_90d, c.revenue_90d, "Revenue per assigned user (90d)", 90, alpha),
            _mean_row(t.revenue_180d, c.revenue_180d, "Revenue per assigned user (180d)", 180, alpha)]
    out = pd.DataFrame(rows)
    out.insert(0, "experiment_id", catalog_row.experiment_id)
    n_t = len(t)
    cost_per_user = float(catalog_row.program_cost_usd) / n_t
    summ = []
    for h in (30, 90, 180):
        r = out[(out.metric == f"Revenue per assigned user ({h}d)")].iloc[0]
        net = r.abs_lift * gross_margin - cost_per_user
        summ.append({"experiment_id": catalog_row.experiment_id, "horizon_days": h,
                     "incremental_revenue_per_assigned_user": r.abs_lift,
                     "incremental_gross_profit_per_assigned_user": r.abs_lift * gross_margin,
                     "program_cost_per_treated_user": cost_per_user, "net_value_per_treated_user": net,
                     "net_value_ci_low": r.abs_ci_low * gross_margin - cost_per_user,
                     "net_value_ci_high": r.abs_ci_high * gross_margin - cost_per_user,
                     "total_net_value_usd": net * n_t, "roi_on_program_cost": (r.abs_lift * gross_margin) / cost_per_user if cost_per_user else float("nan")})
    s = pd.DataFrame(summ)
    r30, r180 = out[out.metric == "Paid conversion (30d)"].iloc[0], out[out.metric == "Revenue per assigned user (180d)"].iloc[0]
    s["persistence_note"] = (f"Relative lift in revenue per user: {out[out.metric=='Revenue per assigned user (30d)'].iloc[0].rel_lift:.1%} at 30d vs "
                             f"{r180.rel_lift:.1%} at 180d - " + ("the effect decays: incremental customers retain worse." if r180.rel_lift < 0.8 * out[out.metric=='Revenue per assigned user (30d)'].iloc[0].rel_lift else "the effect persists."))
    return out, s
