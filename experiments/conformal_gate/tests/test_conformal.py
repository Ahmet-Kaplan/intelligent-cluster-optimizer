import numpy as np
import pytest

from cgate.conformal import ConformalConfig, aci_bounds, gate_requests, min_calibration, peak_targets
from cgate.forecast import QUANTILES, build_inputs, envelopes


def test_peak_targets() -> None:
    u = np.array([1, 5, 2, np.nan, np.nan, 3.0])
    np.testing.assert_array_equal(peak_targets(u, np.array([0, 3]), 3), [5, 3])


def test_cold_start_then_finite_bounds() -> None:
    cfg = ConformalConfig(eps=0.1, eta=0.0)
    rng = np.random.default_rng(0)
    y = rng.normal(10, 1, 50)
    b, _ = aci_bounds(np.full(50, 10.0), y, cfg)
    n0 = min_calibration(0.1)                                     # 9 scores needed
    assert np.all(np.isnan(b[:n0])) and np.all(np.isfinite(b[n0:]))


def test_no_look_ahead_in_bounds() -> None:
    cfg = ConformalConfig(eps=0.1)
    y = np.random.default_rng(1).normal(10, 1, 60)
    z = y.copy()
    z[30:] += 100
    b1, _ = aci_bounds(np.full(60, 10.0), y, cfg)
    b2, _ = aci_bounds(np.full(60, 10.0), z, cfg)
    np.testing.assert_array_equal(b1[:31], b2[:31])               # Y_30 first used at decision 31


@pytest.mark.parametrize("eps", [0.05, 0.1, 0.2])
def test_split_conformal_coverage_on_exchangeable_data(eps: float) -> None:
    # Marginal guarantee P(Y > U_hat) <= eps under exchangeability (Proposition 1), checked by simulation.
    rng = np.random.default_rng(42)
    cfg = ConformalConfig(eps=eps, eta=0.0, window=10_000)
    y = rng.gamma(2.0, 1.0, 4000)                                 # skewed, like memory peaks
    b, _ = aci_bounds(np.zeros(4000), y, cfg)
    ok = np.isfinite(b)
    miss = np.mean(y[ok] > b[ok])
    assert miss <= eps + 0.01 and miss >= eps - 0.03             # valid and not wildly conservative


def test_aci_tracks_target_under_shift() -> None:
    # Level shift the forecaster does not see: static conformal breaks, ACI recovers long-run miscoverage.
    rng = np.random.default_rng(3)
    y = np.concatenate([rng.normal(10, 1, 1500), rng.normal(13, 1, 1500)])
    upper = np.full(3000, 10.0)
    miss = {}
    for eta in (0.0, 0.01):
        b, _ = aci_bounds(upper, y, ConformalConfig(eps=0.1, eta=eta, window=168))
        ok = np.isfinite(b)
        miss[eta] = np.mean(y[1500:][ok[1500:]] > b[1500:][ok[1500:]])
    assert abs(miss[0.01] - 0.1) < 0.03


def test_gate_modes() -> None:
    cand = np.array([5.0, 5.0, 12.0, 5.0])
    bounds = np.array([np.nan, 8.0, 8.0, 8.0])
    req, cold = gate_requests(cand, bounds, "modify")
    np.testing.assert_array_equal(req, [5, 8, 12, 8]) and np.testing.assert_array_equal(cold, [1, 0, 0, 0])
    np.testing.assert_array_equal(gate_requests(cand, bounds, "veto")[0], [5, 5, 12, 12])
    np.testing.assert_array_equal(gate_requests(cand, bounds, "size")[0], [5, 8, 8, 8])
    uncertifiable = gate_requests(np.array([10.0, 4.0]), np.array([np.nan, np.inf]), "modify")[0]
    np.testing.assert_array_equal(uncertifiable, [10, 10])                       # no scale-down when alpha <= 0
    with pytest.raises(ValueError):
        gate_requests(cand, bounds, "nope")


class _FakePipe:
    """Stands in for Chronos2Pipeline: quantile q of a constant forecast equal to last value + 10 q."""

    def predict_quantiles(self, items, prediction_length, quantile_levels, batch_size):
        import torch
        out = []
        for it in items:
            base = float(it["target"][-1])
            q = torch.tensor([[[base + 10 * ql + h * 0.1 for ql in quantile_levels] for h in range(prediction_length)]])
            out.append(q)
        return out, None


def test_build_inputs_and_envelopes() -> None:
    pytest.importorskip("torch")
    mem, cpu = np.arange(100.0), np.arange(100.0) * 2
    items = build_inputs(mem, cpu, np.array([50, 80]), context=30, covariate=True)
    assert len(items[0]["target"]) == 30 and items[0]["target"][-1] == 49            # strictly before t
    assert "cpu" in items[1]["past_covariates"]
    env, med = envelopes(_FakePipe(), items, horizon=5)
    i9 = QUANTILES.index(0.9)
    assert env[0, i9] == pytest.approx(49 + 9 + 0.4) and med.shape == (2, 5)


def test_eval_container_end_to_end() -> None:
    import importlib.util
    import pathlib

    import pandas as pd
    from omegaconf import OmegaConf

    from cgate import SimConfig, decision_steps

    spec = importlib.util.spec_from_file_location("ce", pathlib.Path(__file__).parents[1] / "run" / "conformal_eval.py")
    ce = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ce)
    sim = SimConfig(step_s=60, warmup_steps=120, every_steps=60)
    mem = 40 + np.random.default_rng(0).normal(0, 1, 3000)
    k = np.arange(len(decision_steps(len(mem), sim)))
    fc = pd.concat([pd.DataFrame({"k": k, "variant": v, "env_q0.9": 41.0}) for v in ("univariate", "covariate")])
    cfg = OmegaConf.create({"variants": ["univariate", "covariate"], "eps": [0.1], "eta": [0.0, 0.005],
                            "modes": ["size", "modify", "veto"], "tau0": 0.9, "window": 168})
    rows = ce.eval_container(mem, fc, sim, cfg)
    assert len(rows) == 2 * 2 * 3
    modify = next(r for r in rows if r["mode"] == "modify" and r["eta"] == 0.0)
    assert modify["bound_miss_rate"] <= 0.25 and 0 < modify["cold_frac"] < 0.3


def test_size_mode_floors_nonpositive_bounds_and_metrics_count_them() -> None:
    from cgate import SimConfig, sizing_metrics
    from cgate.conformal import MIN_REQUEST

    req, _ = gate_requests(np.array([5.0, 5.0]), np.array([-3.0, 0.0]), "size")
    assert np.all(req == MIN_REQUEST)
    sim = SimConfig(step_s=60, warmup_steps=60, every_steps=60)
    u = np.full(180, 10.0)
    m = sizing_metrics(u, np.array([0.0, 20.0]), sim)                        # a zero request is not skipped
    assert m["horizons"] == 2 and m["violation_rate"] == 0.5
