"""Replay baselines B1-B3 on prepared seeds; write one row per (seed, container, policy).

Usage: uv run python run/baselines.py [hydra overrides]
Memory only for now: it is the resource the leak gate protects (OOM).
"""

import logging
from pathlib import Path

import hydra
import numpy as np
import pandas as pd
from omegaconf import DictConfig

from cgate import OLSLeakConfig, SimConfig, fixed_headroom, gate_metrics, ico, sizing_metrics, vpa

logger = logging.getLogger(__name__)


def run_container(u: np.ndarray, label: int, onset: int, sim: SimConfig, leak: OLSLeakConfig,
                  leak_windows_h: list[float]) -> list[dict]:
    rows = []
    gated = [(f"B3_ico_olsgate_{w:g}h", *ico(u, sim, leak, leak_window_steps=int(w * 3600 / sim.step_s)))
             for w in leak_windows_h]
    for name, req, blocked in [
        ("B1_vpa", vpa(u, sim), None),
        ("B2_headroom", fixed_headroom(u, sim), None),
        ("B3_ico_nogate", ico(u, sim, None)[0], None),
        *gated,
    ]:
        row = {"policy": name, **sizing_metrics(u, req, sim)}
        if blocked is not None:
            row.update(gate_metrics(blocked, label, onset, len(u), sim))
        rows.append(row)
    return rows


@hydra.main(version_base=None, config_path="../conf", config_name="baselines")
def main(cfg: DictConfig) -> None:
    sim, leak = SimConfig(**cfg.sim), OLSLeakConfig(**cfg.leak)
    root = Path(hydra.utils.to_absolute_path(cfg.prepared_dir))
    rows = []
    for seed in cfg.seeds:
        data = pd.read_parquet(root / f"seed_{seed}" / "series.parquet")
        labels = pd.read_csv(root / f"seed_{seed}" / "labels.csv").set_index("container_id")
        for cid, g in data.groupby("container_id"):
            lab = labels.loc[cid]
            for r in run_container(g["mem"].to_numpy(float), int(lab.label), int(lab.onset), sim, leak,
                                     list(cfg.leak_windows_h)):
                rows.append({"seed": seed, "container_id": cid, "label": int(lab.label), "shape": lab["shape"], **r})
        logger.info("seed %d done", seed)
    out = Path(hydra.utils.to_absolute_path(cfg.out_dir))
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out / "per_container.csv", index=False)
    logger.info("wrote %d rows to %s", len(rows), out / "per_container.csv")


if __name__ == "__main__":
    main()
