"""Held-out operating-point selection for leak gates, plus Wilcoxon/Holm tests for paired claims (finding M5).

Usage: uv run python run/stats_eval.py   (needs scipy; run in the .venv-fm environment)
Reads per-container CSVs already produced by leak_eval.py, conformal_eval.py, run/baselines.py and the panel.
"""

import zlib
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

FPR_TARGETS = (0.05, 0.10, 0.35)


def fold(cid: str) -> int:
    return zlib.crc32(cid.encode()) % 2


def leak_points(df: pd.DataFrame) -> pd.DataFrame:
    """recall, healthy container-FPR and healthy violation per (method, param) on one fold."""
    rows = []
    for (m, prm), g in df.groupby(["method", "param"]):
        clean = g[g["shape"] == "none"]
        leaks, hard = g[g.label == 1], g[(g.label == 0) & (g["shape"] != "none")]
        # FPR per distinct container (uninjected series repeat across seeds): average over seeds first
        fpr = clean.groupby("container_id").ever_false_block.mean().mean()
        fb = g.false_blocks.sum() / max(g.healthy_decisions.sum(), 1)
        rows.append({"method": m, "param": prm, "recall": leaks.detected.astype(float).mean(),
                     "fpr": fpr, "violation": clean.violation_rate.mean(),
                     "hard_fpr": hard.ever_false_block.astype(float).mean(),
                     "slow_recall": leaks[leaks.rate_per_hour <= 0.02].detected.astype(float).mean(),
                     "delay_h": leaks.delay_h.median(), "fb_per_1000": 24_000 * fb})
    return pd.DataFrame(rows)


def cluster_ci(g: pd.DataFrame, n: int = 1000) -> tuple[float, float, float, float]:
    """Container-clustered bootstrap CIs for recall and healthy FPR (rows of a container resampled together)."""
    rng = np.random.default_rng(0)
    by = {c: x for c, x in g.groupby("container_id")}
    ids = np.array(list(by))
    rec, fpr = [], []
    for _ in range(n):
        b = pd.concat([by[c] for c in rng.choice(ids, len(ids))])
        rec.append(b[b.label == 1].detected.astype(float).mean())
        cl = b[b["shape"] == "none"]
        fpr.append(cl.groupby("container_id").ever_false_block.mean().mean())
    q = lambda v: np.nanpercentile(v, [2.5, 97.5])
    return (*q(rec), *q(fpr))


def heldout_leak_repeated(paths: list[Path], n_splits: int = 10) -> None:
    """Held-out selection repeated over p-value randomizations (one file each) and random 2-fold splits.

    For each (randomization, split) the operating point is selected on fold A and reported on fold B, as in
    heldout_leak; the table gives mean and SD over all repetitions of the selected gate per method.
    """
    res = []
    for i, path in enumerate(paths):
        df = pd.read_csv(path)
        for salt in range(n_splits):
            df["fold"] = df.container_id.map(lambda c: zlib.crc32(f"{salt}/{c}".encode()) % 2)
            sel, test = leak_points(df[df.fold == 0]), leak_points(df[df.fold == 1])
            for target in FPR_TARGETS:
                ok = sel[sel.fpr <= target]
                if not len(ok):
                    continue
                best = ok.loc[ok.groupby("method").recall.idxmax()][["method", "param"]].merge(test, on=["method", "param"])
                res += [{"rep": i, "split": salt, "target": target, **r} for r in best.to_dict("records")]
    r = pd.DataFrame(res)
    print(f"## Leak gates over {len(paths)} randomizations x {n_splits} splits (fold-B mean +- SD of the selected point)")
    print("| FPR target | method | recall | healthy FPR | hard-neg FPR | violation | reps |")
    print("|---|---|---|---|---|---|---|")
    agg = r.groupby(["target", "method"]).agg(recall=("recall", "mean"), recall_sd=("recall", "std"),
                                              fpr=("fpr", "mean"), fpr_sd=("fpr", "std"), hard=("hard_fpr", "mean"),
                                              viol=("violation", "mean"), n=("recall", "size")).reset_index()
    for target, g in agg.groupby("target"):
        for _, x in g.sort_values("recall", ascending=False).head(6).iterrows():
            print(f"| {target} | {x.method} | {x.recall:.3f} +- {x.recall_sd:.3f} | {x.fpr:.3f} +- {x.fpr_sd:.3f} | "
                  f"{x.hard:.3f} | {x.viol:.4f} | {x.n} |")


