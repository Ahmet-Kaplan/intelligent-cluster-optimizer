import numpy as np
import pytest

from cgate.fm_models import DECILES, ffill, from_deciles, left_pad
from cgate.forecast import QUANTILES
from cgate.hourly_baselines import START, features, fold_of, lgbm_predict, seasonal_naive


def test_from_deciles_maps_available_levels_only() -> None:
    paths = np.broadcast_to(np.array(DECILES, dtype=np.float32), (2, 3, 9))
    out = from_deciles(paths)
    assert out[0, 0, QUANTILES.index(0.9)] == pytest.approx(0.9)
    assert np.isnan(out[0, 0, QUANTILES.index(0.99)])


def test_left_pad_masks_padding_and_nans() -> None:
    x, m = left_pad([np.array([1.0, np.nan, 3.0]), np.array([5.0])])
    np.testing.assert_array_equal(x, [[1, 0, 3], [0, 0, 5]])
    np.testing.assert_array_equal(m, [[1, 0, 1], [0, 0, 1]])


def test_ffill_handles_leading_and_inner_gaps() -> None:
    np.testing.assert_array_equal(ffill(np.array([np.nan, 2.0, np.nan, 4.0])), [2, 2, 2, 4])


def test_seasonal_naive_on_pure_daily_pattern() -> None:
    h = np.tile(np.arange(24.0), 4)
    q = seasonal_naive(h, 72)
    np.testing.assert_allclose(q, h[48])                          # zero residuals -> all quantiles = yesterday


def test_features_are_scale_free_and_use_past_only() -> None:
    h = np.random.default_rng(0).uniform(10, 20, 100)
    f1, f2 = features(h, 60), features(h * 7, 60)
    np.testing.assert_allclose(f1[:-1], f2[:-1])
    g = h.copy()
    g[60:] = 999
    np.testing.assert_allclose(features(g, 60), f1)


def test_lgbm_predict_scales_back_and_sorts() -> None:
    class Const:
        def __init__(self, r: float) -> None:
            self.r = r

        def predict(self, X: np.ndarray) -> np.ndarray:
            return np.full(len(X), self.r)

    h = np.full(80, 10.0)
    models = [Const(r) for r in (1.2, 1.0, 1.1, 1.3, 1.4)]           # deliberately crossed
    out = lgbm_predict(models, h, np.array([START - 1, START]))
    assert np.all(np.isnan(out[0]))
    np.testing.assert_allclose(out[1], [10, 11, 12, 13, 14])


def test_fold_assignment_is_deterministic() -> None:
    assert fold_of("c_123") == fold_of("c_123") and {fold_of(f"c_{i}") for i in range(50)} == {0, 1}


def test_fit_quantile_models_end_to_end() -> None:
    try:
        import lightgbm  # noqa: F401
    except OSError as e:  # e.g. macOS without libomp; runs on the Linux server
        pytest.skip(f"lightgbm native library unavailable: {e}")
    from cgate.hourly_baselines import LGBMConfig, fit_quantile_models

    rng = np.random.default_rng(0)
    series = [50 + 5 * np.sin(np.arange(150) * 2 * np.pi / 24) + rng.normal(0, 1, 150) for _ in range(6)]
    models = fit_quantile_models(series, LGBMConfig(n_estimators=30))
    q = lgbm_predict(models, series[0], np.arange(START, 150))
    assert q.shape == (150 - START, len(QUANTILES)) and np.all(np.diff(q, axis=1) >= 0)
    assert np.mean(series[0][START:] <= q[:, QUANTILES.index(0.9)]) > 0.7    # roughly calibrated in-sample


def test_left_pad_rounds_up_to_patch_multiple() -> None:
    x, m = left_pad([np.ones(33), np.ones(5)], multiple=32)
    assert x.shape == (2, 64) and m[0].sum() == 33 and m[1].sum() == 5 and not m[:, :31].any()
