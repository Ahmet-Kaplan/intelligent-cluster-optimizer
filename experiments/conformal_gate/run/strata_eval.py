"""Gate effect by memory variability (reviewer R2 W3): containers split into tertiles of the coefficient of
variation of their uninjected memory series; ICO engine vs the gate in modify mode, per tertile.

Usage: uv run python run/strata_eval.py outputs/frontier_r4/per_container.csv outputs/prepared_alibaba
"""

import sys
from pathlib import Path

import pandas as pd

df = pd.read_csv(sys.argv[1])
root = Path(sys.argv[2])
cv = {}
for seed in range(5):
    labels = pd.read_csv(root / f"seed_{seed}" / "labels.csv")
    healthy = set(labels.loc[labels["shape"] == "none", "container_id"]) - set(cv)
    if not healthy:
        continue
    s = pd.read_parquet(root / f"seed_{seed}" / "series.parquet")
    for cid, g in s[s.container_id.isin(healthy)].groupby("container_id"):
        cv[cid] = g["mem"].std() / g["mem"].mean()
df["tertile"] = pd.qcut(df.container_id.map(cv), 3, labels=["low", "mid", "high"])
pick = {"ICO engine": ("ico_margin", 0.2), "gate modify (LightGBM, 0.05)": ("conformal_modify_lgbm", 0.05),
        "gate modify (candidate, 0.05)": ("conformal_modify_candidate", 0.05),
        "bound as request (LightGBM, 0.05)": ("conformal_size_lgbm", 0.05)}
print("## By memory-variability tertile (CV of the uninjected series): violation / slack, mean over containers")
print("| policy | " + " | ".join(f"{t} CV" for t in ("low", "mid", "high")) + " |")
print("|---|---|---|---|")
for name, (fam, prm) in pick.items():
    g = df[(df.family == fam) & (df.param == prm)]
    if g.empty:
        continue
    cells = [f"{x.violation_rate.mean():.4f} / {x.slack.mean():.4f}" for _, x in g.groupby("tertile", observed=True)]
    print(f"| {name} | " + " | ".join(cells) + " |")
print("CV tertile edges:", pd.Series(cv).quantile([1 / 3, 2 / 3]).round(3).tolist(), "n =", len(cv))
