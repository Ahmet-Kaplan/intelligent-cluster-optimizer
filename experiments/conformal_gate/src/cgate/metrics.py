"""Sizing and leak-gate metrics for one container, given a policy's decisions."""

import numpy as np

from .baselines import SimConfig, decision_steps


def sizing_metrics(u: np.ndarray, req: np.ndarray, cfg: SimConfig) -> dict[str, float]:
    """Slack and violation rate over the decision horizons.

    slack: time-averaged (request - usage) / request (Autopilot's metric).
    violation_rate: fraction of horizons whose peak usage exceeds the request (request exceedance; an OOM only if limit = request).
    Horizons with no request yet (NaN) are skipped.
    """
    slack, viol, changes, prev = [], [], 0, np.nan
    for t, r in zip(decision_steps(len(u), cfg), req):
        if not np.isfinite(r):
            continue
        seg = u[t:t + cfg.every_steps]
        seg = seg[~np.isnan(seg)]
        if len(seg) == 0:
            continue
        # A non-positive request is counted (as a violation with zero slack), never skipped.
        slack.append(float(np.mean((r - seg) / r)) if r > 0 else 0.0)
        viol.append(bool(seg.max() > r))
        changes += np.isfinite(prev) and not np.isclose(r, prev)
        prev = r
    n = len(viol)
    return {"slack": float(np.mean(slack)) if n else np.nan,
            "violation_rate": float(np.mean(viol)) if n else np.nan,
            "changes": changes, "horizons": n}


def gate_metrics(blocked: np.ndarray, label: int, onset: int, n: int, cfg: SimConfig) -> dict[str, float]:
    """Leak-gate outcome for one container.

    Decisions before `onset` (or all, for healthy containers) are healthy; any block there is a false block.
    detected / delay_h only apply to leak containers (label 1).
    """
    steps = decision_steps(n, cfg)
    healthy = steps < onset if label == 1 else np.ones(len(steps), dtype=bool)
    after = ~healthy
    first = np.flatnonzero(blocked & after)
    return {
        "healthy_decisions": int(healthy.sum()),
        "false_blocks": int((blocked & healthy).sum()),
        "detected": bool(len(first)) if label == 1 else np.nan,
        "delay_h": float((steps[first[0]] - onset) * cfg.step_s / 3600) if label == 1 and len(first) else np.nan,
    }
