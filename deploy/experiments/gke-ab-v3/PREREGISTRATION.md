# Live v3 run: analysis plan, fixed before launch

Written and committed before `run.sh up`; the commit hash and the start time in `out/started_at` date it.
Changes after launch are listed at the end, with reasons.

## Why a third run
v3 repeats the pre-registered v2 design (deploy/experiments/gke-ab-v2/PREREGISTRATION.md) unchanged except for the
controller. During v2 the controller was OOM-killed after 34 h. The cause was that its metrics store was never
garbage-collected, and restoring the unbounded backup then failed at start-up. Each restart erased the gate's
calibration. v2 was stopped on 2026-10-25T12:52Z. Its pre-incident segment is reported as exploratory, and v3 is
the confirmatory run.

## Design
- **Demand:** `pattern.sh` sets usage per 10-min wall-clock segment from (pattern, seed, segment) only. Every arm sees the same demand, and a restarted pod resumes at the clock's level.
- **Workloads:** 7 patterns (steady, cycle-1h, cycle-6h, spike, regime, leak-reset, noisy) x 3 seeds = 21 single-replica Deployments per arm. Initial request 512Mi, limit 1Gi.
- **Arms:**
  - `ab-gate`: ICO with memoryRiskBudget 0.05.
  - `ab-nogate`: ICO with no gate.
  - `ab-margin`: ICO with no gate and safetyMargin 1.65, chosen to match the gate's memory in v1.
  - `ab-vpa`: GKE VPA with updateMode Recreate, memory only, RequestsOnly, minReplicas 1, maxAllowed 1Gi.
- **Configuration:** the leak and anomaly vetoes are off in all ICO arms. The operator is at commit b70b4ce or later: gate raises bypass the change filters, a capped bound emits RiskBudgetUncertified, the controller's metrics store is garbage-collected (24 h retention), and pending approvals are de-duplicated. Controller memory limit 2Gi.
- **Duration and cluster:** 72 h on GKE, 4 x e2-highmem-4.

## Outcomes
**Primary:** for each workload, the fraction of hours in which the hourly peak of non-evictable memory exceeded the hour's minimum request.
- Data: GKE metrics at 60 s; an hour counts if it has >= 30 samples.
- Window: whole run, starting 1 h after launch.

**Secondary:**
- (a) The same outcome over the calibrated window, from the gate arm's first calibrated decision per workload. The same window is applied to the other arms.
- (b) Mean request in MiB.
- (c) Pod recreations, counted as distinct pod names.
- (d) Minutes over the request, and the mean overrun in MiB.
- (e) Gate log: the bound-miss rate, the bound slack over the peak, and the number of calibration scores per container.
- (f) RiskBudgetUncertified events.
- (g) Controller memory (non-evictable, hourly maximum) and restarts over the run; the store is expected to stay
  bounded after the first 24 h.

## Tests
- **Unit of analysis:** the workload (21 per arm).
- **Primary comparisons, paired by workload:** gate vs nogate, gate vs margin, gate vs vpa.
  - Wilcoxon signed-rank test on per-workload exceedance rates, Holm-corrected over these 3 comparisons.
  - Mean paired difference with a 95% bootstrap CI over workloads (10,000 resamples).
- **Hour-level counts** are reported descriptively only.
- **Reporting:** all four arms and all 21 workloads go in a per-workload table, whatever the result.

## Changes after launch
(none)
