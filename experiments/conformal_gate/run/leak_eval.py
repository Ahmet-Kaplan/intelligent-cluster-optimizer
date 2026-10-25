"""Leak gate evaluation (H3): conformal martingale gate vs the ICO OLS/R^2 gate, on injected leaks.

Usage: uv run python run/leak_eval.py [hydra overrides]
Scores (one per hourly decision, using only data before the decision):
  seasonal_diff      h[j-1] - h[j-25]: last completed hourly peak minus the same hour yesterday (forecaster-free)
  resid_<variant>    previous horizon's realized peak minus its median-forecast peak (Chronos-2, Toto, LightGBM)
Veto: martingale >= 1/lambda and positive 6 h slope; a blocked decision keeps the previous request.
"""

import dataclasses
import logging
import zlib
from pathlib import Path

import hydra
import numpy as np
import pandas as pd
from omegaconf import DictConfig

from cgate import OLSLeakConfig, SimConfig, decision_steps, gate_metrics, ico, sizing_metrics
from cgate.conformal import peak_targets
from cgate.holt_winters import hourly_max
from cgate.leak_conformal import (
    apply_blocks,
    lag1_autocorr,
    leak_blocks,
    log_mixture_martingale,
    recent_slope,
    smoothed_pvalues,
    thin_scores,
)

logger = logging.getLogger(__name__)


REF_HOURS = 24


def frozen_scores(h: np.ndarray, hours: np.ndarray) -> dict[str, np.ndarray]:
    """Scores at decision hour j against the frozen reference day: profile (same hour-of-day) and level (median)."""
    ref = h[:REF_HOURS]
    level = float(np.nanmedian(ref))
    ok = hours > REF_HOURS
    prev = np.where(ok, hours - 1, 0)
    return {"frozen_profile": np.where(ok, h[prev] - ref[prev % REF_HOURS], np.nan),
            "frozen_level": np.where(ok, h[prev] - level, np.nan)}


def scores_for(mem: np.ndarray, sim: SimConfig, env50: dict[str, np.ndarray]) -> tuple[dict, np.ndarray, np.ndarray]:
    steps = decision_steps(len(mem), sim)
    hours = steps // (3600 // sim.step_s)
    h = hourly_max(mem, sim.step_s)
    y = peak_targets(mem, steps, sim.every_steps)
    out = {"seasonal_diff": np.array([h[j - 1] - h[j - 25] if j >= 25 else np.nan for j in hours])}
    # Frozen reference = the warmup day (hours 0-23), healthy for every container (earliest onset: hour 38).
    # Unlike an adaptive forecaster it does not follow a leak, so leak scores keep growing.
    out.update(frozen_scores(h, hours))
    for name, e in env50.items():
        r = y - e
        out[f"resid_{name}"] = np.concatenate([[np.nan], r[:-1]])  # outcome of decision k-1, known at k
    slopes = np.array([recent_slope(h, j) for j in hours])
    return out, slopes, steps


