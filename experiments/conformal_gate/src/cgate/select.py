"""Select long-lived containers and stratify them by CPU variability."""

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class SelectionConfig:
    min_days: float = 3.0
    max_nan_frac: float = 0.05
    per_stratum: int = 100
    seed: int = 42


STRATA = ("stable", "periodic", "bursty")


def cpu_cv(s: pd.Series) -> float:
    m = s.mean()
    return float(s.std() / m) if m > 0 else float("inf")


def select(series: dict[str, pd.DataFrame], cfg: SelectionConfig, step_s: int = 60) -> pd.DataFrame:
    """Return a table of selected container ids with their stratum.

    Strata are CPU coefficient-of-variation tertiles over eligible containers.
    ponytail: CV tertiles as a proxy for stable/periodic/bursty; swap in a periodogram test if reviewers object.
    """
    min_len = int(cfg.min_days * 86_400 / step_s)
    rows = [
        {"container_id": cid, "cv": cpu_cv(df["cpu"].dropna()), "n": len(df)}
        for cid, df in series.items()
        if len(df) >= min_len and df[["cpu", "mem"]].isna().mean().max() <= cfg.max_nan_frac
    ]
    table = pd.DataFrame(rows, columns=["container_id", "cv", "n"])
    table = table[np.isfinite(table["cv"])]
    if len(table) < len(STRATA):
        raise ValueError(f"Only {len(table)} eligible containers; need at least {len(STRATA)}")
    table["stratum"] = pd.qcut(table["cv"].rank(method="first"), len(STRATA), labels=STRATA)
    rng = np.random.default_rng(cfg.seed)
    picked = [
        g.iloc[rng.permutation(len(g))[: cfg.per_stratum]]
        for _, g in table.groupby("stratum", observed=True)
    ]
    return pd.concat(picked, ignore_index=True).sort_values("container_id", ignore_index=True)
