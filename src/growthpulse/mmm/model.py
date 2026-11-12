"""Fitting, tuning, evaluation, uncertainty and diagnostics for the MMM."""
from __future__ import annotations

import itertools
import math

import numpy as np
import pandas as pd
from scipy.optimize import lsq_linear
from scipy import stats
import statsmodels.api as sm
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error, mean_squared_error, r2_score
from sklearn.model_selection import TimeSeriesSplit
from statsmodels.stats.diagnostic import acorr_ljungbox, het_breuschpagan
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.stats.stattools import durbin_watson

from .data import CONTROLS, MEDIA, TARGET, FeatureBuilder, Spec, chronological_split

DECAY_GRID = [0.0, 0.2, 0.4, 0.6, 0.8]
SCALE_GRID = [0.5, 1.0, 2.0, 4.0]
LAG_GRID = [0, 1, 2, 3]
RIDGE_ALPHA = 1.0


# ------------------------------------------------------------- estimator
def fit_bounded_ridge(X: pd.DataFrame, y: np.ndarray, alpha: float = RIDGE_ALPHA):
    """Ridge regression with media coefficients constrained >= 0 (spend cannot reduce sales), controls free.
    Features are standardised internally; coefficients are returned in ORIGINAL units. Intercept is unpenalised."""
    cols = list(X.columns)
    A = X.values.astype(float)
    mu, sd = A.mean(0), A.std(0)
    sd[sd == 0] = 1.0
    Z = (A - mu) / sd
    yc = y - y.mean()
    p = Z.shape[1]
    aug_X = np.vstack([Z, math.sqrt(alpha) * np.eye(p)])
    aug_y = np.concatenate([yc, np.zeros(p)])
    lower = np.array([0.0 if c in MEDIA else -np.inf for c in cols])
    res = lsq_linear(aug_X, aug_y, bounds=(lower, np.full(p, np.inf)), method="bvls")
    coef = res.x / sd
    intercept = y.mean() - float(coef @ mu)
    return pd.Series(coef, index=cols), float(intercept)


def predict(X: pd.DataFrame, coef: pd.Series, intercept: float) -> np.ndarray:
    return X[coef.index].values @ coef.values + intercept


def metrics(y, yhat) -> dict:
    """Evaluation metrics (scikit-learn implementations)."""
    y, yhat = np.asarray(y, float), np.asarray(yhat, float)
    return {"rmse": float(np.sqrt(mean_squared_error(y, yhat))), "mae": float(mean_absolute_error(y, yhat)),
            "mape": float(mean_absolute_percentage_error(y, yhat)),
            "r2": float(r2_score(y, yhat)) if len(y) > 1 and np.ptp(y) > 0 else float("nan")}


# ------------------------------------------------------------- tuning (time-series CV inside TRAIN only)
def _cv_rmse(df: pd.DataFrame, spec: Spec, n_folds: int = 3, min_train: int = 60) -> float:
    """Expanding-window time-series cross-validation (scikit-learn TimeSeriesSplit): every validation block lies strictly
    AFTER its training block, and features/saturation scales are re-learned from each training block only."""
    n = len(df)
    fold = (n - min_train) // n_folds
    tscv = TimeSeriesSplit(n_splits=n_folds, test_size=fold)
    errs = []
    for tr, va in tscv.split(np.arange(n)):
        tr_idx, va_idx = df.index[tr], df.index[va]
        fb = FeatureBuilder(spec).fit(df, tr_idx)
        X = fb.matrix(df)
        coef, b = fit_bounded_ridge(X.loc[tr_idx], df.loc[tr_idx, TARGET].values)
        errs.append(metrics(df.loc[va_idx, TARGET], predict(X.loc[va_idx], coef, b))["rmse"])
    return float(np.mean(errs))


def tune_spec(train: pd.DataFrame, passes: int = 2) -> tuple[Spec, pd.DataFrame]:
    """Coordinate descent over (decay, saturation scale) per channel, scored by expanding-window CV RMSE.
    Uses only training weeks. Returns best spec and the search log."""
    spec = Spec()
    log = []
    best = _cv_rmse(train, spec)
    for p in range(passes):
        for m in MEDIA:
            for lg, dcy, sc in itertools.product(LAG_GRID, DECAY_GRID, SCALE_GRID):
                trial = spec.copy()
                trial.decay[m], trial.scale_mult[m], trial.lag[m] = dcy, sc, lg
                score = _cv_rmse(train, trial)
                log.append({"pass": p + 1, "channel": m, "lag": lg, "decay": dcy, "scale_mult": sc, "cv_rmse": score})
                if score < best - 1e-9:
                    best, spec = score, trial
    return spec, pd.DataFrame(log)


