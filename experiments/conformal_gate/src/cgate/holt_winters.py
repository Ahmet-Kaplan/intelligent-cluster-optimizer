"""Port of ICO's Holt-Winters forecaster (pkg/prediction/holt_winters.go, commit 370fc98), additive/additive.

Kept as in Go, including quirks: initial trend divided by m twice; seasonal update uses the *new* level
(paper Eq. 5 uses l_{t-1} + b_{t-1}); grid search by SSE over t >= m; fitModel updates from t >= m - 1 and
counts residuals from t = 0; interval = point +/- z * sigma * sqrt(h) with sigma on n - 3 dof.
The grid search is vectorized over all 900 (alpha, beta, gamma) combinations.
"""

from statistics import NormalDist

import numpy as np


def _go_grid(start: float, stop: float, step: float) -> list[float]:
    """Reproduce Go's float loop `for x := start; x <= stop; x += step`, including accumulation error."""
    out, x = [], start
    while x <= stop:
        out.append(x)
        x += step
    return out


_A, _B, _G = (np.array(v) for v in np.meshgrid(_go_grid(0.1, 0.9, 0.1), _go_grid(0.01, 0.5, 0.05),
                                                 _go_grid(0.01, 0.5, 0.05), indexing="ij"))
ALPHA, BETA, GAMMA = _A.ravel(), _B.ravel(), _G.ravel()


def _init(y: np.ndarray, m: int) -> tuple[float, float, np.ndarray]:
    level = y[:m].mean()
    trend = ((y[m:2 * m] - y[:m]) / m).sum() / m if len(y) >= 2 * m else 0.0
    season = y[:m] - level
    return level, trend, season - season.mean()


def _run(y: np.ndarray, m: int, a: np.ndarray, b: np.ndarray, g: np.ndarray, start: int, sse_from: int):
    """Recursion for len(a) parameter sets at once. Returns (sse, level, trend, season, residuals)."""
    l0, t0, s0 = _init(y, m)
    k = len(a)
    level, trend = np.full(k, l0), np.full(k, t0)
    season = np.tile(s0, (k, 1))
    sse, resid = np.zeros(k), np.zeros((k, len(y)))
    for t in range(len(y)):
        i = t % m
        err = y[t] - (level + trend + season[:, i])
        resid[:, t] = err
        if t >= sse_from:
            sse += err * err
        if t >= start:
            prev = level
            level = a * (y[t] - season[:, i]) + (1 - a) * (level + trend)
            trend = b * (level - prev) + (1 - b) * trend
            season[:, i] = g * (y[t] - level) + (1 - g) * season[:, i]
    return sse, level, trend, season, resid


def fit_predict(y: np.ndarray, m: int = 24, horizon: int = 1, quantiles: tuple[float, ...] = (0.9,)) -> np.ndarray:
    """Fit on y (no NaNs) and return the quantile forecasts at `horizon`, shape (len(quantiles),).

    Raises ValueError with fewer than two seasons, like Go's FitWithTimestamps.
    """
    if len(y) < 2 * m:
        raise ValueError(f"insufficient data: need at least {2 * m} points (2 seasons), got {len(y)}")
    sse, *_ = _run(y, m, ALPHA, BETA, GAMMA, start=m, sse_from=m)  # calculateSSE updates from t = m
    best = int(np.argmin(sse))  # first minimum, matching Go's strict '<'
    _, level, trend, season, resid = _run(y, m, ALPHA[[best]], BETA[[best]], GAMMA[[best]], start=m - 1,
                                          sse_from=len(y))
    sigma = np.sqrt((resid[0] ** 2).sum() / max(len(y) - 3, 1))
    point = level[0] + horizon * trend[0] + season[0, (len(y) + horizon - 1) % m]
    z = np.array([NormalDist().inv_cdf(q) for q in quantiles])
    return point + z * sigma * np.sqrt(horizon)


def hourly_max(u: np.ndarray, step_s: int = 60) -> np.ndarray:
    """Collapse a 60 s series to hourly peaks (the quantity the gate bounds); forward-fill empty hours."""
    per = 3600 // step_s
    n = len(u) // per
    blocks = u[: n * per].reshape(n, per)
    with np.errstate(all="ignore"):
        h = np.where(np.isfinite(blocks).any(axis=1), np.nanmax(np.where(np.isfinite(blocks), blocks, -np.inf), axis=1),
                     np.nan)
    for i in range(1, n):
        if np.isnan(h[i]):
            h[i] = h[i - 1]
    return h
