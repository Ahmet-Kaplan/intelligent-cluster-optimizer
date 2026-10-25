"""Evaluate conformal admission (B4 size / P modify / P veto) on cached Chronos-2 envelopes.

Usage: uv run python run/conformal_eval.py [hydra overrides]
Writes <out_dir>/per_container.csv and prints a summary next to the baselines.
Candidate requests come from the ICO engine without its leak gate (B3_ico_nogate): the gate decides admission.
Variant "ico_candidate" calibrates the candidate itself (U_k = R_k), as the Go operator does; it needs no forecasts.
"""

import dataclasses
import itertools
import logging
from pathlib import Path

import hydra
import numpy as np
import pandas as pd
from omegaconf import DictConfig

from cgate import SimConfig, decision_steps, ico, sizing_metrics
from cgate.conformal import MIN_REQUEST, ConformalConfig, aci_bounds, gate_requests, peak_targets

logger = logging.getLogger(__name__)


def eval_container(mem: np.ndarray, fc: pd.DataFrame | None, sim: SimConfig, cfg: DictConfig) -> list[dict]:
    """skip_decisions drops the first decisions for every forecaster, so all are scored on the same decisions
    (Holt-Winters and the hourly baselines need 48 h; Chronos/Toto/TimesFM only 24 h)."""
    skip = int(cfg.get("skip_decisions", 0))
    n_all = len(decision_steps(len(mem), sim))
    sim = dataclasses.replace(sim, warmup_steps=sim.warmup_steps + skip * sim.every_steps)
    steps = decision_steps(len(mem), sim)
    y = peak_targets(mem, steps, sim.every_steps)
    cand = ico(mem, sim, None)[0]
    rows = []
    for variant, eps, eta in itertools.product(cfg.variants, cfg.eps, cfg.eta):
        if variant == "ico_candidate":
            upper = cand
        else:
            upper = fc[fc.variant == variant].sort_values("k")[f"env_q{cfg.tau0:g}"].to_numpy(float)
            if len(upper) != n_all:
                raise ValueError(f"forecast/decision mismatch: {len(upper)} vs {n_all}")
            upper = upper[skip:]
        bounds, _ = aci_bounds(upper, y, ConformalConfig(eps=eps, eta=eta, window=cfg.window))
        cert = np.isfinite(bounds) & np.isfinite(y)
        for mode in cfg.modes:
            req, cold = gate_requests(cand, bounds, mode)
            active = ~cold & np.isfinite(cand)
            metrics = sizing_metrics(mem, req, sim)
            rows.append({"variant": variant, "eps": eps, "eta": eta, "mode": mode,
                         **metrics,
                         "cold_frac": float(cold.mean()), "uncertifiable_frac": float(np.isposinf(bounds).mean()),
                         "bound_miss_rate": float(np.mean(y[cert] > bounds[cert])) if cert.any() else np.nan,
                         "n_cert": int(cert.sum()), "n_miss": int((y[cert] > bounds[cert]).sum()),
                         # sharpness: headroom of the (floored) bound over the realized peak, relative to the peak
                         "bound_slack": float(np.mean((np.maximum(bounds[cert], MIN_REQUEST) - y[cert])
                                                      / np.maximum(y[cert], MIN_REQUEST))) if cert.any() else np.nan,
                         "modified_frac": float(np.mean(req[active] != cand[active])) if active.any() else np.nan,
                         "changes_per_day": 24.0 * metrics["changes"] / max(metrics["horizons"], 1)})
    return rows


def boot(x: np.ndarray, b: int = 2000) -> str:
    x = x[np.isfinite(x)]
    m = np.random.default_rng(0).choice(x, (b, len(x))).mean(axis=1)
    return f"{x.mean():.4f} [{np.percentile(m, 2.5):.4f}, {np.percentile(m, 97.5):.4f}]"


def summarize(df: pd.DataFrame) -> None:
    clean = df[df["shape"] == "none"]
    keys = ["variant", "eps", "eta", "mode"]
    cols = ["slack", "violation_rate", "bound_miss_rate", "bound_slack", "cold_frac"]
    per_ctr = clean.groupby([*keys, "container_id"])[cols].mean()
    print("## Conformal policies on healthy, uninjected containers (mean [95% CI over containers])")
    for key, g in per_ctr.groupby(level=keys):
        print(f"{'/'.join(map(str, key)):34s} n={len(g):3d} slack {boot(g.slack.to_numpy())}  "
              f"violation {boot(g.violation_rate.to_numpy())}  bound-miss {boot(g.bound_miss_rate.to_numpy())}  "
              f"bound-slack {boot(g.bound_slack.to_numpy())}  "
              f"cold {g.cold_frac.mean():.3f}")


@hydra.main(version_base=None, config_path="../conf", config_name="conformal_eval")
def main(cfg: DictConfig) -> None:
    sim = SimConfig(**cfg.sim)
    root = Path(hydra.utils.to_absolute_path(cfg.prepared_dir))
    fdir = Path(hydra.utils.to_absolute_path(cfg.forecast_dir))
    rows = []
    for seed in cfg.seeds:
        data = pd.read_parquet(root / f"seed_{seed}" / "series.parquet")
        labels = pd.read_csv(root / f"seed_{seed}" / "labels.csv").set_index("container_id")
        live_only = list(cfg.variants) == ["ico_candidate"]
        fcg = {} if live_only else dict(tuple(pd.read_parquet(
            fdir / f"seed_{seed}.parquet", columns=["container_id", "k", "variant", f"env_q{cfg.tau0:g}"]).groupby("container_id")))
        for cid, g in data.groupby("container_id"):
            lab = labels.loc[cid]
            for r in eval_container(g["mem"].to_numpy(float), fcg.get(cid), sim, cfg):
                rows.append({"seed": seed, "container_id": cid, "label": int(lab.label), "shape": lab["shape"], **r})
        logger.info("seed %d done", seed)
    out = Path(hydra.utils.to_absolute_path(cfg.out_dir))
    out.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_csv(out / "per_container.csv", index=False)
    summarize(df)


if __name__ == "__main__":
    main()