def heldout_leak(path: Path) -> None:
    df = pd.read_csv(path)
    df["fold"] = df.container_id.map(fold)
    sel, test = leak_points(df[df.fold == 0]), leak_points(df[df.fold == 1])
    print("## Leak gates: operating point selected on fold A (max recall s.t. healthy FPR <= target), reported on fold B")
    print("| FPR target | method | param | recall [95% CI] | healthy FPR [95% CI] | violation | hard-neg FPR | "
          "recall (rate<=2%/h) | median delay h | false blocks / 1000 ctr-days |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for target in FPR_TARGETS:
        ok = sel[sel.fpr <= target]
        best = ok.loc[ok.groupby("method").recall.idxmax()] if len(ok) else ok
        res = best[["method", "param"]].merge(test, on=["method", "param"]).sort_values("recall", ascending=False)
        for _, r in res.head(6).iterrows():
            g = df[(df.fold == 1) & (df.method == r.method) & (df.param == r.param)]
            lo_r, hi_r, lo_f, hi_f = cluster_ci(g)
            print(f"| {target} | {r.method} | {r.param:g} | {r.recall:.3f} [{lo_r:.3f}, {hi_r:.3f}] | "
                  f"{r.fpr:.3f} [{lo_f:.3f}, {hi_f:.3f}] | {r.violation:.4f} | {r.hard_fpr:.3f} | {r.slow_recall:.3f} | "
                  f"{r.delay_h:.1f} | {r.fb_per_1000:.0f} |")


def signflip(d: pd.Series, n: int = 20000) -> tuple[float, float, float]:
    """Mean paired difference: two-sided sign-flip permutation p-value and 95% bootstrap CI (same estimand)."""
    x = d.to_numpy(float)
    rng = np.random.default_rng(0)
    flips = rng.choice([-1.0, 1.0], size=(n, len(x)))
    p = (np.sum(np.abs((flips * x).mean(axis=1)) >= abs(x.mean()) - 1e-15) + 1) / (n + 1)
    boot = x[rng.integers(0, len(x), size=(n // 4, len(x)))].mean(axis=1)
    return p, *np.percentile(boot, [2.5, 97.5])


def per_ctr(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    return df[df["shape"] == "none"].groupby("container_id")[cols].mean()


def paired_tests(root: Path) -> None:
    base = pd.read_csv(root / "baselines" / "per_container.csv")
    conf = pd.read_csv(root / "conformal" / "per_container.csv")
    c = conf[(conf.variant == "covariate") & np.isclose(conf.eps, 0.05) & np.isclose(conf.eta, 0.005)]
    arms = {"modify": per_ctr(c[c["mode"] == "modify"], ["slack", "violation_rate"]),
            "veto": per_ctr(c[c["mode"] == "veto"], ["slack", "violation_rate"])}
    refs = {p: per_ctr(base[base.policy == p], ["slack", "violation_rate"])
            for p in ("B3_ico_nogate", "B1_vpa", "B3_ico_olsgate_6h")}
    tests = [(a, r, m) for a, r in (("modify", "B3_ico_nogate"), ("modify", "B1_vpa"), ("modify", "B3_ico_olsgate_6h"),
                                    ("veto", "B3_ico_nogate")) for m in ("slack", "violation_rate")]
    panel = pd.concat([pd.read_csv(p) for p in sorted((root / "panel").glob("*/per_container.csv"))])
    pz = panel[(panel["mode"] == "size") & np.isclose(panel.eps, 0.05) & np.isclose(panel.eta, 0.005) & (panel["shape"] == "none")]
    pz = pz.groupby(["variant", "container_id"]).bound_slack.mean().unstack(0)
    rows = []
    for a, r, m in tests:
        j = arms[a][[m]].join(refs[r][[m]], rsuffix="_ref", how="inner").dropna()
        d = j[m] - j[m + "_ref"]
        rows.append((f"{a} vs {r}", m, d, *signflip(d)))
    for v in pz.columns:
        if v in ("holt_winters", "covariate"):
            continue
        for ref in ("holt_winters", "univariate"):
            if v == ref:
                continue
            d = (pz[v] - pz[ref]).dropna()
            rows.append((f"{v} vs {ref}", "bound_slack", d, *signflip(d)))
    rows += [(name, "bound_slack", d, *signflip(d)) for name, d in extra_comparisons(root)]
    res = pd.DataFrame(rows, columns=["comparison", "metric", "d", "p", "lo", "hi"]).sort_values("p")
    m = len(res)
    res["p_holm"] = np.minimum(1, np.maximum.accumulate((m - np.arange(m)) * res.p.to_numpy()))
    print("\n## Paired comparisons: mean difference [95% bootstrap CI], sign-flip permutation p, "
          "Holm-corrected over every comparison reported in the paper (this table is the whole family)")
    print("| comparison | metric | mean diff [95% CI] | n | lower/higher | p | p (Holm) |")
    print("|---|---|---|---|---|---|---|")
    for _, r in res.iterrows():
        print(f"| {r.comparison} | {r.metric} | {r.d.mean():+.4f} [{r.lo:+.4f}, {r.hi:+.4f}] | {len(r.d)} | "
              f"{(r.d < 0).sum()}/{(r.d > 0).sum()} | {r.p:.2g} | {r.p_holm:.2g} |")


def extra_comparisons(root: Path) -> list[tuple[str, pd.Series]]:
    """Comparisons that used to sit outside the Holm family: forecaster context length and the operator's envelope."""
    out = []

    def sel(d: pd.DataFrame) -> pd.DataFrame:
        return d[(d["mode"] == "size") & np.isclose(d.eps, 0.05) & np.isclose(d.eta, 0.005) & (d["shape"] == "none")]

    ctx = [root / "panel" / "toto2_22m" / "per_container.csv", root / "panel_ctx" / "toto2_22m_ctx8192" / "per_container.csv"]
    if all(p.exists() for p in ctx):
        a, b = (sel(pd.read_csv(p)).groupby("container_id").bound_slack.mean() for p in ctx)
        out.append(("toto2_22m ctx8192 vs ctx2048", (b - a).dropna()))
    live = root / "panel_live" / "ico_candidate" / "per_container.csv"
    if live.exists():
        ref = pd.read_csv(root / "panel" / "chronos2" / "per_container.csv")
        a = sel(pd.read_csv(live)).groupby("container_id").bound_slack.mean()
        b = sel(ref[ref.variant == "univariate"]).groupby("container_id").bound_slack.mean()
        out.append(("ico_candidate vs univariate", (a - b).dropna()))
    return out


def validity_detail(root: Path) -> None:
    """Per-forecaster validity with denominators: certified decisions, cold/uncertifiable shares, per-container tail."""
    from scipy.stats import binom

    panel = pd.concat([pd.read_csv(p) for p in sorted((root / "panel").glob("*/per_container.csv"))])
    v = panel[(panel["mode"] == "size") & (panel["shape"] == "none")]
    print("\n## Validity detail (size mode, healthy uninjected; per distinct container, seed-averaged)")
    print("| forecaster | eps | eta | miss rate [95% CI over ctrs] | certified/ctr | cold | uncertifiable | miss P90 (per ctr) | "
          "share of ctrs with miss > eps / 1.5 eps / 2 eps | ctrs sig. > eps (BH 5%) | approvals / 1000 ctr-days |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    rng = np.random.default_rng(0)
    for (var, eps, eta), g in v.groupby(["variant", "eps", "eta"]):
        c = g.groupby("container_id")[["n_cert", "n_miss", "cold_frac", "uncertifiable_frac", "bound_miss_rate"]].mean()
        p = binom.sf(np.round(c.n_miss) - 1, np.round(c.n_cert).clip(lower=1), eps)  # H0: miss <= eps
        order = np.argsort(p)
        bh = np.zeros(len(p), dtype=bool)
        k = np.flatnonzero(p[order] <= 0.05 * (np.arange(len(p)) + 1) / len(p))
        if len(k):
            bh[order[: k.max() + 1]] = True
        mr = c.bound_miss_rate.dropna().to_numpy()
        lo, hi = np.percentile(mr[rng.integers(0, len(mr), (2000, len(mr)))].mean(axis=1), [2.5, 97.5])
        tail = " / ".join(f"{np.mean(mr > f * eps):.3f}" for f in (1, 1.5, 2))
        print(f"| {var} | {eps:g} | {eta:g} | {mr.mean():.4f} [{lo:.4f}, {hi:.4f}] | {c.n_cert.mean():.0f} | "
              f"{c.cold_frac.mean():.3f} | {c.uncertifiable_frac.mean():.3f} | {np.nanpercentile(c.bound_miss_rate, 90):.3f} | "
              f"{tail} | {bh.mean():.3f} | {24_000 * c.cold_frac.mean():.0f} |")


def modify_binding(root: Path) -> None:
    conf = pd.read_csv(root / "conformal" / "per_container.csv")
    m = conf[(conf["mode"] == "modify") & (conf["shape"] == "none")]
    print("\n## Modify mode: how often the gate changes the candidate, resize churn")
    print("| variant | eps | eta | modified fraction | resizes / ctr-day | violation | slack |")
    print("|---|---|---|---|---|---|---|")
    for (var, eps, eta), g in m.groupby(["variant", "eps", "eta"]):
        c = g.groupby("container_id")[["modified_frac", "changes_per_day", "violation_rate", "slack"]].mean()
        print(f"| {var} | {eps:g} | {eta:g} | {c.modified_frac.mean():.4f} | {c.changes_per_day.mean():.2f} | "
              f"{c.violation_rate.mean():.4f} | {c.slack.mean():.4f} |")


def post_onset_hours(prepared: Path) -> None:
    hrs = []
    for seed in range(5):
        lab = pd.read_csv(prepared / f"seed_{seed}" / "labels.csv")
        n = pd.read_parquet(prepared / f"seed_{seed}" / "series.parquet", columns=["container_id"]).container_id.value_counts()
        leaks = lab[lab.label == 1]
        hrs += list((n.loc[leaks.container_id].to_numpy() - leaks.onset.to_numpy()) / 60)
    h = np.array(hrs)
    print(f"\n## Hours from leak onset to trace end: median {np.median(h):.0f}, min {h.min():.0f}, max {h.max():.0f} "
          f"(= {np.median(h) / 12:.1f} blocks of 12 h, {np.median(h) / 24:.1f} of 24 h at the median)")


def context_sensitivity(root: Path) -> None:
    rows = []
    for name in ("toto2_22m", "toto2_22m_ctx8192"):
        p = root / ("panel_ctx" if "ctx" in name else "panel") / name / "per_container.csv"
        if not p.exists():
            return
        d = pd.read_csv(p)
        d = d[(d["mode"] == "size") & np.isclose(d.eps, 0.05) & np.isclose(d.eta, 0.005) & (d["shape"] == "none")]
        rows.append(d.groupby("container_id")[["bound_slack", "bound_miss_rate", "slack", "violation_rate"]].mean())
    j = rows[1].join(rows[0], rsuffix="_2048", how="inner")
    d = j.bound_slack - j.bound_slack_2048
    print(f"\n## Toto 2.0 22M context 8192 vs 2048 steps (eps 0.05, size): bound-slack diff {d.mean():+.4f}, "
          f"Wilcoxon p = {wilcoxon(d).pvalue:.2g}; miss {j.bound_miss_rate.mean():.4f} vs {j.bound_miss_rate_2048.mean():.4f}; "
          f"slack {j.slack.mean():.4f} vs {j.slack_2048.mean():.4f}")


def live_envelope(root: Path) -> None:
    """The Go operator's configuration (envelope = ICO candidate) against the Chronos-2 envelope, same decisions."""
    p = root / "panel_live" / "ico_candidate" / "per_container.csv"
    if not p.exists():
        return
    def sel(d: pd.DataFrame) -> pd.DataFrame:
        return d[(d["mode"] == "size") & np.isclose(d.eps, 0.05) & np.isclose(d.eta, 0.005) & (d["shape"] == "none")]
    live = sel(pd.read_csv(p)).groupby("container_id").bound_slack.mean()
    ref = pd.read_csv(root / "panel" / "chronos2" / "per_container.csv")
    ref = sel(ref[ref.variant == "univariate"]).groupby("container_id").bound_slack.mean()
    d = (live - ref).dropna()
    print(f"\n## Live envelope (ICO candidate) vs Chronos-2 univariate, bound slack (eps 0.05, size, healthy): "
          f"{live.mean():.4f} vs {ref.mean():.4f}, diff {d.mean():+.4f}, n = {len(d)}, Wilcoxon p = {wilcoxon(d).pvalue:.2g} "
          f"(outside the Holm family above)")


if __name__ == "__main__":
    out = Path("outputs")
    heldout_leak(out / "leak_eval_thin" / "per_container.csv")
    reps = [out / "leak_eval_thin" / "per_container.csv"] + sorted((out / "leak_eval_r4").glob("theta_*/per_container.csv"))
    heldout_leak_repeated(reps)
    paired_tests(out)
    validity_detail(out)
    modify_binding(out)
    post_onset_hours(out / "prepared_alibaba")
    context_sensitivity(out)
    live_envelope(out)
