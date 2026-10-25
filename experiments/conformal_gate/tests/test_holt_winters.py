import numpy as np
import pytest

from cgate.holt_winters import ALPHA, BETA, GAMMA, _go_grid, fit_predict, hourly_max


def test_grid_matches_go_float_loop() -> None:
    assert len(_go_grid(0.1, 0.9, 0.1)) == 9 and len(_go_grid(0.01, 0.5, 0.05)) == 10
    assert len(ALPHA) == len(BETA) == len(GAMMA) == 900


def test_constant_series_forecasts_constant_with_zero_width() -> None:
    q = fit_predict(np.full(72, 40.0), quantiles=(0.5, 0.9))
    np.testing.assert_allclose(q, [40.0, 40.0], atol=1e-9)


def test_pure_daily_season_is_tracked() -> None:
    t = np.arange(24 * 5)
    y = 50 + 10 * np.sin(2 * np.pi * t / 24)
    q50, q90 = fit_predict(y, quantiles=(0.5, 0.9))
    assert q50 == pytest.approx(50 + 10 * np.sin(2 * np.pi * len(t) / 24), abs=1.0)
    assert q90 >= q50


def test_needs_two_seasons() -> None:
    with pytest.raises(ValueError):
        fit_predict(np.ones(47))


def test_hourly_max_and_gap_fill() -> None:
    u = np.arange(180.0)
    u[60:120] = np.nan
    np.testing.assert_array_equal(hourly_max(u), [59, 59, 179])
