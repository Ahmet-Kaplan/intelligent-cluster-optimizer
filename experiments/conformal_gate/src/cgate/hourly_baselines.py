"""Non-FM baselines on hourly peaks: seasonal-naive quantiles and a global LightGBM quantile model.

Both predict the peak of hour j from hours < j and start at j = 48, the same start as Holt-Winters.
"""

import zlib
from dataclasses import dataclass

import numpy as np

from .forecast import QUANTILES

SEASON = 24
START = 2 * SEASON
RESID_WINDOW = 168


def seasonal_naive(h: np.ndarray, j: int) -> np.ndarray:
    """Point = same hour yesterday; quantiles from the last <= 7 days of seasonal-difference residuals."""
    lo = max(SEASON, j - RESID_WINDOW)
    resid = h[lo:j] - h[lo - SEASON:j - SEASON]
    return h[j - SEASON] + np.quantile(resid, QUANTILES)


N_FEATURES = SEASON + 5


def features(h: np.ndarray, j: int) -> np.ndarray:
    """Scale-free features for predicting h[j] / h[j-1]: 24 lag ratios, 24 h mean/std/max/min ratios, hour of day."""
    ref = max(h[j - 1], 1e-3)
    last = h[j - SEASON:j] / ref
    return np.concatenate([last[::-1], [last.mean(), last.std(), last.max(), last.min(), j % SEASON]])


def fold_of(container_id: str, n_folds: int = 2) -> int:
    return zlib.crc32(container_id.encode()) % n_folds


@dataclass(frozen=True)
class LGBMConfig:
    n_estimators: int = 300
    learning_rate: float = 0.05
    num_leaves: int = 31
    min_child_samples: int = 50
    seed: int = 0


def training_rows(series: list[np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    X, y = [], []
    for h in series:
        for j in range(START, len(h)):
            X.append(features(h, j))
            y.append(h[j] / max(h[j - 1], 1e-3))
    return np.asarray(X), np.asarray(y)


def fit_quantile_models(series: list[np.ndarray], cfg: LGBMConfig) -> list:
    """One LightGBM model per level in QUANTILES, trained on ratio targets."""
    import lightgbm as lgb

    X, y = training_rows(series)
    data = lgb.Dataset(X, y, free_raw_data=False)
    params = {"objective": "quantile", "learning_rate": cfg.learning_rate, "num_leaves": cfg.num_leaves,
              "min_child_samples": cfg.min_child_samples, "seed": cfg.seed, "deterministic": True,
              "force_row_wise": True, "num_threads": 4, "verbose": -1}  # >4 threads spin-wait on small predicts
    return [lgb.train({**params, "alpha": q}, data, num_boost_round=cfg.n_estimators) for q in QUANTILES]


def lgbm_predict(models: list, h: np.ndarray, hours: np.ndarray) -> np.ndarray:
    """Quantile forecasts (len(hours), len(QUANTILES)); NaN before START; crossing fixed by sorting."""
    out = np.full((len(hours), len(QUANTILES)), np.nan)
    ok = hours >= START
    if ok.any():
        X = np.stack([features(h, j) for j in hours[ok]])
        ratio = np.sort(np.column_stack([m.predict(X) for m in models]), axis=1)
        out[ok] = ratio * np.maximum(h[hours[ok] - 1], 1e-3)[:, None]
    return out
