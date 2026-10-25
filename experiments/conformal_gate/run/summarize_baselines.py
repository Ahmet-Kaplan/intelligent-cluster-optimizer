"""Summarize outputs/baselines/per_container.csv: sizing metrics with 95 % bootstrap CIs, leak-gate rates.

Usage: uv run python run/summarize_baselines.py [path/to/per_container.csv]
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

B = 2000
SEED = 0


def boot_ci(x: np.ndarray) -> str:
    """Mean and percentile-bootstrap 95 % CI, resampling containers."""
    x = x[np.isfinite(x)]
    rng = np.random.default_rng(SEED)
    means = rng.choice(x, (B, len(x))).mean(axis=1)
    return f"{x.mean():.4f} [{np.percentile(means, 2.5):.4f}, {np.percentile(means, 97.5):.4f}]"


def main(path: Path) -> None:
    df = pd.read_csv(path)
    # Sizing on untouched containers only, averaged over seeds per container (seeds change only injections).
    clean = df[df["shape"] == "none"].groupby(["policy", "container_id"])[["slack", "violation_rate"]].mean()
    print("## Sizing on healthy, uninjected containers (mean [95% CI], n = containers)")
    for policy, g in clean.groupby(level="policy"):
        print(f"{policy:22s} n={len(g):3d}  slack {boot_ci(g.slack.to_numpy())}  "
              f"violation {boot_ci(g.violation_rate.to_numpy())}")

    gated = df[df["policy"].str.contains("olsgate")]
    print("\n## Leak gate (pooled over 5 seeds)")
    for policy, g in gated.groupby("policy"):
        fb = g.groupby(g["shape"].where(g.label == 0, "pre-onset (leak ctr)"))[["false_blocks", "healthy_decisions"]].sum()
        rates = (fb.false_blocks / fb.healthy_decisions).round(4).to_dict()
        leaks = g[g.label == 1]
        recall = leaks.detected.astype(float).mean()
        print(f"{policy}: recall {recall:.3f} (n={len(leaks)}), median delay {leaks.delay_h.median():.1f} h")
        print(f"   false-block rate per healthy decision: {rates}")
        print(f"   recall by leak shape: {leaks.groupby('shape').detected.mean().round(2).to_dict()}")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "outputs/baselines/per_container.csv"))
