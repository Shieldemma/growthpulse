"""Budget allocation: maximise predicted weekly new MRR for a FIXED total weekly budget under channel bounds."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from .data import MEDIA
from .transforms import steady_state_adstock


def response(spend: np.ndarray, betas: np.ndarray, decays: np.ndarray, scales: np.ndarray) -> float:
    """Predicted weekly media contribution when each channel sustains `spend` per week."""
    ads = np.array([steady_state_adstock(s, d) for s, d in zip(spend, decays)])
    return float(np.sum(betas * (1 - np.exp(-ads / scales))))


def marginal_return(spend, betas, decays, scales) -> np.ndarray:
    """d(response)/d(spend) per channel at the given weekly spend (extra weekly MRR per extra $1/week)."""
    ads = np.asarray(spend) / (1 - np.asarray(decays))
    return betas * np.exp(-ads / scales) / scales / (1 - decays)


def optimise(current: np.ndarray, budget: float, betas, decays, scales, lo_mult=0.5, hi_mult=1.5) -> np.ndarray:
    lo, hi = current * lo_mult, current * hi_mult
    if lo.sum() > budget or hi.sum() < budget:      # infeasible bounds -> relax proportionally
        lo, hi = np.zeros_like(current), np.full_like(current, budget)
    x0 = np.clip(current * budget / current.sum(), lo, hi)
    res = minimize(lambda s: -response(s, betas, decays, scales), x0, method="SLSQP",
                   bounds=list(zip(lo, hi)), constraints=[{"type": "eq", "fun": lambda s: s.sum() - budget}],
                   options={"maxiter": 300, "ftol": 1e-10})
    return res.x if res.success else x0


def scenarios(current: np.ndarray, coef: pd.Series, decays: dict, scales: dict, boot: pd.DataFrame,
              lo_mult: float = 0.5, hi_mult: float = 1.5) -> pd.DataFrame:
    """Budget scenarios with bootstrap uncertainty on the predicted response."""
    betas = np.array([coef[m] for m in MEDIA])
    d = np.array([decays[m] for m in MEDIA])
    s = np.array([scales[m] for m in MEDIA])
    B = float(current.sum())
    plans = {
        "current (last-52-week average)": current,
        "optimised, same budget": optimise(current, B, betas, d, s, lo_mult, hi_mult),
        "optimised, budget +10%": optimise(current, B * 1.10, betas, d, s, lo_mult, hi_mult * 1.1),
        "optimised, budget -20%": optimise(current, B * 0.80, betas, d, s, lo_mult * 0.8, hi_mult),
        "equal split, same budget": np.clip(np.full_like(current, B / len(current)), current * lo_mult, current * hi_mult),
    }
    boot_betas = boot[[f"beta_{m}" for m in MEDIA]].values
    base_draws = np.array([response(current, b, d, s) for b in boot_betas])
    rows = []
    for name, alloc in plans.items():
        pt = response(alloc, betas, d, s)
        draws = np.array([response(alloc, b, d, s) for b in boot_betas])
        delta = draws - base_draws
        rows.append({"scenario": name, "weekly_budget_usd": float(alloc.sum()),
                     **{f"spend_{m.replace('spend_', '')}": float(a) for m, a in zip(MEDIA, alloc)},
                     "predicted_weekly_media_mrr": pt, "pred_p05": float(np.percentile(draws, 5)),
                     "pred_p95": float(np.percentile(draws, 95)),
                     "delta_vs_current": pt - response(current, betas, d, s),
                     "delta_p05": float(np.percentile(delta, 5)), "delta_p95": float(np.percentile(delta, 95)),
                     "prob_better_than_current": float((delta > 0).mean())})
    return pd.DataFrame(rows)


def response_curves(df_spend_max: dict, coef: pd.Series, decays: dict, scales: dict, boot: pd.DataFrame,
                    n_points: int = 40) -> pd.DataFrame:
    """Steady-state weekly response vs weekly spend per channel with a 90% bootstrap band."""
    rows = []
    for m in MEDIA:
        grid = np.linspace(0, df_spend_max[m] * 1.0, n_points)
        ads = grid / (1 - decays[m])
        shape = 1 - np.exp(-ads / scales[m])
        bs = boot[f"beta_{m}"].values
        lo, hi = np.percentile(np.outer(bs, shape), [5, 95], axis=0)
        for g, pt, l, h in zip(grid, coef[m] * shape, lo, hi):
            rows.append({"channel": m.replace("spend_", ""), "weekly_spend_usd": g, "weekly_mrr": pt, "p05": l, "p95": h})
    return pd.DataFrame(rows)
