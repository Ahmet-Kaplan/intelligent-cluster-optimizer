"""Conformal-martingale leak gate (sections/conformal_gate.tex, Eqs. pvalue, martingale, ville).

Scores arrive one per decision and must only use data available before that decision.
Large scores = evidence of a leak -> small p-values -> the martingale grows.
"""

import numpy as np

KAPPAS = np.linspace(0.01, 0.99, 99)  # grid for the mixture over the power-martingale betting parameter


def smoothed_pvalues(scores: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Online smoothed conformal p-values: p_k ranks s_k among s_0..s_k (larger score -> smaller p).

    Under exchangeability of the scores these p-values are i.i.d. U(0, 1) (Vovk et al. 2005).
    NaN scores yield NaN p-values and are skipped by the martingales.
    """
    p = np.full(len(scores), np.nan)
    seen: list[float] = []
    for k, s in enumerate(scores):
        if not np.isfinite(s):
            continue
        seen.append(s)
        arr = np.asarray(seen)
        p[k] = (np.sum(arr > s) + rng.uniform() * np.sum(arr == s)) / len(arr)
    return p


def log_mixture_martingale(p: np.ndarray, cusum: bool = False) -> np.ndarray:
    """log S_k of the simple mixture power martingale S_k = mean_kappa prod_i kappa * p_i^(kappa - 1).

    cusum=True floors each per-kappa log-wealth at 0 before every bet (conformal CUSUM): faster after long
    healthy stretches, but the guarantee becomes an average-run-length bound instead of Ville's inequality.
    """
    log_w = np.zeros(len(KAPPAS))
    out = np.full(len(p), np.nan)
    for k, pk in enumerate(p):
        if np.isfinite(pk):
            if cusum:
                log_w = np.maximum(log_w, 0.0)
            log_w = log_w + np.log(KAPPAS) + (KAPPAS - 1) * np.log(max(pk, 1e-12))
        m = log_w.max()
        out[k] = m + np.log(np.mean(np.exp(log_w - m)))
    return out


def recent_slope(h: np.ndarray, j: int, window: int = 6) -> float:
    """OLS slope of the last `window` hourly peaks before hour j (directional confirmation)."""
    y = h[max(0, j - window):j]
    if len(y) < 3 or not np.isfinite(y).all():
        return np.nan
    t = np.arange(len(y), dtype=float)
    return float(np.polyfit(t, y, 1)[0])


def leak_blocks(log_s: np.ndarray, slopes: np.ndarray, lam: float) -> np.ndarray:
    """Veto rule: martingale above 1 / lambda and recent trend upward."""
    return (log_s >= np.log(1.0 / lam)) & (np.nan_to_num(slopes, nan=0.0) > 0)


def apply_blocks(candidate: np.ndarray, blocked: np.ndarray) -> np.ndarray:
    """A blocked decision keeps the previous request (the scale-up is not applied)."""
    req, prev = np.empty(len(candidate)), np.nan
    for k, (r, b) in enumerate(zip(candidate, blocked)):
        req[k] = prev = prev if (b and np.isfinite(prev)) else r
    return req


def thin_scores(scores: np.ndarray, block: int) -> np.ndarray:
    """Block means over non-overlapping windows of `block` decisions, emitted at each block's last decision.

    Other decisions get NaN, so the martingale holds its value between blocks. Fewer, less correlated
    observations trade detection delay for exchangeability. A block with any NaN is skipped.
    """
    if block <= 1:
        return scores.copy()
    out = np.full(len(scores), np.nan)
    for end in range(block - 1, len(scores), block):
        win = scores[end - block + 1:end + 1]
        if np.isfinite(win).all():
            out[end] = win.mean()
    return out


def lag1_autocorr(x: np.ndarray) -> float:
    """Lag-1 autocorrelation of the finite values in order (NaN if fewer than 4)."""
    v = x[np.isfinite(x)]
    if len(v) < 4 or v.std() == 0:
        return np.nan
    return float(np.corrcoef(v[:-1], v[1:])[0, 1])
