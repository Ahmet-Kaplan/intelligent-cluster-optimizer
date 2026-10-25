"""Build the evaluation set: load trace -> select containers -> inject leaks / hard negatives per seed.

Usage: uv run python run/prepare.py [hydra overrides]
Writes <out_dir>/seed_<k>/series.parquet (long format) and labels.csv (ground truth).
"""

import logging
from pathlib import Path

import hydra
import numpy as np
import pandas as pd
from omegaconf import DictConfig

from cgate import (
    LEAK_SHAPES,
    NEGATIVE_SHAPES,
    SelectionConfig,
    inject_leak,
    inject_negative,
    load_alibaba,
    ramp,
    resample,
    select,
)

logger = logging.getLogger(__name__)


def build_seed(series: dict[str, pd.DataFrame], ids: list[str], cfg: DictConfig, seed: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    step = cfg.data.step_s
    order = rng.permutation(ids)
    n_leak = round(cfg.injection.leak_prevalence * len(ids))
    n_neg = round(cfg.injection.negative_frac * (len(ids) - n_leak))
    frames, labels = [], []
    for k, cid in enumerate(order):
        df = series[cid]
        mem, cpu = df["mem"].to_numpy(), df["cpu"].to_numpy()
        # Onset in the second half so the gate has a healthy calibration period first.
        onset = int(rng.integers(len(mem) // 2, len(mem) - 6 * 3600 // step))
        if k < n_leak:
            inj = inject_leak(mem, cpu, str(rng.choice(LEAK_SHAPES)), float(rng.choice(cfg.injection.leak_rates)),
                              onset, step, rng)
        elif k < n_leak + n_neg:
            shape = str(rng.choice(NEGATIVE_SHAPES))
            inj = inject_negative(mem, cpu, shape, onset, step_s=step)
            if shape == "load_growth":
                cpu = cpu * (1 + 0.3 * ramp(len(cpu), onset, step))
        else:
            inj = None
        frames.append(pd.DataFrame({"container_id": cid, "t": df.index, "cpu": cpu,
                                    "mem": inj.mem if inj else mem}))
        labels.append({"container_id": cid, "label": inj.label if inj else 0,
                       "shape": inj.shape if inj else "none", "onset": inj.onset if inj else -1,
                       "rate_per_hour": inj.rate_per_hour if inj else 0.0})
    return pd.concat(frames, ignore_index=True), pd.DataFrame(labels)


@hydra.main(version_base=None, config_path="../conf", config_name="config")
def main(cfg: DictConfig) -> None:
    path = cfg.data.alibaba_path
    raw = load_alibaba(path if path == "-" else Path(hydra.utils.to_absolute_path(path)),
                       chunksize=cfg.data.chunksize, keep_frac=cfg.data.keep_frac, bin_s=cfg.data.step_s)
    series = resample(raw, cfg.data.step_s)
    chosen = select(series, SelectionConfig(**cfg.selection), cfg.data.step_s)
    out = Path(hydra.utils.to_absolute_path(cfg.out_dir))
    out.mkdir(parents=True, exist_ok=True)
    chosen.to_csv(out / "selected_containers.csv", index=False)
    logger.info("selected %d containers", len(chosen))
    for seed in cfg.injection.seeds:
        d = out / f"seed_{seed}"
        d.mkdir(exist_ok=True)
        data, labels = build_seed(series, chosen["container_id"].tolist(), cfg, seed)
        data.to_parquet(d / "series.parquet", index=False)
        labels.to_csv(d / "labels.csv", index=False)
        logger.info("seed %d: %d leaks, %d hard negatives", seed,
                    labels["label"].sum(), labels["shape"].isin(NEGATIVE_SHAPES).sum())


if __name__ == "__main__":
    main()
