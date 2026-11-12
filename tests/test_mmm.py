import numpy as np
import pandas as pd
import pytest

from growthpulse.mmm import budget as B, model as MM
from growthpulse.mmm.data import CONTROLS, MEDIA, FeatureBuilder, Spec, chronological_split, prepare
from growthpulse.mmm.transforms import exp_saturation, geometric_adstock


def test_adstock_known_values():
    assert geometric_adstock([100, 0, 0], 0.5).tolist() == [100, 50, 25]
    assert geometric_adstock([1, 1, 1], 0.0).tolist() == [1, 1, 1]
    with pytest.raises(ValueError):
        geometric_adstock([1], 1.0)


def test_adstock_is_causal():
    x = np.arange(10.0)
    a = geometric_adstock(x, 0.6)
    x2 = x.copy(); x2[7:] = 999
    assert np.allclose(a[:7], geometric_adstock(x2, 0.6)[:7])


def test_saturation_monotonic_bounded_concave():
    s = exp_saturation(np.linspace(0, 100, 50), 20)
    assert (np.diff(s) > 0).all() and s.max() < 1 and (np.diff(s, 2) < 0).all()


def synth(n=160, seed=0, noise=300.0):
    """Weekly data with a KNOWN structure: lag 1, decay 0.5 on search; saturation; trend; seasonality."""
    rng = np.random.default_rng(seed)
    wk = pd.date_range("2023-01-02", periods=n, freq="W-MON")
    df = pd.DataFrame({"week_start": wk, "promo_share": (rng.random(n) < 0.1) * 1.0})
    for m, base in zip(MEDIA, [5000, 4000, 2000, 1500]):
        df[m] = base * np.exp(rng.normal(0, 0.4, n))
    df["is_complete_week"] = 1
    ads = geometric_adstock(np.concatenate([[0], df.spend_paid_search.values[:-1]]), 0.5)
    sat = exp_saturation(ads, 1.5 * ads.mean())
    t = np.arange(n)
    df["new_mrr_usd"] = 8000 + 40 * t + 800 * np.sin(2 * np.pi * t / 52) + 9000 * sat + 1500 * df.promo_share + rng.normal(0, noise, n)
    return df


def test_prepare_validates_input():
    df = synth()
    out = prepare(df)
    assert len(out) == len(df) - 4 and {"trend", "sin1", "cos2"} <= set(out.columns)
    with pytest.raises(ValueError, match="gaps"):
        prepare(df.drop(index=[40]))
    with pytest.raises(ValueError, match="missing"):
        prepare(df.drop(columns=["promo_share"]))
    bad = df.copy(); bad.loc[3, "spend_display"] = np.nan
    with pytest.raises(ValueError, match="missing values"):
        prepare(bad)


def test_split_is_chronological_and_disjoint():
    d = prepare(synth())
    tr, te = chronological_split(d, 26)
    assert tr.week_start.max() < te.week_start.min() and len(te) == 26 and len(tr) + len(te) == len(d)
    with pytest.raises(ValueError):
        chronological_split(d.head(30), 26)


def test_no_future_leakage_into_training_features():
    d = prepare(synth())
    tr, te = chronological_split(d, 26)
    spec = Spec(decay={m: 0.5 for m in MEDIA}, scale_mult={m: 1.0 for m in MEDIA}, lag={m: 1 for m in MEDIA})
    fb1 = FeatureBuilder(spec).fit(d, tr.index)
    X1 = fb1.matrix(d)
    d2 = d.copy()
    for m in MEDIA:                       # wildly change the TEST period spend
        d2.loc[te.index, m] = d2.loc[te.index, m] * 50 + 1e6
    d2.loc[te.index, "new_mrr_usd"] = -1
    fb2 = FeatureBuilder(spec).fit(d2, tr.index)
    X2 = fb2.matrix(d2)
    assert fb1.scales_ == fb2.scales_                                  # learned scales ignore the future
    pd.testing.assert_frame_equal(X1.loc[tr.index], X2.loc[tr.index])  # training matrix unchanged


def test_tuning_uses_only_training_weeks(monkeypatch):
    d = prepare(synth())
    tr, te = chronological_split(d, 26)
    seen = []
    orig = MM._cv_rmse
    monkeypatch.setattr(MM, "_cv_rmse", lambda df, spec, *a, **k: (seen.append(df.week_start.max()), orig(df, spec, *a, **k))[1])
    MM.evaluate_models(d, 26)
    assert max(seen) <= tr.week_start.max()


def test_bounded_ridge_enforces_non_negative_media():
    d = prepare(synth())
    X = d[MEDIA + CONTROLS]
    y = d.new_mrr_usd.values - 20 * d.spend_display.values     # make display look harmful
    coef, _ = MM.fit_bounded_ridge(X, y)
    assert (coef[MEDIA] >= -1e-9).all()


def test_model_recovers_known_search_effect_and_beats_controls_only():
    d = prepare(synth(n=200, noise=200))
    ev = MM.evaluate_models(d, 26)
    cmp_ = ev["comparison"].set_index("model")
    assert cmp_.loc["improved (adstock + saturation)", "test_rmse"] < cmp_.loc["controls_only (no media)", "test_rmse"]
    spec = ev["spec"]
    fb, X, coef, b, fitted = MM.final_fit(d, spec)
    contrib = {m: coef[m] * X[m].sum() for m in MEDIA}
    assert max(contrib, key=contrib.get) == "spend_paid_search"
    assert spec.lag["spend_paid_search"] in (0, 1, 2)
    true_contrib = 9000 * exp_saturation(geometric_adstock(np.concatenate([[0], d.spend_paid_search.values[:-1]]), 0.5), 1.5 * d.spend_paid_search.mean() * 2).sum()
    assert contrib["spend_paid_search"] == pytest.approx(true_contrib, rel=0.6)


def test_budget_optimiser_respects_constraints():
    cur = np.array([5000.0, 4000, 2000, 1500])
    betas, dec, sc = np.array([9000.0, 3000, 1000, 500]), np.array([0.5, 0.3, 0.2, 0.1]), np.array([8000.0, 6000, 3000, 2000])
    x = B.optimise(cur, cur.sum(), betas, dec, sc, 0.5, 1.5)
    assert x.sum() == pytest.approx(cur.sum(), rel=1e-6)
    assert (x >= cur * 0.5 - 1e-6).all() and (x <= cur * 1.5 + 1e-6).all()
    assert B.response(x, betas, dec, sc) >= B.response(cur, betas, dec, sc) - 1e-6


def test_marginal_return_decreases_with_spend():
    betas, dec, sc = np.array([1000.0]), np.array([0.3]), np.array([5000.0])
    assert B.marginal_return(np.array([1000.0]), betas, dec, sc)[0] > B.marginal_return(np.array([8000.0]), betas, dec, sc)[0]


def test_metrics_match_manual_formulas():
    y, yh = np.array([10.0, 20, 30, 40]), np.array([12.0, 18, 33, 38])
    m = MM.metrics(y, yh)
    assert m["rmse"] == pytest.approx(np.sqrt(np.mean((y - yh) ** 2)))
    assert m["mae"] == pytest.approx(np.mean(np.abs(y - yh)))
    assert m["r2"] == pytest.approx(1 - ((y - yh) ** 2).sum() / ((y - y.mean()) ** 2).sum())


def test_cv_folds_are_chronological():
    from sklearn.model_selection import TimeSeriesSplit
    for tr, va in TimeSeriesSplit(n_splits=3, test_size=20).split(np.arange(120)):
        assert tr.max() < va.min()
