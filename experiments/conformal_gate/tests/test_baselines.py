import numpy as np
import pytest

from cgate import (
    OLSLeakConfig,
    SimConfig,
    decision_steps,
    fixed_headroom,
    gate_metrics,
    ico,
    is_leak,
    sizing_metrics,
    vpa,
)
from cgate.leak_ols import count_resets, ols_slope_r2

SIM = SimConfig(step_s=60, warmup_steps=120, every_steps=60)
LEAK = OLSLeakConfig()


def test_ols_matches_exact_line() -> None:
    t = np.arange(50) / 60.0
    slope, r2 = ols_slope_r2(t, 3.0 * t + 7)
    assert slope == pytest.approx(3.0) and r2 == pytest.approx(1.0)


def test_ols_slope_threshold_nonbinding() -> None:
    # 0.013 %/h of an 8 GB machine already exceeds the Go threshold of 1 MiB/h.
    assert 0.013 / 100 * 8 * 1024**3 > LEAK.slope_threshold_bytes_per_h


def test_is_leak_on_clean_growth_but_not_on_noise_or_gc() -> None:
    rng = np.random.default_rng(0)
    n = 61                                                                         # 60 min span
    assert not is_leak(np.linspace(40, 50, 60), 60, LEAK)                          # 59 min < MinDuration
    assert is_leak(np.linspace(40, 50, n) + rng.normal(0, 0.1, n), 60, LEAK)       # +25 %/h, R^2 ~ 1
    assert not is_leak(40 + rng.normal(0, 0.5, n), 60, LEAK)                       # flat
    sawtooth = 40 + 15 * (np.arange(n) % 15) / 15 + np.linspace(0, 6, n)           # ~25 % GC drops / 15 min
    assert count_resets(sawtooth, LEAK.reset_threshold) > LEAK.max_resets
    assert not is_leak(sawtooth, 60, LEAK)
    assert not is_leak(np.linspace(40, 50, 10), 60, LEAK)                          # < min_samples


def test_policies_never_look_ahead() -> None:
    rng = np.random.default_rng(1)
    u = 30 + rng.normal(0, 1, 600)
    v = u.copy()
    t = decision_steps(len(u), SIM)[2]
    v[t:] += 50                                                                    # change only the future
    for f in (lambda x: vpa(x, SIM), lambda x: fixed_headroom(x, SIM), lambda x: ico(x, SIM, LEAK)[0]):
        np.testing.assert_allclose(f(u)[:3], f(v)[:3])


def test_ico_gate_holds_previous_request_while_leaking() -> None:
    u = np.concatenate([np.full(240, 40.0) + np.random.default_rng(2).normal(0, 0.2, 240), np.linspace(40, 80, 240)])
    req_g, blocked = ico(u, SIM, LEAK, leak_window_steps=120)
    req_n, _ = ico(u, SIM, None)
    k = np.flatnonzero(blocked)
    assert len(k) and decision_steps(len(u), SIM)[k[0]] >= 240                    # blocks only after leak starts
    assert np.all(req_g[k] == req_g[k[0] - 1])                                     # previous request kept
    assert req_n[-1] > req_g[-1]                                                   # ungated engine follows the leak up


def test_sizing_metrics_on_constant_usage() -> None:
    u = np.full(600, 10.0)
    steps = decision_steps(len(u), SIM)
    m = sizing_metrics(u, np.full(len(steps), 20.0), SIM)
    assert m["slack"] == pytest.approx(0.5) and m["violation_rate"] == 0 and m["changes"] == 0
    assert sizing_metrics(u, np.full(len(steps), 5.0), SIM)["violation_rate"] == 1


def test_gate_metrics_split_at_onset() -> None:
    n = 600
    steps = decision_steps(n, SIM)
    blocked = steps >= 300
    leak = gate_metrics(blocked, 1, 300, n, SIM)
    assert leak["false_blocks"] == 0 and leak["detected"] and leak["delay_h"] == 0
    healthy = gate_metrics(blocked, 0, -1, n, SIM)
    assert healthy["false_blocks"] == blocked.sum() and np.isnan(healthy["detected"])
