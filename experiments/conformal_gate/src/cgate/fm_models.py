"""Toto 2.0 and TimesFM 3.0 behind the same envelope interface as forecast.envelopes (GPU, lazy imports).

Both models emit the nine deciles 0.1..0.9, so env_q0.95 / env_q0.99 are NaN for them; the gate uses tau0 = 0.9.
Univariate only: Toto 2.0 has no exogenous inputs, and the CPU covariate gave no sizing gain with Chronos-2.
"""

import logging
from typing import Any

import numpy as np

from .forecast import QUANTILES

logger = logging.getLogger(__name__)

DECILES = tuple(round(0.1 * i, 1) for i in range(1, 10))
TOTO_SIZES = ("4m", "22m", "313m", "1b", "2.5b")


def from_deciles(paths: np.ndarray) -> np.ndarray:
    """(n, H, 9) decile paths -> (n, H, len(QUANTILES)), NaN for levels the model does not produce."""
    out = np.full((*paths.shape[:2], len(QUANTILES)), np.nan, dtype=np.float32)
    for j, q in enumerate(QUANTILES):
        if q in DECILES:
            out[:, :, j] = paths[:, :, DECILES.index(q)]
    return out


TOTO_PATCH = 32  # Toto 2.0 needs the padded length to be a multiple of its patch size


def left_pad(contexts: list[np.ndarray], multiple: int = 1) -> tuple[np.ndarray, np.ndarray]:
    """Stack variable-length contexts, left-padded to a multiple of `multiple`; NaNs and padding are masked out."""
    n = -(-max(len(c) for c in contexts) // multiple) * multiple
    x = np.zeros((len(contexts), n), dtype=np.float32)
    mask = np.zeros((len(contexts), n), dtype=bool)
    for i, c in enumerate(contexts):
        ok = np.isfinite(c)
        x[i, n - len(c):] = np.where(ok, c, 0.0)
        mask[i, n - len(c):] = ok
    return x, mask


def ffill(c: np.ndarray) -> np.ndarray:
    """Forward-fill NaNs (back-fill a leading gap) for models without a missing-value mask."""
    s = c.astype(np.float32).copy()
    idx = np.where(np.isfinite(s), np.arange(len(s)), 0)
    np.maximum.accumulate(idx, out=idx)
    s = s[idx]
    first = np.flatnonzero(np.isfinite(s))
    if len(first):
        s[: first[0]] = s[first[0]]
    return s


def load_model(name: str, device: str = "cuda") -> Any:
    if name.startswith("toto2_"):
        size = name.removeprefix("toto2_")
        if size not in TOTO_SIZES:
            raise ValueError(f"unknown Toto 2.0 size {size!r}; expected one of {TOTO_SIZES}")
        from toto2 import Toto2Model

        logger.info("loading Datadog/Toto-2.0-%s on %s", size, device)
        return Toto2Model.from_pretrained(f"Datadog/Toto-2.0-{size}").to(device).eval()
    if name == "timesfm3":
        from timesfm import TimesFM3Forecaster

        logger.info("loading google/timesfm-3.0-pytorch on %s", device)
        return TimesFM3Forecaster.from_pretrained("google/timesfm-3.0-pytorch", device=device)
    raise ValueError(f"unknown model {name!r}")


def decile_paths(name: str, model: Any, contexts: list[np.ndarray], horizon: int, batch_size: int) -> np.ndarray:
    """Decile forecast paths, shape (n, horizon, 9)."""
    if name == "timesfm3":
        outs = model.predict_batch([ffill(c) for c in contexts], horizon=horizon, return_quantiles=True)
        return np.stack([np.asarray(o.quantiles, dtype=np.float32) for o in outs])
    import torch

    device = next(model.parameters()).device
    parts = []
    for i in range(0, len(contexts), batch_size):
        x, m = left_pad(contexts[i:i + batch_size], TOTO_PATCH)
        inputs = {"target": torch.from_numpy(x)[:, None, :].to(device),
                  "target_mask": torch.from_numpy(m)[:, None, :].to(device),
                  "series_ids": torch.zeros(len(x), 1, dtype=torch.long, device=device)}
        with torch.no_grad():
            q = model.forecast(inputs, horizon=horizon, decode_block_size=None, has_missing_values=True)
        parts.append(q[:, :, 0, :].permute(1, 2, 0).float().cpu().numpy())  # (9, B, 1, H) -> (B, H, 9)
    return np.concatenate(parts)


def fm_envelopes(name: str, model: Any, contexts: list[np.ndarray], horizon: int,
                 batch_size: int = 256) -> tuple[np.ndarray, np.ndarray]:
    """Same contract as forecast.envelopes: (max over horizon per quantile, median paths)."""
    paths = from_deciles(decile_paths(name, model, contexts, horizon, batch_size))
    return paths.max(axis=1), paths[:, :, QUANTILES.index(0.5)]
