# Test-count and coverage audit (2026-10-20)

Measured on voximul (Go 1.26.4, linux/amd64). Code state = what the paper describes:
intelligent-cluster-optimizer `370fc98` + local fix `d2c48a4` (leak gate wired into the reconciler),
optimizer-test `c107d18` + local fix `1422b7b` (6 stale Holt-Winters inputs). Neither fix is pushed.
optimizer-test was pointed at the code via a temporary modfile replace (its go.mod is untouched).

## Test counts
| Suite | Result |
|---|---|
| optimizer-test unit + integration (before test fix) | 1098 pass, 6 fail, 1 skip |
| optimizer-test unit + integration (after test fix) | 1104 pass, 1 skip (= 1105) |
| optimizer-test e2e (needs kind; counted from source, not executed) | 13 |
| **Dedicated suite total** | **1118** (matches the paper; README's "600+" is stale) |
| In-package tests in intelligent-cluster-optimizer (incl. 5 new leak-gate tests) | 914 pass |
| **All automated tests** | **2032** |

The 6 failures: `TestHoltWinters_{ValidInput,StepIndexing,PointOrdering,ConstantSeries}` and
`TestIntegration_Fallback_ML{ServiceUnavailable,ServiceTimeout}`. The cause is "insufficient data: need at least 120
points (1 seasons), got 60". FallbackForecaster uses `PodMetricsConfig` (season 120), and the tests predate that change.

## Statement coverage (`-covermode=atomic -coverpkg=.../pkg/...`, blocks merged by max count)
| Scope | Coverage |
|---|---|
| Dedicated suite (unit + integration) only | 79.5% (5380/6770) |
| In-package tests only (at 370fc98) | 64.3% |
| **All tests merged** | **85.1% (5760/6770)** |

Per package, all tests merged: events 100.0, applier 70.3, cost 98.3, scheduler 96.7, pareto 95.9,
recommendation 89.9, leakdetector 91.9, webhook 96.3, controller 44.5.
The paper's previous figures (80.3% merged; applier 98.1, webhook 56.8, controller 45.7, leak detector 83.1)
could not be reproduced at any combination of these suites.

## The former "83% leak-detector accuracy"
- No test or script in either repository produces 83% detection accuracy.
- `TestLeakDetector_DetectionAccuracy85Percent` reports 100.0% (10/10 synthetic patterns).
- 83% matches the leakdetector package's test **coverage** in commit 4f7afbe ("leakdetector 83%") and in the paper's old Table II (83.1%).
- Replaced in the paper by the 10/10 acceptance test and the trace-driven leak study (results/leak_gate_*.md).