# ------------------------------------------------------------- baseline + improved + null
def fit_baseline_ols(train: pd.DataFrame):
    """Understandable baseline: plain OLS on RAW spend + trend + seasonality + promo (no adstock, no saturation)."""
    X = sm.add_constant(train[MEDIA + CONTROLS])
    return sm.OLS(train[TARGET], X).fit()


def evaluate_models(df: pd.DataFrame, test_weeks: int) -> dict:
    """Train on early weeks, score on the LAST `test_weeks` (never seen in fitting or tuning)."""
    train, test = chronological_split(df, test_weeks)
    out = {"train_weeks": len(train), "test_weeks": len(test)}
    rows = []
    # 0) controls only (is paid media adding anything?)
    Xc = sm.add_constant(train[CONTROLS])
    ctrl = sm.OLS(train[TARGET], Xc).fit()
    rows.append({"model": "controls_only (no media)", **{f"test_{k}": v for k, v in metrics(
        test[TARGET], ctrl.predict(sm.add_constant(test[CONTROLS], has_constant="add"))).items()},
        "train_rmse": metrics(train[TARGET], ctrl.fittedvalues)["rmse"], "cv_rmse": float("nan")})
    # 1) baseline OLS, raw spend
    base = fit_baseline_ols(train)
    rows.append({"model": "baseline_ols (raw spend)", **{f"test_{k}": v for k, v in metrics(
        test[TARGET], base.predict(sm.add_constant(test[MEDIA + CONTROLS], has_constant="add"))).items()},
        "train_rmse": metrics(train[TARGET], base.fittedvalues)["rmse"], "cv_rmse": float("nan")})
    # 2) improved: adstock + saturation + sign constraints, tuned by CV on train
    spec, log = tune_spec(train)
    fb = FeatureBuilder(spec).fit(df, train.index)
    X = fb.matrix(df)
    coef, b = fit_bounded_ridge(X.loc[train.index], train[TARGET].values)
    rows.append({"model": "improved (adstock + saturation)", **{f"test_{k}": v for k, v in metrics(
        test[TARGET], predict(X.loc[test.index], coef, b)).items()},
        "train_rmse": metrics(train[TARGET], predict(X.loc[train.index], coef, b))["rmse"],
        "cv_rmse": _cv_rmse(train, spec)})
    comp = pd.DataFrame(rows)
    # decision rule: complexity is justified only if it beats baseline on BOTH held-out test RMSE and by >= 2%
    imp, bas = comp.iloc[2].test_rmse, comp.iloc[1].test_rmse
    chosen = "improved" if imp < 0.98 * bas else "baseline"
    out.update({"comparison": comp, "spec": spec, "tuning_log": log, "chosen": chosen,
                "decision_rule": "Improved model is used for contributions/budget only if its held-out test RMSE is >=2% lower than the OLS baseline."})
    return out


# ------------------------------------------------------------- final fit, contributions, bootstrap
def final_fit(df: pd.DataFrame, spec: Spec):
    fb = FeatureBuilder(spec).fit(df, df.index)
    X = fb.matrix(df)
    coef, b = fit_bounded_ridge(X, df[TARGET].values)
    fitted = predict(X, coef, b)
    return fb, X, coef, b, fitted


def contributions(X: pd.DataFrame, coef: pd.Series, intercept: float) -> pd.DataFrame:
    """Weekly decomposition: each column's coefficient x feature, plus 'baseline' = intercept + controls."""
    comp = pd.DataFrame({m: coef[m] * X[m] for m in MEDIA})
    comp["baseline"] = intercept + sum(coef[c] * X[c] for c in CONTROLS)
    return comp


def block_bootstrap(df, X, coef, intercept, fitted, n_boot: int = 300, block: int = 8, seed: int = 7) -> pd.DataFrame:
    """Moving-block bootstrap of residuals (keeps autocorrelation). Refits coefficients with FIXED transformations,
    so intervals reflect coefficient uncertainty only - not uncertainty about adstock/saturation settings
    (see the sensitivity table for those) and not model-misspecification."""
    rng = np.random.default_rng(seed)
    resid = df[TARGET].values - fitted
    n = len(resid)
    draws = []
    for _ in range(n_boot):
        starts = rng.integers(0, n - block + 1, size=math.ceil(n / block))
        r = np.concatenate([resid[s:s + block] for s in starts])[:n]
        y_star = fitted + r
        c, b = fit_bounded_ridge(X, y_star)
        draws.append({**{f"beta_{k}": v for k, v in c.items()}, "intercept": b})
    return pd.DataFrame(draws)


