"""Slack-violation frontier: tuned simple rules vs the conformal gate, on identical decisions (finding M3).

Usage: uv run python run/frontier_eval.py [hydra overrides]
Each policy family sweeps its own knob; slack is then compared at matched violation levels by linear
interpolation along each family's frontier, with a bootstrap over containers for the CIs and a paired bootstrap
(containers resampled jointly, every family re-interpolated per resample) for differences against VPA.
Every container is used with an uninjected series (from the first seed that leaves it healthy).
Decisions before `eval_from` are dropped for every family, so all conformal points are calibrated ones.
"""

import dataclasses
import logging
from pathlib import Path

import hydra
import numpy as np
import pandas as pd
from omegaconf import DictConfig

from cgate import (SimConfig, decision_steps, error_padding, fixed_headroom, ico, sizing_metrics, vpa,
                   vpa_faithful)
from cgate.conformal import ConformalConfig, aci_bounds, gate_requests, peak_targets

logger = logging.getLogger(__name__)


def policies(mem: np.ndarray, sim: SimConfig, env: dict[str, np.ndarray], cfg: DictConfig) -> dict[str, np.ndarray]:
    """All requests for one container, keyed 'family|param'. Decisions start at the common start (skip)."""
    steps = decision_steps(len(mem), sim)
    out = {}
    for d in cfg.ico_delta:
        out[f"ico_margin|{d}"] = ico(mem, sim, None, margin=1 + d)[0]
    for q in cfg.vpa_percentile:
        out[f"vpa_percentile|{q}"] = vpa(mem, sim, q=q)
        out[f"vpa_updater|{q}"] = vpa_faithful(mem, sim, q=q)
    for f in cfg.headroom_factor:
        out[f"fixed_headroom|{f}"] = fixed_headroom(mem, sim, factor=f)
    y = peak_targets(mem, steps, sim.every_steps)
    cand = out["ico_margin|0.2"]
    for name, upper in env.items():
        for eps in cfg.eps:
            eta = 0.0 if eps < 0.05 else 0.005  # static for small budgets, ACI otherwise (Table V)
            b, _ = aci_bounds(upper, y, ConformalConfig(eps=eps, eta=eta, window=168))
            out[f"conformal_size_{name}|{eps}"] = gate_requests(cand, b, "size")[0]
            out[f"conformal_modify_{name}|{eps}"] = gate_requests(cand, b, "modify")[0]
        for n in cfg.padding_n:
            out[f"error_padding_{name}|{n}"] = error_padding(upper, y, n)
    for n in cfg.padding_n:
        out[f"error_padding_candidate|{n}"] = error_padding(cand, y, n)
    for req in out.values():
        req[:cfg.eval_from] = np.nan
    return out


def frontier_at(df: pd.DataFrame, family: str, target: float) -> float:
    """Slack of `family` at violation `target`, interpolated along its (violation-sorted) points; NaN if out of range."""
    g = df[df.family == family].groupby("param")[["violation_rate", "slack"]].mean().sort_values("violation_rate")
    v, s = g.violation_rate.to_numpy(), g.slack.to_numpy()
    if len(v) < 2 or target < v.min() or target > v.max():
        return np.nan
    return float(np.interp(target, v, s))


