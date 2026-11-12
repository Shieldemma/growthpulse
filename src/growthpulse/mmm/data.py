"""MMM data preparation: loading, calendar features, chronological split and a LEAKAGE-FREE feature builder."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .transforms import exp_saturation, geometric_adstock

MEDIA = ["spend_paid_search", "spend_paid_social", "spend_display", "spend_affiliate"]
CONTROLS = ["trend", "sin1", "cos1", "sin2", "cos2", "promo_share"]
TARGET = "new_mrr_usd"
BURN_IN_WEEKS = 4        # first weeks lack trial-lag inflow and adstock history
TEST_WEEKS = 26


def prepare(df: pd.DataFrame, burn_in: int = BURN_IN_WEEKS) -> pd.DataFrame:
    """Sort, drop incomplete weeks and burn-in, add trend + Fourier seasonality. Raises on gaps or missing columns."""
    need = ["week_start", TARGET, "promo_share", *MEDIA]
    missing = [c for c in need if c not in df.columns]
    if missing:
        raise ValueError(f"MMM input is missing columns: {missing}")
    d = df.copy()
    d["week_start"] = pd.to_datetime(d["week_start"])
    d = d.sort_values("week_start").reset_index(drop=True)
    if "is_complete_week" in d:
        d = d[d.is_complete_week == 1].reset_index(drop=True)
    gaps = d.week_start.diff().dropna().dt.days.unique()
    if len(gaps) > 1 or (len(gaps) == 1 and gaps[0] != 7):
        raise ValueError(f"weekly series has gaps (day-differences seen: {sorted(gaps)})")
    if d[[TARGET, *MEDIA]].isna().any().any():
        raise ValueError("MMM input contains missing values in outcome or spend")
    d["week_index"] = np.arange(len(d))
    doy = d.week_start.dt.dayofyear.values + 3  # mid-week
    d["trend"] = d.week_index / 52.0
    for k in (1, 2):
        d[f"sin{k}"] = np.sin(2 * np.pi * k * doy / 365.25)
        d[f"cos{k}"] = np.cos(2 * np.pi * k * doy / 365.25)
    return d.iloc[burn_in:].reset_index(drop=True).assign(week_index=lambda x: np.arange(len(x)))


def chronological_split(df: pd.DataFrame, test_weeks: int = TEST_WEEKS):
    """Train = everything before the last `test_weeks`; test = the last `test_weeks`. NEVER shuffled."""
    if test_weeks >= len(df) - 20:
        raise ValueError("not enough weeks for a train/test split")
    cut = len(df) - test_weeks
    return df.iloc[:cut].copy(), df.iloc[cut:].copy()


@dataclass
class Spec:
    """Hyper-parameters of the transformed model."""
    decay: dict = field(default_factory=lambda: {m: 0.3 for m in MEDIA})
    scale_mult: dict = field(default_factory=lambda: {m: 1.5 for m in MEDIA})
    lag: dict = field(default_factory=lambda: {m: 0 for m in MEDIA})   # weeks between spend and its first effect

    def copy(self):
        return Spec(dict(self.decay), dict(self.scale_mult), dict(self.lag))


class FeatureBuilder:
    """Builds the design matrix. `fit` learns ONLY from training rows (saturation scales), so test/future
    weeks cannot influence anything the model learns. Adstock is causal by construction."""

    def __init__(self, spec: Spec | None = None, transform: bool = True):
        self.spec, self.transform = spec or Spec(), transform
        self.scales_: dict[str, float] = {}

    def _ads(self, df: pd.DataFrame) -> pd.DataFrame:
        out = {}
        for m in MEDIA:
            x = df[m].values.astype(float)
            L = int(self.spec.lag[m])
            if L > 0:                      # delay: week t sees spend from week t-L (past only; zeros before the series starts)
                x = np.concatenate([np.zeros(L), x[:-L]])
            out[m] = geometric_adstock(x, self.spec.decay[m])
        return pd.DataFrame(out, index=df.index)

    def fit(self, df: pd.DataFrame, train_idx) -> "FeatureBuilder":
        if self.transform:
            ads = self._ads(df)
            self.scales_ = {m: self.spec.scale_mult[m] * float(ads.loc[train_idx, m].mean()) for m in MEDIA}
        return self

    def matrix(self, df: pd.DataFrame) -> pd.DataFrame:
        if self.transform:
            ads = self._ads(df)
            media = pd.DataFrame({m: exp_saturation(ads[m].values, self.scales_[m]) for m in MEDIA}, index=df.index)
        else:
            media = df[MEDIA].copy()
        return pd.concat([media, df[CONTROLS]], axis=1)
