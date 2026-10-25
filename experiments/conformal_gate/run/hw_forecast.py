"""Holt-Winters (ICO port) quantile envelopes at each decision, same layout as run/forecast.py (CPU).

Usage: uv run python run/hw_forecast.py [hydra overrides]
Decision k sizes hour j = (warmup + k * every) / 3600 s; HW sees hourly peaks h[:j] with a daily season (m = 24),
the Go DefaultConfig. With fewer than two seasons (first 24 decisions) the envelope is NaN -> cold start.
"""

import hashlib
import logging
from pathlib import Path

import hydra
import numpy as np
import pandas as pd
from omegaconf import DictConfig

from cgate import SimConfig, decision_steps
from cgate.forecast import QUANTILES
from cgate.holt_winters import fit_predict, hourly_max

logger = logging.getLogger(__name__)


def envelopes_hw(mem: np.ndarray, sim: SimConfig, m: int) -> np.ndarray:
    h = hourly_max(mem, sim.step_s)
    per = 3600 // sim.step_s
    out = np.full((len(decision_steps(len(mem), sim)), len(QUANTILES)), np.nan)
    for k, t in enumerate(decision_steps(len(mem), sim)):
        j = t // per
        if j >= 2 * m:
            out[k] = fit_predict(h[:j], m=m, horizon=1, quantiles=QUANTILES)
    return out


@hydra.main(version_base=None, config_path="../conf", config_name="forecast")
def main(cfg: DictConfig) -> None:
    sim = SimConfig(**cfg.sim)
    if (sim.warmup_steps * sim.step_s) % 3600 or (sim.every_steps * sim.step_s) != 3600:
        raise ValueError("HW ablation assumes hourly decisions aligned to hours")
    root = Path(hydra.utils.to_absolute_path(cfg.prepared_dir))
    out = Path(hydra.utils.to_absolute_path(cfg.hw_out_dir))
    out.mkdir(parents=True, exist_ok=True)
    cache: dict[str, np.ndarray] = {}
    for seed in cfg.seeds:
        data = pd.read_parquet(root / f"seed_{seed}" / "series.parquet")
        frames = []
        for cid, g in data.groupby("container_id"):
            mem = g["mem"].to_numpy(np.float64)
            key = hashlib.sha1(mem.tobytes()).hexdigest()
            if key not in cache:
                cache[key] = envelopes_hw(mem, sim, cfg.hw_season)
            env = cache[key]
            frames.append(pd.DataFrame({"container_id": cid, "k": np.arange(len(env)), "variant": "holt_winters",
                                        **{f"env_q{q:g}": env[:, i] for i, q in enumerate(QUANTILES)}}))
        pd.concat(frames, ignore_index=True).to_parquet(out / f"seed_{seed}.parquet", index=False)
        logger.info("seed %d done (%d unique series so far)", seed, len(cache))


if __name__ == "__main__":
    main()
