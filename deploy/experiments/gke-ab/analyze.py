"""Final A/B table for the live GKE run of the conformal admission gate.

Usage: analyze.py OUT_DIR

Window: for each workload, from the gate-on container's first calibrated decision to the end of the run;
the same window is used for the workload's gate-off twin. Ground truth is GKE's 60-s non-evictable memory,
binned into wall-clock hours (an hour counts when it has >= 30 samples).
"""
import collections
import json
import re
import statistics
import sys
from pathlib import Path

SCORED = re.compile(r'key="([^"]+)" at="([^"]+)" peak=(\S+) upper=(\S+) bound=(.+?) alpha=(\S+)$')


def bound_value(raw: str) -> float | None:
    b = raw.strip('"')
    if "NaN" in b or "internal" in b:  # cold start (NaN is logged as a JSON error string)
        return None
    return {"+Inf": float("inf"), "-Inf": float("-inf")}.get(b) or float(b)


def gate_decisions(out: Path) -> dict:
    rows = {}
    for e in json.load(open(out / "controller-gate.json")):
        m = SCORED.search(e.get("jsonPayload", {}).get("message", ""))
        if m:
            rows[(m[1], m[2])] = m.groups()
    return rows


def series(path: Path, memory_type: str | None = None) -> dict:
    d = collections.defaultdict(dict)
    for s in json.load(open(path)):
        if memory_type and s["metric"]["labels"].get("memory_type") != memory_type:
            continue
        r = s["resource"]["labels"]
        key = (r["namespace_name"], r["pod_name"].rsplit("-", 2)[0])
        for p in s["points"]:
            t = p["interval"]["endTime"][:16]
            d[key][t] = max(d[key].get(t, 0), int(p["value"]["int64Value"]))
    return d


def main(out: Path) -> None:
    rows = gate_decisions(out)
    calibrated = [(r, bound_value(r[4])) for r in rows.values() if bound_value(r[4]) is not None]
    misses = [r for r, b in calibrated if float(r[2]) > b]
    start = {}
    for r, _ in calibrated:
        w = r[0].split("/")[2]
        start[w] = min(start.get(w, r[1]), r[1])
    print(f"gate log: scored={len(rows)} calibrated={len(calibrated)} misses={len(misses)} "
          f"rate={len(misses) / len(calibrated):.4f} +Inf={sum(b == float('inf') for _, b in calibrated)}")
    finite = [(b - float(r[2])) / float(r[2]) for r, b in calibrated if abs(b) != float("inf")]
    print(f"gate log: median relative bound slack over peak = {statistics.median(finite):.3f}")

    used = series(out / "memory_used_bytes.json", "non-evictable")
    req = series(out / "memory_request_bytes.json")
    print("\narm       container-hours  peak>request  rate    median-slack  minutes-over  mean-request-MiB")
    for ns in ("gate-on", "gate-off"):
        hours = miss = over = total = 0
        slack, reqs = [], []
        for (n, w), u in used.items():
            if n != ns or w not in start:
                continue
            by_hour = collections.defaultdict(list)
            for t, v in u.items():
                if t >= start[w][:16] and t in req.get((n, w), {}):
                    by_hour[t[:13]].append((v, req[(n, w)][t]))
            for vs in by_hour.values():
                if len(vs) < 30:
                    continue
                peak, rq = max(v for v, _ in vs), min(q for _, q in vs)
                hours += 1
                miss += peak > rq
                slack.append((rq - peak) / rq)
                reqs.append(statistics.mean(q for _, q in vs) / 2**20)
                over += sum(v > q for v, q in vs)
                total += len(vs)
        print(f"{ns:9} {hours:15d}  {miss:12d}  {miss / hours:.4f}  {statistics.median(slack):12.3f}"
              f"  {over / total:12.4f}  {statistics.mean(reqs):16.0f}")

    restarts = collections.Counter()
    for s in json.load(open(out / "restart_count.json")):
        ns = s["resource"]["labels"]["namespace_name"]
        restarts[ns] += max(int(p["value"]["int64Value"]) for p in s["points"])
    print("\ncontainer restarts:", dict(restarts))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
