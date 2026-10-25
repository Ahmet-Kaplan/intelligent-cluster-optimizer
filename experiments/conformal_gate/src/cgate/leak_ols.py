"""Port of the ICO regression leak detector (pkg/leakdetector/detector.go, commit 370fc98).

Same decision chain as `detectLeak`: slope > threshold, R^2 >= 0.7, resets <= 2, growth >= 10 %.
Memory here is percent of machine memory (Alibaba units), so the Go byte threshold is converted
with an assumed machine size; see `OLSLeakConfig.machine_mem_gb`.
"""

from dataclasses import dataclass

import numpy as np

MIB = 1024 * 1024


@dataclass(frozen=True)
class OLSLeakConfig:
    min_samples: int = 20
    min_duration_h: float = 1.0
    slope_threshold_bytes_per_h: float = 1 * MIB
    reset_threshold: float = 0.15
    max_resets: int = 2
    r2_threshold: float = 0.7
    growth_threshold: float = 0.10
    # Assumption, not trace data: Alibaba v2018 normalizes machine memory. The 1 MiB/h threshold is
    # non-binding for any realistic size (>= 8 GB gives < 0.013 %/h); test_ols_slope_threshold_nonbinding.
    machine_mem_gb: float = 64.0


def ols_slope_r2(t_h: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """Least-squares slope (units of y per hour) and R^2 clamped to [0, 1], as in calculateLinearRegression."""
    n = len(y)
    if n < 2:
        return 0.0, 0.0
    sx, sy = t_h.sum(), y.sum()
    den = n * (t_h @ t_h) - sx * sx
    if den == 0:
        return 0.0, 0.0
    slope = (n * (t_h @ y) - sx * sy) / den
    intercept = (sy - slope * sx) / n
    ss_tot = ((y - sy / n) ** 2).sum()
    ss_res = ((y - intercept - slope * t_h) ** 2).sum()
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return float(slope), float(min(max(r2, 0.0), 1.0))


def count_resets(y: np.ndarray, threshold: float) -> int:
    resets, peak = 0, y[0]
    for v in y[1:]:
        peak = max(peak, v)
        if peak > 0 and (peak - v) / peak >= threshold:
            resets += 1
            peak = v
    return resets


def is_leak(mem_pct: np.ndarray, step_s: int, cfg: OLSLeakConfig) -> bool:
    """Leak verdict on one window of evenly spaced samples (NaNs dropped first, as missing samples)."""
    ok = ~np.isnan(mem_pct)
    y = mem_pct[ok]
    t_h = np.flatnonzero(ok) * step_s / 3600.0
    if len(y) < cfg.min_samples or t_h[-1] - t_h[0] < cfg.min_duration_h:
        return False
    slope, r2 = ols_slope_r2(t_h - t_h[0], y)
    slope_bytes = slope / 100.0 * cfg.machine_mem_gb * 1024**3
    if slope_bytes <= cfg.slope_threshold_bytes_per_h or r2 < cfg.r2_threshold:
        return False
    if count_resets(y, cfg.reset_threshold) > cfg.max_resets:
        return False
    return y[0] > 0 and (y[-1] - y[0]) / y[0] >= cfg.growth_threshold
