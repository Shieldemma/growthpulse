"""Media transformations: carryover (adstock) and diminishing returns (saturation)."""
from __future__ import annotations

import numpy as np


def geometric_adstock(x, decay: float) -> np.ndarray:
    """a_t = x_t + decay * a_{t-1}.  Causal: a_t depends only on x_0..x_t (no future information).
    decay in [0, 1): 0 = no carryover; 0.5 = half of last week's effect persists into this week."""
    if not 0 <= decay < 1:
        raise ValueError("decay must be in [0, 1)")
    x = np.asarray(x, dtype=float)
    out = np.empty_like(x)
    carry = 0.0
    for i, v in enumerate(x):
        carry = v + decay * carry
        out[i] = carry
    return out


def exp_saturation(x, scale: float) -> np.ndarray:
    """1 - exp(-x / scale): rises steeply at first, flattens toward 1 (diminishing returns). scale > 0."""
    if scale <= 0:
        raise ValueError("scale must be positive")
    return 1.0 - np.exp(-np.asarray(x, dtype=float) / scale)


def steady_state_adstock(weekly_spend: float, decay: float) -> float:
    """Adstock level when the same weekly spend is sustained: s / (1 - decay)."""
    return weekly_spend / (1.0 - decay)
