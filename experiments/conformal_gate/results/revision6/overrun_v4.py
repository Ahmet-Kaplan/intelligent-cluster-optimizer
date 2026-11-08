"""Descriptive, not pre-registered: overrun size (peak - min request) in each exceedance hour, calibrated window.
Run from deploy/experiments/gke-ab-v4: python3 overrun_v4.py out 2026-11-06T14:03"""
import sys
sys.path.insert(0, "..")
import live_report as L

out, until = L.Path(sys.argv[1]), sys.argv[2]
used, _ = L.series(out / "memory_used_bytes.json", "non-evictable", until)
req, _ = L.series(out / "memory_request_bytes.json", until=until)
for (ns, w), hs in sorted(L.hours(used, req).items()):
    rows = [(k, (v[0] - v[1]) / 1024, v[1] / 2**20) for k, v in sorted(hs.items()) if k >= "2026-11-04T10" and v[0] > v[1]]
    if rows:  # ponytail: calibrated window hard-coded as 2026-11-04T10 (all workloads' first calibrated hour, report)
        print(ns, w, "; ".join(f"{k[5:]} +{o:.0f} KiB over {r:.0f} MiB" for k, o, r in rows))
