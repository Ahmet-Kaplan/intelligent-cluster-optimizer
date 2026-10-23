"""Workload-level report for a live A/B run of the conformal admission gate (v1 and v2 runs).

Usage: live_report.py OUT_DIR GATE_NS OTHER_NS [OTHER_NS ...] [--gate-log FILE] [--vetoes FILE]

Ground truth is GKE's 60-s non-evictable memory and the request series, binned into wall-clock hours (an hour
counts with >= 30 samples; peak = max usage, request = min request in the hour). The unit of analysis is the
workload: per-workload exceedance rates are compared between the gate arm and each other arm with a paired
Wilcoxon signed-rank test (Holm over the comparisons) and a bootstrap CI over workloads; hour counts are
descriptive. Two windows: the whole run (from 1 h after the first sample) and the calibrated window (from the
first full hour after the gate arm's first calibrated decision for that workload). Replayed rules re-size against the gate arm's usage.
"""

import argparse
import collections
import json
import re
import statistics
from pathlib import Path

import numpy as np
from scipy.stats import wilcoxon

MIB = 2**20
SCORED = re.compile(r'key="([^"]+)" at="([^"]+)" peak=(\S+) upper=(\S+) bound=(.+?) alpha=(\S+)$')


def series(path: Path, memory_type: str | None = None) -> dict:
    """{(namespace, workload): {minute: value}} and {(namespace, workload): set(pod names)}."""
    d, pods = collections.defaultdict(dict), collections.defaultdict(set)
    for s in json.load(open(path)):
        if memory_type and s["metric"]["labels"].get("memory_type") != memory_type:
            continue
        r = s["resource"]["labels"]
        key = (r["namespace_name"], r["pod_name"].rsplit("-", 2)[0])
        pods[key].add(r["pod_name"])
        for p in s["points"]:
            t = p["interval"]["endTime"][:16]
            d[key][t] = max(d[key].get(t, 0), int(p["value"]["int64Value"]))
    return d, pods


def hours(used: dict, req: dict) -> dict:
    """{key: {hour: (peak, min_request, mean_request, minutes_over, overrun_mib_sum)}}."""
    out = {}
    for key, u in used.items():
        by = collections.defaultdict(list)
        for t, v in u.items():
            if t in req.get(key, {}):
                by[t[:13]].append((v, req[key][t]))
        out[key] = {h: (max(v for v, _ in vs), min(q for _, q in vs), statistics.mean(q for _, q in vs),
                        sum(v > q for v, q in vs), sum(max(v - q, 0) for v, q in vs) / MIB)
                    for h, vs in by.items() if len(vs) >= 30}
    return out


def gate_log(path: Path | None, gate_ns: str) -> dict:
    if path is None:
        return {}
    rows = {}
    for e in json.load(open(path)):
        m = SCORED.search(e.get("jsonPayload", {}).get("message", ""))
        if m and m[1].startswith(gate_ns + "/"):
            rows[(m[1], m[2])] = m.groups()
    return rows


def bound(raw: str) -> float | None:
    b = raw.strip('"')
    if "NaN" in b or "internal" in b:
        return None
    return {"+Inf": float("inf"), "-Inf": float("-inf")}.get(b) or float(b)


def rate(hrs: dict, since: str) -> tuple[int, int, float]:
    sel = [x for h, x in hrs.items() if h >= since]
    return len(sel), sum(p > r for p, r, *_ in sel), (statistics.mean(x[2] for x in sel) / MIB if sel else np.nan)


def replay(hrs: dict, since: str, factor: float, window_h: int = 24) -> tuple[int, int, float]:
    """Request = trailing max of the last `window_h` hourly peaks x factor, against the same hours' peaks."""
    keys = sorted(hrs)
    n = miss = 0
    reqs = []
    for i, h in enumerate(keys):
        past = [hrs[k][0] for k in keys[max(0, i - window_h):i]]
        if h < since or not past:
            continue
        r = max(past) * factor
        n, miss = n + 1, miss + (hrs[h][0] > r)
        reqs.append(r / MIB)
    return n, miss, (statistics.mean(reqs) if reqs else np.nan)


