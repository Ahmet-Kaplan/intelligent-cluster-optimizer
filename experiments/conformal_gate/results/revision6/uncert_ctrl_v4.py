"""v4 outcome (f) and (g). Usage: python3 uncert_v4.py OUTDIR UNTIL(ISO Z)"""
import json, re, sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta

out, until = sys.argv[1], sys.argv[2]
RAISE = re.compile(r"Risk budget [\d.]+ raised memory for ab-gate/Deployment/([\w-]+)/mem: \d+ -> (\d+)")
CAP = re.compile(r"Capping recommended Memory for ab-gate/([\w-]+)/mem: (\d+) -> \d+ \(limit\)")
MSG = re.compile(r'^\s*"message": "(.*)",?$')
TS = re.compile(r'^\s*"timestamp": "([^"]+)"')

ev, msg = [], None  # ponytail: line scan of gcloud's pretty JSON, 1.8 GB file won't fit json.load
with open(f"{out}/controller-full.json") as f:
    for line in f:
        m = MSG.match(line)
        if m:
            msg = m.group(1) if ("Capping" in line or "Risk budget" in line) else None
            continue
        t = TS.match(line)
        if t and msg:
            ev.append((t.group(1)[:26], msg))
            msg = None
ev.sort()
last_raise = {}
paired, unpaired, per_wl = 0, 0, Counter()
for ts, m in ev:
    if ts >= until:
        continue
    r = RAISE.search(m)
    if r:
        last_raise[r.group(1)] = (ts, r.group(2))
        continue
    c = CAP.search(m)
    if not c:
        continue
    lr = last_raise.get(c.group(1))
    t0 = datetime.fromisoformat(lr[0]) if lr else None
    if lr and lr[1] == c.group(2) and datetime.fromisoformat(ts) - t0 < timedelta(seconds=60):
        paired += 1
        per_wl[c.group(1)] += 1
    else:
        unpaired += 1
print(f"(f) uncertified (capping line after same-container raise, <60 s, same value): {paired}; other capping lines: {unpaired}")
print("    per workload:", dict(sorted(per_wl.items())))

# (g) controller: hourly max non-evictable memory, restart count
mem = json.load(open(f"{out}/controller_memory_used_bytes.json"))
hourly = defaultdict(float)
for s in mem:
    if s["metric"].get("labels", {}).get("memory_type") != "non-evictable":
        continue
    for p in s["points"]:
        t = p["interval"]["endTime"]
        if t >= until:
            continue
        v = float(p["value"].get("int64Value", p["value"].get("doubleValue", 0)))
        hourly[t[:13]] = max(hourly[t[:13]], v)
vals = [v / 2**20 for _, v in sorted(hourly.items())]
print(f"(g) controller non-evictable hourly max MiB: min {min(vals):.0f}, median {sorted(vals)[len(vals)//2]:.0f}, "
      f"max {max(vals):.0f}, last {vals[-1]:.0f} over {len(vals)} h")
rs = json.load(open(f"{out}/controller_restart_count.json"))
mx = max(int(p["value"].get("int64Value", 0)) for s in rs for p in s["points"])
pods = {s["resource"]["labels"]["pod_name"] for s in mem}
print(f"(g) controller restart_count max: {mx}; controller pods: {len(pods)}")
