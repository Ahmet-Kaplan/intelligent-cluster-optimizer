# Live GKE A/B run of the operator's conformal admission gate

Run: GKE Standard zonal cluster ico-gate-ab (us-central1-a, 2x e2-standard-4, Kubernetes 1.35.6-gke.1250001),
controller image us-central1-docker.pkg.dev/<gcp-project>/optimizer/controller:gate-2669eb3 (operator commit 90173a5; gate unchanged since 77218d1 apart from one log line).
Controller start 2026-10-21T11:42:42Z; data collected and cluster deleted at 2026-10-23T11:42Z (48 h).
Arms: namespaces gate-on (memoryRiskBudget 0.05, ACI eta 0.005, window 168, horizon 1 h) and gate-off (0),
otherwise identical OptimizerConfigs (strategy balanced, live mode, minSamples 24, history 24 h).
Workloads per arm: 9 single-replica stress-ng memory patterns (steady, cycle-1h, cycle-6h, spike x2, regime,
leak-reset, noisy x2), initial request 512Mi, limit 1Gi; manifests in operator repo deploy/experiments/gke-ab/.
Ground truth: GKE system metric kubernetes.io/container/memory/used_bytes (non-evictable, 60 s) and
memory/request_bytes; window per workload = from the gate-on container's first calibrated decision to the end;
hours with >= 30 samples. Gate decisions: Cloud Logging lines "conformal decision scored".
Command: python3 deploy/experiments/gke-ab/analyze.py out (operator commit 9abf288).

```
gate log: scored=404 calibrated=233 misses=2 rate=0.0086 +Inf=0
gate log: median relative bound slack over peak = 0.662

arm       container-hours  peak>request  rate    median-slack  minutes-over  mean-request-MiB
gate-on               254             0  0.0000         0.398        0.0000               706
gate-off              254            16  0.0630         0.166        0.0085               510

container restarts: {'gate-off': 0, 'gate-on': 0}
```

Derived (computed 2026-10-23 from the table above):
- Fisher exact test, two-sided, 0/254 vs 16/254 hours with peak > request: p = 2.39e-05
- Wilson 95% CI: gate-on [0, 0.0149]; gate-off [0.0391, 0.0999]; gate log 2/233 [0.0024, 0.0308]
- First calibrated gate decision 2026-10-22T06:59Z (first scored decision 2026-10-21T11:54Z).
- Gate-off misses: spike 13 h (request 245Mi, peak 606Mi), regime 3 h (request 245Mi, peak 455Mi); the 2 gate-log misses (noisy,
  cycle-1h) have bound < candidate, so the applied request max(candidate, bound) covered the peak.