def channel_summary(df, X, coef, boot: pd.DataFrame, spec: Spec, fb: FeatureBuilder) -> pd.DataFrame:
    total_y = df[TARGET].sum()
    rows = []
    for m in MEDIA:
        feat_sum = X[m].sum()
        contrib = coef[m] * feat_sum
        boots = boot[f"beta_{m}"].values * feat_sum
        spend = df[m].sum()
        rows.append({
            "channel": m.replace("spend_", ""), "total_spend_usd": spend,
            "contribution_usd": contrib, "contribution_p05": np.percentile(boots, 5), "contribution_p95": np.percentile(boots, 95),
            "share_of_revenue": contrib / total_y,
            "share_p05": np.percentile(boots, 5) / total_y, "share_p95": np.percentile(boots, 95) / total_y,
            "avg_roi": contrib / spend if spend else float("nan"),
            "avg_roi_p05": np.percentile(boots, 5) / spend if spend else float("nan"),
            "avg_roi_p95": np.percentile(boots, 95) / spend if spend else float("nan"),
            "share_of_draws_at_zero": float((boot[f"beta_{m}"] <= 1e-9).mean()),
            "decay": spec.decay[m], "lag_weeks": spec.lag[m], "saturation_scale_usd": fb.scales_[m]})
    return pd.DataFrame(rows)


def sensitivity(df: pd.DataFrame, spec: Spec) -> pd.DataFrame:
    """How much do channel contributions move if adstock/saturation assumptions are different?
    One-at-a-time perturbations of decay (+/-0.2) and saturation scale (x0.5, x2) for each channel."""
    total_y = df[TARGET].sum()
    rows = []
    base_fb, base_X, base_c, _, _ = final_fit(df, spec)
    base_contrib = {m: base_c[m] * base_X[m].sum() for m in MEDIA}
    for m in MEDIA:
        for label, mod in [("decay -0.2", ("decay", -0.2)), ("decay +0.2", ("decay", 0.2)),
                           ("saturation scale x0.5", ("scale", 0.5)), ("saturation scale x2", ("scale", 2.0)),
                           ("lag -1 week", ("lag", -1)), ("lag +1 week", ("lag", 1))]:
            s = spec.copy()
            if mod[0] == "lag":
                s.lag[m] = int(max(0, s.lag[m] + mod[1]))
            elif mod[0] == "decay":
                s.decay[m] = float(np.clip(s.decay[m] + mod[1], 0.0, 0.9))
            else:
                s.scale_mult[m] = s.scale_mult[m] * mod[1]
            fb, X, c, _, fitted = final_fit(df, s)
            for ch in MEDIA:
                rows.append({"perturbed_channel": m.replace("spend_", ""), "change": label,
                             "channel": ch.replace("spend_", ""),
                             "contribution_usd": c[ch] * X[ch].sum(),
                             "base_contribution_usd": base_contrib[ch],
                             "change_in_share_of_revenue": (c[ch] * X[ch].sum() - base_contrib[ch]) / total_y,
                             "model_rmse": metrics(df[TARGET], fitted)["rmse"]})
    return pd.DataFrame(rows)


# ------------------------------------------------------------- diagnostics
def diagnostics(df: pd.DataFrame, X: pd.DataFrame, fitted: np.ndarray, n_params: int) -> pd.DataFrame:
    resid = df[TARGET].values - fitted
    rows = []
    dw = float(durbin_watson(resid))
    rows.append(("Durbin-Watson", dw, "ok" if 1.5 <= dw <= 2.5 else "warn",
                 "~2 = no first-order autocorrelation; <1.5 positive autocorrelation (omitted dynamics?)."))
    lb = acorr_ljungbox(resid, lags=[8], return_df=True)
    p = float(lb["lb_pvalue"].iloc[0])
    rows.append(("Ljung-Box p (8 lags)", p, "ok" if p > 0.05 else "warn", "p<0.05 = residuals still autocorrelated."))
    exog = sm.add_constant(X.values)
    bp = het_breuschpagan(resid, exog)
    rows.append(("Breusch-Pagan p", float(bp[1]), "ok" if bp[1] > 0.05 else "warn", "p<0.05 = non-constant residual variance."))
    jb = stats.jarque_bera(resid)
    rows.append(("Jarque-Bera p (normality)", float(jb.pvalue), "ok" if jb.pvalue > 0.05 else "warn", "p<0.05 = residuals not normal (matters for intervals)."))
    vifs = [variance_inflation_factor(X.values, i) for i in range(X.shape[1])]
    worst = float(np.max(vifs))
    rows.append(("Max VIF (multicollinearity)", worst, "ok" if worst < 5 else ("warn" if worst < 10 else "fail"),
                 f"Highest: {X.columns[int(np.argmax(vifs))]}. >5 means estimates of that column are unstable."))
    rows.append(("Weeks per parameter", len(df) / n_params, "ok" if len(df) / n_params >= 10 else "warn",
                 "Rule of thumb >= 10 observations per parameter."))
    return pd.DataFrame(rows, columns=["check", "value", "status", "meaning"])
