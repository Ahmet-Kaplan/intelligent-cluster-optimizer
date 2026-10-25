import numpy as np
import pytest

from cgate.leak_conformal import (
    apply_blocks,
    leak_blocks,
    log_mixture_martingale,
    recent_slope,
    smoothed_pvalues,
)


def test_pvalues_uniform_under_exchangeability() -> None:
    rng = np.random.default_rng(0)
    p = smoothed_pvalues(rng.normal(size=3000), rng)
    assert abs(p.mean() - 0.5) < 0.02 and abs(np.mean(p < 0.1) - 0.1) < 0.02


def test_ville_bound_on_iid_scores() -> None:
    # P(ever S >= 1/lambda) <= lambda for exchangeable scores (Eq. ville), checked by simulation.
    rng = np.random.default_rng(1)
    lam, n_seq = 0.05, 600
    alarms = sum(np.nanmax(log_mixture_martingale(smoothed_pvalues(rng.normal(size=150), rng))) >= np.log(1 / lam)
                 for _ in range(n_seq))
    assert alarms / n_seq <= lam + 0.02


def test_martingale_detects_upward_drift() -> None:
    rng = np.random.default_rng(2)
    s = np.concatenate([rng.normal(size=80), rng.normal(size=70) + np.linspace(0.5, 4, 70)])
    for cusum in (False, True):
        log_s = log_mixture_martingale(smoothed_pvalues(s, rng), cusum=cusum)
        assert log_s[-1] > np.log(100) and log_s[:80].max() < np.log(100)


def test_nan_scores_are_skipped() -> None:
    p = smoothed_pvalues(np.array([np.nan, 1.0, np.nan, 2.0]), np.random.default_rng(0))
    assert np.isnan(p[0]) and np.isnan(p[2]) and np.isfinite(p[[1, 3]]).all()
    log_s = log_mixture_martingale(p)
    assert log_s[0] == pytest.approx(0.0) and log_s[2] == pytest.approx(log_s[1])


def test_slope_blocks_and_apply() -> None:
    h = np.arange(20.0)
    assert recent_slope(h, 10) == pytest.approx(1.0) and np.isnan(recent_slope(h, 2))
    blocked = leak_blocks(np.array([0, 10, 10]), np.array([1.0, -1.0, 1.0]), lam=0.01)
    np.testing.assert_array_equal(blocked, [False, False, True])
    np.testing.assert_array_equal(apply_blocks(np.array([5.0, 6.0, 7.0]), np.array([False, True, False])), [5, 5, 7])


def test_frozen_scores_use_reference_day_and_past_only() -> None:
    import importlib.util
    import pathlib

    spec = importlib.util.spec_from_file_location("le", pathlib.Path(__file__).parents[1] / "run" / "leak_eval.py")
    le = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(le)
    h = np.concatenate([np.tile(np.arange(24.0), 3), np.arange(24.0) + 10])     # day 3 shifted up by 10
    hours = np.arange(24, 96)
    s = le.frozen_scores(h, hours)
    assert np.isnan(s["frozen_profile"][0])                                     # hour 24: no completed hour yet
    np.testing.assert_allclose(s["frozen_profile"][1:48], 0.0)                  # days 1-2 equal the reference
    np.testing.assert_allclose(s["frozen_profile"][49:], 10.0)                  # shifted day: +10 everywhere
    g = h.copy()
    g[60:] = 999
    np.testing.assert_allclose(le.frozen_scores(g, hours)["frozen_level"][:37], s["frozen_level"][:37])


def test_thin_scores_block_means_and_nan_skip() -> None:
    from cgate.leak_conformal import thin_scores

    s = np.arange(12.0)
    t = thin_scores(s, 6)
    assert np.isnan(t[:5]).all() and t[5] == pytest.approx(2.5) and t[11] == pytest.approx(8.5)
    s[7] = np.nan
    assert np.isnan(thin_scores(s, 6)[11])
    np.testing.assert_array_equal(thin_scores(s, 1), s)


def test_thinning_reduces_autocorrelation_of_ar1() -> None:
    from cgate.leak_conformal import lag1_autocorr, thin_scores

    rng = np.random.default_rng(0)
    x = np.zeros(6000)
    for i in range(1, len(x)):
        x[i] = 0.8 * x[i - 1] + rng.normal()
    assert lag1_autocorr(x) > 0.7 and lag1_autocorr(thin_scores(x, 24)) < 0.3
