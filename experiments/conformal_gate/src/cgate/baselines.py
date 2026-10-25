"""Baseline sizing policies replayed on one usage series.

Every policy decides a request at steps t = warmup, warmup + every, ... using only usage[:t]
(no look-ahead) and holds it until the next decision. NaN = no decision possible yet.
"""

from dataclasses import dataclass

import numpy as np

from .leak_ols import OLSLeakConfig, is_leak


@dataclass(frozen=True)
class SimConfig:
    step_s: int = 60
    warmup_steps: int = 1440   # 1 day of history before the first decision
    every_steps: int = 60      # decide hourly; also the evaluation horizon H


def decision_steps(n: int, cfg: SimConfig) -> np.ndarray:
    return np.arange(cfg.warmup_steps, n - cfg.every_steps + 1, cfg.every_steps)


def fixed_headroom(u: np.ndarray, cfg: SimConfig, q: float = 95, factor: float = 1.5) -> np.ndarray:
    """B2 (reviewer S4): percentile of all history times a fixed headroom; no gates."""
    return np.array([np.nanpercentile(u[:t], q) * factor for t in decision_steps(len(u), cfg)])


def vpa(u: np.ndarray, cfg: SimConfig, q: float = 90, margin: float = 1.15, half_life_h: float = 24) -> np.ndarray:
    """B1: Kubernetes VPA recommender target, P90 of exponentially decayed history x 1.15.

    ponytail: exact weighted percentile instead of VPA's bucketed histogram, and per-sample memory instead of
    per-interval peaks. Upgrade to the histogram + peak aggregation if B1 lands close to P on any metric.
    """
    out = []
    for t in decision_steps(len(u), cfg):
        x = u[:t]
        ok = ~np.isnan(x)
        age_h = (t - np.flatnonzero(ok)) * cfg.step_s / 3600.0
        w = 0.5 ** (age_h / half_life_h)
        order = np.argsort(x[ok])
        cw = np.cumsum(w[order])
        i = min(int(np.searchsorted(cw, q / 100 * cw[-1])), len(cw) - 1)
        out.append(x[ok][order][i] * margin)
    return np.array(out)


def ico(u: np.ndarray, cfg: SimConfig, leak_cfg: OLSLeakConfig | None, history_steps: int = 60,
        q: float = 95, margin: float = 1.2, leak_window_steps: int = 360) -> tuple[np.ndarray, np.ndarray]:
    """B3: current ICO engine (P95 over the last 1 h x 1.2), optionally gated by the OLS leak detector.

    The detector gets its own window: the Go code never wires it to the engine, and its 1 h MinDuration
    (first-to-last sample) rejects every 1 h window. The window sets recall via the 10 % growth rule, so sweep it.
    A blocked decision keeps the previous request (the change is not applied).
    Returns (requests, blocked flags).
    """
    steps = decision_steps(len(u), cfg)
    req, blocked = np.empty(len(steps)), np.zeros(len(steps), dtype=bool)
    prev = np.nan
    for k, t in enumerate(steps):
        window = u[max(0, t - history_steps):t]
        rec = np.nanpercentile(window, q) * margin if np.isfinite(window).any() else prev
        if leak_cfg is not None and is_leak(u[max(0, t - leak_window_steps):t], cfg.step_s, leak_cfg):
            blocked[k] = True
            rec = prev
        req[k] = prev = rec
    return req, blocked


def _weighted_pct(x: np.ndarray, w: np.ndarray, q: float) -> float:
    order = np.argsort(x)
    cw = np.cumsum(w[order])
    return float(x[order][min(int(np.searchsorted(cw, q / 100 * cw[-1])), len(cw) - 1)])


def vpa_faithful(u: np.ndarray, cfg: SimConfig, q: float = 90, margin: float = 1.15, half_life_h: float = 24,
                 interval_h: int = 24, intervals: int = 8, min_lifetime_h: float = 12,
                 min_change: float = 0.10) -> np.ndarray:
    """B1': VPA recommender and updater semantics (kubernetes/autoscaler defaults).

    Recommender: decaying (24 h half-life) distribution of per-interval memory peaks over 8 x 24 h intervals;
    target = P_q x 1.15, lower = P50 x 1.15, upper = P95 x 1.15 x (1 + 1/confidence), confidence in days.
    Updater: the request (set at pod creation) changes only when it leaves [lower, upper], or when the pod has
    lived >= 12 h and the target differs by more than 10%.
    ponytail: exact weighted percentiles instead of exponential buckets, and intervals end at the decision
    instead of being wall-clock aligned.
    """
    per_interval = interval_h * 3600 // cfg.step_s
    out, cur, since = [], np.nan, 0.0
    for t in decision_steps(len(u), cfg):
        peaks, ages = [], []
        for i in range(intervals):
            seg = u[max(0, t - (i + 1) * per_interval):t - i * per_interval]
            seg = seg[~np.isnan(seg)]
            if len(seg):
                peaks.append(seg.max())
                ages.append(i * interval_h)
        if not peaks:
            out.append(cur)
            continue
        x, w = np.array(peaks), 0.5 ** (np.array(ages) / half_life_h)
        conf = max(t * cfg.step_s / 86400.0, 1e-3)
        target = _weighted_pct(x, w, q) * margin
        lower = _weighted_pct(x, w, 50) * margin * (1 + 0.001 / conf) ** -2
        upper = _weighted_pct(x, w, 95) * margin * (1 + 1 / conf)
        since += cfg.every_steps * cfg.step_s / 3600
        if not np.isfinite(cur) or not lower <= cur <= upper or \
                (since >= min_lifetime_h and abs(target - cur) > min_change * cur):
            if cur != target:
                since = 0.0
            cur = target
        out.append(cur)
    return np.array(out)


def error_padding(upper: np.ndarray, y: np.ndarray, n: int) -> np.ndarray:
    """B5: CloudScale-style padding: envelope plus the largest under-prediction of the last n matured decisions.

    Decision k sees outcomes y[:k] (one-decision feedback delay, as the gate). NaN until one outcome exists.
    """
    req = np.full(len(upper), np.nan)
    for k in range(1, len(upper)):
        res = (y - upper)[max(0, k - n):k]
        res = res[np.isfinite(res)]
        if len(res):
            req[k] = upper[k] + max(res.max(), 0.0)
    return req