def eval_container(mem: np.ndarray, env50: dict[str, np.ndarray], lab: pd.Series, sim: SimConfig,
                   cfg: DictConfig, rng: np.random.Generator) -> list[dict]:
    label, onset = int(lab.label), int(lab.onset)
    scores, slopes, _ = scores_for(mem, sim, env50)
    cand = ico(mem, sim, None)[0]
    rows = []

    def record(method: str, param: float, blocked: np.ndarray, req: np.ndarray, acf1: float = np.nan) -> None:
        g = gate_metrics(blocked, label, onset, len(mem), sim)
        rows.append({"method": method, "param": param, **g, "ever_false_block": g["false_blocks"] > 0,
                     **sizing_metrics(mem, req, sim), "acf1": acf1})

    for name, raw in scores.items():
        blocks = cfg.get("thin_hours", [1]) if name in cfg.get("thin_scores", []) else [1]
        for block in blocks:
            s = thin_scores(raw, block)
            # autocorrelation of the healthy part only (before onset for leak containers)
            healthy = s[: max(0, (onset // sim.every_steps) - sim.warmup_steps // sim.every_steps)] if label else s
            acf1 = lag1_autocorr(healthy)
            p = smoothed_pvalues(s, rng)
            for cusum in (False, True):
                log_s = log_mixture_martingale(p, cusum=cusum)
                for lam in cfg.lambdas:
                    blocked = leak_blocks(log_s, slopes, lam)
                    tag = f"{name}{f'_t{block}' if block > 1 else ''}{'_cusum' if cusum else ''}"
                    record(tag, lam, blocked, apply_blocks(cand, blocked), acf1)
    base = OLSLeakConfig(machine_mem_gb=cfg.machine_mem_gb)
    for tau in cfg.ols_r2:
        req, blocked = ico(mem, sim, dataclasses.replace(base, r2_threshold=tau),
                           leak_window_steps=int(cfg.ols_window_h * 3600 / sim.step_s))
        record(f"ols_{cfg.ols_window_h:g}h", tau, blocked, req)
    return rows


def summarize(df: pd.DataFrame) -> None:
    print("## Leak gate operating points (pooled over seeds)")
    print("| method | param | recall | recall@rate<=2%/h | ctr FPR healthy | ctr FPR hard-neg | "
          "false-block/decision | median delay h | violation (healthy) | lag-1 ACF (healthy) |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for (m, prm), g in df.groupby(["method", "param"]):
        leaks, clean, hard = g[g.label == 1], g[g["shape"] == "none"], g[(g.label == 0) & (g["shape"] != "none")]
        slow = leaks[leaks.rate_per_hour <= 0.02]
        fb = g.false_blocks.sum() / max(g.healthy_decisions.sum(), 1)
        print(f"| {m} | {prm:g} | {leaks.detected.astype(float).mean():.3f} | {slow.detected.astype(float).mean():.3f} | "
              f"{clean.ever_false_block.mean():.3f} | {hard.ever_false_block.mean():.3f} | {fb:.4f} | "
              f"{leaks.delay_h.median():.1f} | {clean.violation_rate.mean():.4f} | {clean.acf1.mean():.2f} |")


@hydra.main(version_base=None, config_path="../conf", config_name="leak_eval")
def main(cfg: DictConfig) -> None:
    sim = SimConfig(**cfg.sim)
    root = Path(hydra.utils.to_absolute_path(cfg.prepared_dir))
    rows = []
    for seed in cfg.seeds:
        data = pd.read_parquet(root / f"seed_{seed}" / "series.parquet")
        labels = pd.read_csv(root / f"seed_{seed}" / "labels.csv").set_index("container_id")
        env = {}
        for name, (d, variant) in cfg.residual_sources.items():
            fc = pd.read_parquet(Path(hydra.utils.to_absolute_path(d)) / f"seed_{seed}.parquet",
                                 columns=["container_id", "k", "variant", "env_q0.5"])
            fc = fc[fc.variant == variant].sort_values("k")
            env[name] = {c: g["env_q0.5"].to_numpy(float) for c, g in fc.groupby("container_id")}
        for cid, g in data.groupby("container_id"):
            lab = labels.loc[cid]
            # theta_rep 0 reproduces the published run; others redraw the smoothing variables theta
            key = f"{seed}/{cid}" if cfg.theta_rep == 0 else f"{seed}/{cid}/{cfg.theta_rep}"
            rng = np.random.default_rng(zlib.crc32(key.encode()))
            env50 = {n: e[cid] for n, e in env.items()}
            for r in eval_container(g["mem"].to_numpy(float), env50, lab, sim, cfg, rng):
                rows.append({"seed": seed, "container_id": cid, "label": int(lab.label), "shape": lab["shape"],
                             "rate_per_hour": float(lab.rate_per_hour), **r})
        logger.info("seed %d done", seed)
    out = Path(hydra.utils.to_absolute_path(cfg.out_dir))
    out.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_csv(out / "per_container.csv", index=False)
    summarize(df)


if __name__ == "__main__":
    main()
