"""Compare all forecasters under the same conformal gate (outputs/panel/*/per_container.csv).

Usage: uv run python run/panel_summary.py [panel_dir] [eps] [eta]
All panel runs use skip_decisions=24, so every forecaster is scored on the same decisions.
Paired differences are per container (uninjected, seed-averaged), with percentile-bootstrap 95 % CIs.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

B, SEED = 4000, 0
METRICS = ["bound_miss_rate", "bound_slack", "slack", "violation_rate"]
REFERENCES = ("holt_winters", "univariate")  # current ICO forecaster; Chronos-2 univariate


def ci(x: np.ndarray) -> str:
    x = x[np.isfinite(x)]
    m = np.random.default_rng(SEED).choice(x, (B, len(x))).mean(axis=1)
    return f"{x.mean():.4f} [{np.percentile(m, 2.5):.4f}, {np.percentile(m, 97.5):.4f}]"


def load(panel: Path, eps: float, eta: float) -> pd.DataFrame:
    df = pd.concat([pd.read_csv(p) for p in sorted(panel.glob("*/per_container.csv"))], ignore_index=True)
    df = df[(df["shape"] == "none") & np.isclose(df.eps, eps) & np.isclose(df.eta, eta)]
    return df.groupby(["variant", "mode", "container_id"])[METRICS].mean().reset_index()


def main(panel: Path, eps: float, eta: float) -> None:
    df = load(panel, eps, eta)
    print(f"# Forecaster panel under the conformal gate (eps={eps}, eta={eta}, common start at hour 48)\n")
    for mode in ("size", "modify"):
        print(f"## mode = {mode}  (mean [95% CI over containers])")
        print("| forecaster | n | bound miss (<= eps) | bound slack (sharpness) | slack | violation |")
        print("|---|---|---|---|---|---|")
        for v, g in df[df["mode"] == mode].groupby("variant"):
            print(f"| {v} | {len(g)} | " + " | ".join(ci(g[m].to_numpy()) for m in METRICS) + " |")
        print()
    size = df[df["mode"] == "size"].set_index(["variant", "container_id"])
    for ref in REFERENCES:
        if ref not in size.index.get_level_values(0):
            continue
        print(f"## Paired difference vs {ref} (mode = size): forecaster - {ref}")
        print("| forecaster | bound slack | slack | violation |")
        print("|---|---|---|---|")
        base = size.loc[ref]
        for v in sorted(set(size.index.get_level_values(0)) - {ref}):
            j = size.loc[v].join(base, rsuffix="_ref", how="inner")
            cells = [ci((j[m] - j[m + "_ref"]).to_numpy()) for m in ("bound_slack", "slack", "violation_rate")]
            print(f"| {v} | " + " | ".join(cells) + " |")
        print()


if __name__ == "__main__":
    a = sys.argv[1:]
    main(Path(a[0] if a else "outputs/panel"), float(a[1]) if len(a) > 1 else 0.05, float(a[2]) if len(a) > 2 else 0.005)
