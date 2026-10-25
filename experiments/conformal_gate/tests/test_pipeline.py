import numpy as np
import pandas as pd
import pytest

from cgate import (
    LEAK_SHAPES,
    NEGATIVE_SHAPES,
    SelectionConfig,
    inject_leak,
    inject_negative,
    load_alibaba,
    resample,
    select,
)

N = 3 * 1440  # 3 days at 60 s


def healthy(seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    t = np.arange(N)
    cpu = 20 + 10 * np.sin(2 * np.pi * t / 1440) + rng.normal(0, 1, N)
    mem = 40 + rng.normal(0, 0.5, N)
    return mem, cpu


@pytest.mark.parametrize("shape", LEAK_SHAPES)
def test_leak_grows_after_onset_only_and_keeps_input(shape: str) -> None:
    mem, cpu = healthy()
    before = mem.copy()
    inj = inject_leak(mem, cpu, shape, rate_per_hour=0.02, onset=N // 2)
    np.testing.assert_array_equal(mem, before)                     # pure
    np.testing.assert_allclose(inj.mem[: N // 2], mem[: N // 2])   # nothing before onset
    added = inj.mem - mem
    assert added[-1] > 0.02 * 40 * 6                                # > 6 h of linear-rate growth after 36 h
    assert np.all(np.diff(added[N // 2:]) >= -1e-9)                 # leaked memory never frees
    assert inj.label == 1 and inj.onset == N // 2


def test_linear_leak_rate_is_exact() -> None:
    mem = np.full(N, 50.0)
    inj = inject_leak(mem, mem, "linear", rate_per_hour=0.01, onset=0)
    assert inj.mem[60] - 50.0 == pytest.approx(0.5)                 # 1 h * 1% * 50


def test_leak_clipped_to_100_percent() -> None:
    mem, cpu = healthy()
    assert inject_leak(mem, cpu, "linear", 1.0, onset=0).mem.max() <= 100


@pytest.mark.parametrize("shape", NEGATIVE_SHAPES)
def test_negatives_are_labelled_healthy_and_bounded(shape: str) -> None:
    mem, cpu = healthy()
    inj = inject_negative(mem, cpu, shape, onset=N // 2, magnitude=0.3)
    assert inj.label == 0
    assert (inj.mem - mem).max() <= 0.3 * np.median(mem) + 1e-9     # saturates, unlike a leak


def test_bad_inputs_raise() -> None:
    mem, cpu = healthy()
    with pytest.raises(ValueError):
        inject_leak(mem, cpu, "nope", 0.01, 0)
    with pytest.raises(ValueError):
        inject_leak(mem, cpu, "linear", 0.01, N + 1)


def test_load_resample_select_roundtrip(tmp_path) -> None:
    rows = []
    for c in range(9):
        ts = np.arange(0, 3 * 86_400 + 600, 10)                    # Alibaba ~10 s sampling
        cpu = 20 + (c + 1) * np.random.default_rng(c).normal(0, 1, len(ts)).clip(-5, 5)
        rows += [[f"c_{c}", "m_1", t, u, 40, 0, 0, 0, 0, 0, 0] for t, u in zip(ts, cpu)]
    rows.append(["c_short", "m_1", 0, 10, 40, 0, 0, 0, 0, 0, 0])  # too short, must be dropped
    path = tmp_path / "container_usage.csv"
    pd.DataFrame(rows).to_csv(path, header=False, index=False)

    series = resample(load_alibaba(path, chunksize=50_000))
    assert len(series["c_0"]) >= 3 * 1440
    chosen = select(series, SelectionConfig(per_stratum=2))
    assert "c_short" not in set(chosen["container_id"])
    assert len(chosen) == 6 and set(chosen["stratum"]) == {"stable", "periodic", "bursty"}


def test_missing_trace_raises(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        load_alibaba(tmp_path / "missing.csv")


def test_binned_streaming_matches_plain_load(tmp_path) -> None:
    rng = np.random.default_rng(1)
    ts = np.arange(0, 7200, 10)
    rows = [[f"c_{c}", "m", t, rng.uniform(0, 50), rng.uniform(0, 50), 0, 0, 0, 0, 0, 0]
            for c in range(40) for t in ts]
    path = tmp_path / "cu.csv"
    pd.DataFrame(rows).to_csv(path, header=False, index=False)

    plain = resample(load_alibaba(path))
    binned = resample(load_alibaba(path, chunksize=997, bin_s=60))  # odd chunks: bins straddle chunk edges
    assert plain.keys() == binned.keys()
    for cid in plain:
        np.testing.assert_allclose(plain[cid].to_numpy(), binned[cid].to_numpy(), rtol=1e-6)

    a = set(load_alibaba(path, keep_frac=0.3)["container_id"])
    b = set(load_alibaba(path, chunksize=333, keep_frac=0.3)["container_id"])
    assert a == b and 0 < len(a) < 40                               # deterministic, chunk-independent