def compare(a: dict, b: dict) -> str:
    ws = sorted(set(a) & set(b))
    d = np.array([a[w] - b[w] for w in ws])
    rng = np.random.default_rng(0)
    lo, hi = np.percentile(d[rng.integers(0, len(d), (10000, len(d)))].mean(axis=1), [2.5, 97.5])
    p = wilcoxon(d).pvalue if np.any(d != 0) else 1.0
    return d.mean(), lo, hi, p, int((d < 0).sum()), int((d > 0).sum()), len(d)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("gate_ns")
    ap.add_argument("others", nargs="+")
    ap.add_argument("--gate-log")
    ap.add_argument("--vetoes")
    a = ap.parse_args()
    out = Path(a.out)
    arms = [a.gate_ns, *a.others]
    used, _ = series(out / "memory_used_bytes.json", "non-evictable")
    req, pods = series(out / "memory_request_bytes.json")
    hrs = hours(used, req)
    first = min(min(h) for h in hrs.values())
    run_start = f"{first[:11]}{int(first[11:13]) + 1:02d}"
    rows = gate_log(Path(a.gate_log) if a.gate_log else None, a.gate_ns)
    calib = {}  # first full hour after the workload's first calibrated decision
    for r in rows.values():
        if bound(r[4]) is not None:
            w = r[0].split("/")[2]
            h = (np.datetime64(r[1][:13]) + np.timedelta64(1, "h")).astype(str)[:13]
            calib[w] = min(calib.get(w, h), h)
    workloads = sorted({w for (ns, w) in hrs if ns == a.gate_ns})

    for label, since in (("whole run", lambda w: run_start), ("calibrated window", lambda w: calib.get(w, "9"))):
        print(f"\n## {label}: per-workload hours exceeded / hours (mean request MiB)")
        print("| workload | " + " | ".join(arms) + " |")
        print("|---|" + "---|" * len(arms))
        per = {ns: {} for ns in arms}
        tot = {ns: [0, 0, []] for ns in arms}
        for w in workloads:
            cells = []
            for ns in arms:
                n, m, mr = rate(hrs.get((ns, w), {}), since(w))
                if n:
                    per[ns][w] = m / n
                    tot[ns][0] += n
                    tot[ns][1] += m
                    tot[ns][2].append(mr)
                cells.append(f"{m}/{n} ({mr:.0f})" if n else "--")
            print(f"| {w} | " + " | ".join(cells) + " |")
        print("| **total** | " + " | ".join(f"{t[1]}/{t[0]} = {t[1] / max(t[0], 1):.3f} ({np.mean(t[2]):.0f})"
                                          for t in tot.values()) + " |")
        res = [(ns, *compare(per[a.gate_ns], per[ns])) for ns in a.others]
        order = np.argsort([r[4] for r in res])
        holm = np.minimum(1, np.maximum.accumulate([(len(res) - i) * res[j][4] for i, j in enumerate(order)]))
        print(f"\nWorkload-level, {a.gate_ns} minus other arm (per-workload exceedance rate): mean diff [95% bootstrap CI "
              "over workloads], Wilcoxon p, Holm p, workloads lower/higher")
        for i, j in enumerate(order):
            ns, md, lo, hi, p, lower, higher, n = res[j]
            print(f"- vs {ns}: {md:+.4f} [{lo:+.4f}, {hi:+.4f}], p = {p:.3g}, Holm p = {holm[i]:.3g}, "
                  f"{lower} lower / {higher} higher of {n}")
        print("\nReplayed trailing-24 h-max rules on the gate arm's usage (hours exceeded / hours, mean request MiB):")
        for f in (1.0, 1.15):
            n = m = 0
            rq = []
            for w in workloads:
                x = replay(hrs.get((a.gate_ns, w), {}), since(w), f)
                n, m = n + x[0], m + x[1]
                rq.append(x[2])
            print(f"- max(24 h) x {f}: {m}/{n} = {m / max(n, 1):.3f}, mean request {np.nanmean(rq):.0f}")

    print("\n## Operations per arm (whole run)")
    print("| arm | pods created | request changes | minutes over request | mean overrun MiB (when over) |")
    print("|---|---|---|---|---|")
    for ns in arms:
        keys = [k for k in hrs if k[0] == ns]
        changes = sum(sum(1 for x, y in zip(sorted(req[k].items()), sorted(req[k].items())[1:]) if x[1] != y[1])
                      for k in keys)
        over = sum(x[3] for k in keys for x in hrs[k].values())
        mins = sum(len(used[k]) for k in keys)
        ovr = sum(x[4] for k in keys for x in hrs[k].values())
        print(f"| {ns} | {sum(len(pods[k]) for k in keys)} | {changes} | {over}/{mins} = {over / max(mins, 1):.4f} | "
              f"{ovr / max(over, 1):.0f} |")

    if rows:
        cal = [(r, bound(r[4])) for r in rows.values() if bound(r[4]) is not None]
        fin = [(r, b) for r, b in cal if np.isfinite(b)]
        miss = sum(float(r[2]) > b for r, b in cal)
        per_ctr = collections.Counter(r[0] for r, _ in cal)
        print(f"\n## Gate log: scored {len(rows)}, calibrated {len(cal)}, bound misses {miss} ({miss / max(len(cal), 1):.4f}); "
              f"median bound slack over peak {np.median([(b - float(r[2])) / float(r[2]) for r, b in fin]):.3f}; "
              f"bound above 1 GiB limit {sum(b > 2**30 for _, b in fin)}; bound below candidate "
              f"{sum(b < float(r[3]) for r, b in fin)}; calibrated decisions per container "
              f"{min(per_ctr.values())}-{max(per_ctr.values())}")

    if a.vetoes:
        c = collections.Counter()
        for e in json.load(open(a.vetoes)):
            m = e["jsonPayload"]["message"]
            w = re.search(r"Skipping ([\w-]+)/([\w-]+)", m)
            if w and ("anomaly" in m or "memory leak" in m):
                c[(w[1], "anomaly" if "anomaly" in m else "leak")] += 1
        print("\n## Vetoes by other layers (log lines; one per reconcile, ~30 s):", dict(sorted(c.items())))


if __name__ == "__main__":
    main()
