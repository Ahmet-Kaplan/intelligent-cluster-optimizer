"""Foundation-model quantile envelopes at every decision step, per seed and variant (GPU).

Usage: uv run --extra gpu python run/forecast.py [model=chronos2|toto2_4m|toto2_22m|toto2_313m|timesfm3] [overrides]
Writes <out_dir>/seed_<k>.parquet: container_id, k, t, variant, env_q<level>..., median (list, length H).
Series identical across seeds (uninjected containers) are forecast once and reused.
"""

import hashlib
import logging
import time
from pathlib import Path

import hydra
import numpy as np
import pandas as pd
from omegaconf import DictConfig

from cgate import SimConfig, decision_steps
from cgate.fm_models import fm_envelopes, load_model
from cgate.forecast import QUANTILES, build_inputs, envelopes, load_pipeline

logger = logging.getLogger(__name__)


def series_key(mem: np.ndarray, cpu: np.ndarray, variant: str) -> str:
    h = hashlib.sha1(mem.tobytes() + variant.encode())
    if variant == "covariate":
        h.update(cpu.tobytes())
    return h.hexdigest()


@hydra.main(version_base=None, config_path="../conf", config_name="forecast")
def main(cfg: DictConfig) -> None:
    sim = SimConfig(**cfg.sim)
    is_chronos = cfg.model == "chronos2"
    pipe = load_pipeline(cfg.model_id, cfg.device) if is_chronos else load_model(cfg.model, cfg.device)
    variants = list(cfg.variants) if is_chronos else [cfg.model]  # new FMs: univariate, variant = model name
    root = Path(hydra.utils.to_absolute_path(cfg.prepared_dir))
    out = Path(hydra.utils.to_absolute_path(cfg.out_dir))
    out.mkdir(parents=True, exist_ok=True)
    cache: dict[str, pd.DataFrame] = {}
    for seed in cfg.seeds:
        data = pd.read_parquet(root / f"seed_{seed}" / "series.parquet")
        ids = sorted(data["container_id"].unique())[: cfg.limit_containers]
        frames, t0, fresh, n_fc = [], time.time(), 0, 0
        for cid in ids:
            g = data[data["container_id"] == cid]
            mem, cpu = g["mem"].to_numpy(np.float32), g["cpu"].to_numpy(np.float32)
            steps = decision_steps(len(mem), sim)
            for variant in variants:
                key = series_key(mem, cpu, variant)
                if key not in cache:
                    if is_chronos:
                        items = build_inputs(mem, cpu, steps, cfg.context, variant == "covariate")
                        env, med = envelopes(pipe, items, sim.every_steps, cfg.batch_size)
                    else:
                        ctxs = [mem[max(0, t - cfg.context):t] for t in steps]
                        env, med = fm_envelopes(cfg.model, pipe, ctxs, sim.every_steps, cfg.batch_size)
                    n_fc += len(steps)
                    cache[key] = pd.DataFrame({"k": np.arange(len(steps)), "t": steps, "variant": variant,
                                               **{f"env_q{q:g}": env[:, i] for i, q in enumerate(QUANTILES)},
                                               "median": list(med)})
                    fresh += 1
                frames.append(cache[key].assign(container_id=cid))
        pd.concat(frames, ignore_index=True).to_parquet(out / f"seed_{seed}.parquet", index=False)
        dt = time.time() - t0
        logger.info("seed %d: %d containers, %d new series, %d forecasts, %.1f s (%.2f ms/forecast incl. I/O)",
                    seed, len(ids), fresh, n_fc, dt, 1000 * dt / max(n_fc, 1))


if __name__ == "__main__":
    main()
