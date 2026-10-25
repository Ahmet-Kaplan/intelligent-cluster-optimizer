"""Seasonal-naive and LightGBM envelopes per decision, same parquet layout as run/forecast.py (CPU).

Usage: uv run python run/baseline_forecast.py [hydra overrides]
LightGBM is cross-fitted: containers are split into 2 folds by id hash; each fold is predicted by models trained
on the *other* fold's uninjected series (seed 0, shape == "none"), so no container is scored by a model that saw it.
"""

import logging
from pathlib import Path

import hydra
import numpy as np
import pandas as pd
from omegaconf import DictConfig

from cgate import SimConfig, decision_steps
from cgate.forecast import QUANTILES
from cgate.holt_winters import hourly_max
from cgate.hourly_baselines import START, LGBMConfig, fit_quantile_models, fold_of, lgbm_predict, seasonal_naive

logger = logging.getLogger(__name__)


def hours_of(mem: np.ndarray, sim: SimConfig) -> np.ndarray:
    return decision_steps(len(mem), sim) // (3600 // sim.step_s)


def frame(cid: str, env: np.ndarray, variant: str) -> pd.DataFrame:
    return pd.DataFrame({"container_id": cid, "k": np.arange(len(env)), "variant": variant,
                         **{f"env_q{q:g}": env[:, i] for i, q in enumerate(QUANTILES)}})


@hydra.main(version_base=None, config_path="../conf", config_name="forecast")
def main(cfg: DictConfig) -> None:
    sim = SimConfig(**cfg.sim)
    root = Path(hydra.utils.to_absolute_path(cfg.prepared_dir))
    out = Path(hydra.utils.to_absolute_path(cfg.baseline_out_dir))
    out.mkdir(parents=True, exist_ok=True)

    train = pd.read_parquet(root / "seed_0" / "series.parquet")
    healthy = set(pd.read_csv(root / "seed_0" / "labels.csv").query("shape == 'none'").container_id)
    by_fold: dict[int, list[np.ndarray]] = {0: [], 1: []}
    for cid, g in train.groupby("container_id"):
        if cid in healthy:
            by_fold[fold_of(cid)].append(hourly_max(g["mem"].to_numpy(float), sim.step_s))
    models = {f: fit_quantile_models(by_fold[1 - f], LGBMConfig()) for f in (0, 1)}
    logger.info("LightGBM trained: fold sizes %s", {f: len(s) for f, s in by_fold.items()})

    for seed in cfg.seeds:
        data = pd.read_parquet(root / f"seed_{seed}" / "series.parquet")
        frames = []
        for cid, g in data.groupby("container_id"):
            mem = g["mem"].to_numpy(float)
            h, hours = hourly_max(mem, sim.step_s), hours_of(mem, sim)
            naive = np.full((len(hours), len(QUANTILES)), np.nan)
            for k, j in enumerate(hours):
                if j >= START:
                    naive[k] = seasonal_naive(h, j)
            frames += [frame(cid, naive, "seasonal_naive"), frame(cid, lgbm_predict(models[fold_of(cid)], h, hours), "lgbm")]
        pd.concat(frames, ignore_index=True).to_parquet(out / f"seed_{seed}.parquet", index=False)
        logger.info("seed %d done", seed)


if __name__ == "__main__":
    main()
