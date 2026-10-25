"""Conformal risk-gated admission (sections/conformal_gate.tex, Eqs. cqr, admit, aci).

Decision k sizes horizon [t_k, t_k + H) with H = every_steps, so its outcome is known at decision k + 1:
the feedback delay is exactly one decision.
"""

from dataclasses import dataclass
from math import ceil

import numpy as np


@dataclass(frozen=True)
class ConformalConfig:
    eps: float = 0.05     # risk budget eps_c set by the policy engine
    eta: float = 0.005    # ACI step size; 0 = static split conformal (ablation)
    window: int = 168     # calibration scores kept (7 days of hourly decisions)


def peak_targets(u: np.ndarray, steps: np.ndarray, horizon: int) -> np.ndarray:
    """Y_k = max usage over [t_k, t_k + H); NaN when the whole horizon is missing."""
    out = np.full(len(steps), np.nan)
    for k, t in enumerate(steps):
        seg = u[t:t + horizon]
        if np.isfinite(seg).any():
            out[k] = np.nanmax(seg)
    return out


def min_calibration(eps: float) -> int:
    """Smallest n for which the (1 - eps) conformal quantile is finite."""
    return ceil(1 / eps) - 1


def aci_bounds(upper: np.ndarray, y: np.ndarray, cfg: ConformalConfig) -> tuple[np.ndarray, np.ndarray]:
    """Calibrated upper bounds U_k + Q_{1-alpha_k}(scores).

    NaN = cold start (calibration too short, no verdict); +inf = ACI cannot certify any request (alpha <= 0);
    -inf = alpha >= 1 (any request admitted).

    Args:
        upper: forecaster envelope U_k (max over horizon of the tau_0 quantile).
        y: realized peaks Y_k (only Y_j for j < k is used at decision k).
    Returns:
        (bounds, alphas). ACI updates start once calibration is long enough, so cold start does not drift alpha.
    """
    n_dec = len(upper)
    bounds, alphas = np.full(n_dec, np.nan), np.full(n_dec, np.nan)
    alpha, scores = cfg.eps, list[float]()
    for k in range(n_dec):
        if k > 0 and np.isfinite(y[k - 1]) and np.isfinite(upper[k - 1]):
            if not np.isnan(bounds[k - 1]):  # any verdict incl. +/-inf (y > +inf is never an error) -> ACI step
                alpha += cfg.eta * (cfg.eps - float(y[k - 1] > bounds[k - 1]))
            scores = (scores + [y[k - 1] - upper[k - 1]])[-cfg.window:]
        n = len(scores)
        if n < min_calibration(cfg.eps) or not np.isfinite(upper[k]):
            continue
        alphas[k] = alpha
        if alpha >= 1:
            bounds[k] = -np.inf
            continue
        rank = ceil((n + 1) * (1 - alpha)) if alpha > 0 else n + 1
        bounds[k] = upper[k] + np.sort(scores)[rank - 1] if rank <= n else np.inf
    return bounds, alphas


MIN_REQUEST = 0.05  # % of machine memory, about ICO's 32 MiB floor on a 64 GB machine


def gate_requests(candidate: np.ndarray, bounds: np.ndarray, mode: str,
                  floor: float = MIN_REQUEST) -> tuple[np.ndarray, np.ndarray]:
    """Apply the admission rule R >= U_hat to candidate requests.

    mode: "modify" raises a rejected candidate to the bound (policy action *modify*);
          "veto" keeps the previous request; "size" uses the bound itself as the request (B4, BACC-like, no veto).
    NaN bound (cold start): the candidate passes through and is flagged for human approval.
    +inf bound (cannot certify): no scale-down is allowed, the request never drops below the previous one.
    -inf bound: everything is admitted.
    Returns (requests, needs_approval).
    """
    if mode not in ("modify", "veto", "size"):
        raise ValueError(f"unknown mode {mode!r}")
    req, cold = np.empty(len(candidate)), np.isnan(bounds)
    prev = np.nan
    for k, (r, b) in enumerate(zip(candidate, bounds)):
        if cold[k] or b == -np.inf:
            out = r
        elif b == np.inf:
            out = max(r, prev) if np.isfinite(prev) else r
        elif mode == "size":
            out = max(b, floor)  # a forecast can go non-positive; requests never do
        elif r >= b:
            out = r
        elif mode == "modify":
            out = b
        else:
            out = prev if np.isfinite(prev) else b
        req[k] = prev = out
    return req, cold