def summarize(df: pd.DataFrame, targets: list[float], refs: list[str], n_boot: int = 1000) -> None:
    print(f"{df.container_id.nunique()} containers, {int(df.groupby('container_id').horizons.max().mean())} "
          "evaluated decisions per container on average")
    print("## Policy points (mean over containers; median slack; resizes per container-day)")
    df = df.assign(resizes_per_day=df.changes / (df.horizons / 24))
    pts = df.groupby(["family", "param"]).agg(slack=("slack", "mean"), slack_median=("slack", "median"),
                                             violation_rate=("violation_rate", "mean"),
                                             resizes=("resizes_per_day", "mean")).reset_index()
    for _, r in pts.iterrows():
        print(f"| {r.family} | {r.param:g} | slack {r.slack:.4f} (median {r.slack_median:.4f}) | "
              f"violation {r.violation_rate:.4f} | resizes/day {r.resizes:.2f} |")
    families = sorted(df.family.unique())
    ids = df.container_id.unique()
    rng = np.random.default_rng(0)
    boots = [rng.choice(ids, len(ids)) for _ in range(n_boot)]
    by_ctr = dict(tuple(df.groupby("container_id")))
    resampled = [pd.concat([by_ctr[c] for c in pick], ignore_index=True) for pick in boots]
    print("\n## Slack at matched violation (interpolated; mean [95% bootstrap CI over containers]); -- = out of range")
    print("| family | " + " | ".join(f"viol={t}" for t in targets) + " |")
    print("|---|" + "---|" * len(targets))
    for fam in families:
        cells = []
        for t in targets:
            point = frontier_at(df, fam, t)
            if np.isnan(point):
                cells.append("--")
                continue
            bs = [frontier_at(r, fam, t) for r in resampled]
            bs = np.array([b for b in bs if np.isfinite(b)])
            cells.append(f"{point:.4f} [{np.percentile(bs, 2.5):.4f}, {np.percentile(bs, 97.5):.4f}]" if len(bs) else f"{point:.4f}")
        print(f"| {fam} | " + " | ".join(cells) + " |")
    print("\n## Paired difference in slack at matched violation, family - reference "
          "(mean [95% paired bootstrap CI]; share of resamples < 0)")
    for ref in refs:
        for fam in families:
            if fam == ref:
                continue
            cells = []
            for t in targets:
                point = frontier_at(df, fam, t) - frontier_at(df, ref, t)
                if np.isnan(point):
                    cells.append("--")
                    continue
                d = np.array([frontier_at(r, fam, t) - frontier_at(r, ref, t) for r in resampled])
                d = d[np.isfinite(d)]
                cells.append(f"{point:+.4f} [{np.percentile(d, 2.5):+.4f}, {np.percentile(d, 97.5):+.4f}]; "
                             f"{np.mean(d < 0):.3f}")
            print(f"| {fam} - {ref} | " + " | ".join(cells) + " |")


def evaluate(data: pd.DataFrame, env_all: dict, sim: SimConfig, cfg: DictConfig) -> list[dict]:
    rows = []
    for cid, g in data.groupby("container_id"):
        mem = g["mem"].to_numpy(float)
        env = {n: e[cid] for n, e in env_all.items()}
        for key, req in policies(mem, sim, env, cfg).items():
            fam, param = key.split("|")
            rows.append({"container_id": cid, "family": fam, "param": float(param), **sizing_metrics(mem, req, sim)})
    return rows


@hydra.main(version_base=None, config_path="../conf", config_name="frontier_eval")
def main(cfg: DictConfig) -> None:
    base = SimConfig(**cfg.sim)
    skip = cfg.skip_decisions
    sim = dataclasses.replace(base, warmup_steps=base.warmup_steps + skip * base.every_steps)
    root = Path(hydra.utils.to_absolute_path(cfg.prepared_dir))
    # The uninjected series is identical in every seed, so each container is taken from the first seed
    # that leaves it healthy.
    seed_of = {}
    for seed in cfg.seeds:
        labels = pd.read_csv(root / f"seed_{seed}" / "labels.csv")
        for cid in labels.loc[labels["shape"] == "none", "container_id"]:
            seed_of.setdefault(cid, seed)
    rows = []
    for seed in cfg.seeds:
        mine = [c for c, s_ in seed_of.items() if s_ == seed]
        if not mine:
            continue
        data = pd.read_parquet(root / f"seed_{seed}" / "series.parquet")
        env_all = {}
        for name, (d, variant) in cfg.forecasts.items():
            fc = pd.read_parquet(Path(hydra.utils.to_absolute_path(d)) / f"seed_{seed}.parquet",
                                 columns=["container_id", "k", "variant", "env_q0.9"])
            fc = fc[(fc.variant == variant) & fc.container_id.isin(mine)].sort_values("k")
            env_all[name] = {c: g["env_q0.9"].to_numpy(float)[skip:] for c, g in fc.groupby("container_id")}
        rows += evaluate(data[data.container_id.isin(mine)], env_all, sim, cfg)
    df = pd.DataFrame(rows)
    out = Path(hydra.utils.to_absolute_path(cfg.out_dir))
    out.mkdir(parents=True, exist_ok=True)
    df.to_csv(out / "per_container.csv", index=False)
    logger.info("%d containers, %d policies", df.container_id.nunique(), df.groupby(["family", "param"]).ngroups)
    summarize(df, list(cfg.targets), list(cfg.paired_refs))


if __name__ == "__main__":
    main()
