"""Paired slack differences at matched violation between chosen family pairs, from a frontier per_container.csv.

Usage: uv run python run/frontier_paired.py outputs/frontier_r4/per_container.csv
"""

import sys

import numpy as np
import pandas as pd

from frontier_eval import frontier_at

PAIRS = [("conformal_size_lgbm", "error_padding_lgbm"), ("conformal_size_chronos2", "error_padding_chronos2"),
         ("conformal_size_toto2_313m", "error_padding_toto2_313m"), ("conformal_modify_lgbm", "error_padding_candidate"),
         ("conformal_modify_lgbm", "vpa_updater"), ("conformal_modify_lgbm", "ico_margin"),
         ("conformal_size_lgbm", "ico_margin"), ("conformal_size_lgbm", "vpa_percentile"),
         ("vpa_updater", "vpa_percentile"), ("vpa_updater", "ico_margin"), ("vpa_updater", "fixed_headroom")]
TARGETS = [0.0005, 0.001, 0.002, 0.005, 0.01, 0.02, 0.05]

df = pd.read_csv(sys.argv[1])
ids = df.container_id.unique()
rng = np.random.default_rng(0)
by = dict(tuple(df.groupby("container_id")))
res = [pd.concat([by[c] for c in rng.choice(ids, len(ids))], ignore_index=True) for _ in range(1000)]
print("## Slack at matched violation for low targets (family: " + ", ".join(f"viol={t}" for t in TARGETS) + ")")
for fam in sorted(df.family.unique()):
    print(f"| {fam} | " + " | ".join(f"{v:.4f}" if np.isfinite(v := frontier_at(df, fam, t)) else "--" for t in TARGETS) + " |")
print("\n## Paired differences, a - b (mean [95% paired bootstrap CI]; share of resamples < 0)")
print("| a - b | " + " | ".join(f"viol={t}" for t in TARGETS) + " |")
for a, b in PAIRS:
    cells = []
    for t in TARGETS:
        point = frontier_at(df, a, t) - frontier_at(df, b, t)
        if not np.isfinite(point):
            cells.append("--")
            continue
        d = np.array([frontier_at(r, a, t) - frontier_at(r, b, t) for r in res])
        d = d[np.isfinite(d)]
        cells.append(f"{point:+.4f} [{np.percentile(d, 2.5):+.4f}, {np.percentile(d, 97.5):+.4f}]; {np.mean(d < 0):.3f}")
    print(f"| {a} - {b} | " + " | ".join(cells) + " |")
