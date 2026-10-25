"""Chronos-2 quantile envelopes at each decision step (GPU). torch/chronos are imported lazily."""

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

QUANTILES = (0.5, 0.8, 0.9, 0.95, 0.99)


def build_inputs(mem: np.ndarray, cpu: np.ndarray, steps: np.ndarray, context: int, covariate: bool) -> list[dict]:
    """One Chronos-2 input per decision step, using only data before t (no look-ahead)."""
    items = []
    for t in steps:
        lo = max(0, t - context)
        item: dict[str, Any] = {"target": mem[lo:t].astype(np.float32)}
        if covariate:
            item["past_covariates"] = {"cpu": cpu[lo:t].astype(np.float32)}
        items.append(item)
    return items


def envelopes(pipe: Any, items: list[dict], horizon: int, batch_size: int = 256) -> tuple[np.ndarray, np.ndarray]:
    """Return (max over horizon of each quantile, shape (n, len(QUANTILES))) and median paths (n, horizon)."""
    q, _ = pipe.predict_quantiles(items, prediction_length=horizon, quantile_levels=list(QUANTILES),
                                  batch_size=batch_size)
    arr = np.stack([x[0].float().cpu().numpy() for x in q])  # (n, horizon, n_q); variate 0 = target
    return arr.max(axis=1), arr[:, :, QUANTILES.index(0.5)]


def load_pipeline(model_id: str = "amazon/chronos-2", device: str = "cuda") -> Any:
    from chronos import Chronos2Pipeline

    logger.info("loading %s on %s", model_id, device)
    return Chronos2Pipeline.from_pretrained(model_id, device_map=device)
