"""Inject synthetic memory leaks and hard negatives into healthy traces (ground truth for the leak gate).

All functions are pure: they return a new array and never modify the input.
Memory is in percent of machine memory (Alibaba units) and is clipped to [0, 100].
"""

from dataclasses import dataclass

import numpy as np

LEAK_SHAPES = ("linear", "step", "sqrt", "load_coupled")
NEGATIVE_SHAPES = ("load_growth", "warmup", "level_shift")


@dataclass(frozen=True)
class Injection:
    mem: np.ndarray
    label: int          # 1 = leak, 0 = healthy (incl. hard negatives)
    shape: str
    onset: int          # index where the injected behaviour starts (-1 if none)
    rate_per_hour: float  # leak rate as fraction of baseline memory per hour (0 for negatives)


def _baseline(mem: np.ndarray) -> float:
    return float(np.nanmedian(mem))


def inject_leak(mem: np.ndarray, cpu: np.ndarray, shape: str, rate_per_hour: float,
                onset: int, step_s: int = 60, rng: np.random.Generator | None = None) -> Injection:
    """Add a leak that starts at `onset` and grows at `rate_per_hour` x baseline memory.

    Shapes: linear; step (allocations in bursts every ~15 min, same mean rate);
    sqrt (sub-linear, scaled to match the linear leak at 24 h); load_coupled (growth proportional to CPU load).
    """
    if shape not in LEAK_SHAPES:
        raise ValueError(f"unknown leak shape {shape!r}; expected one of {LEAK_SHAPES}")
    if not 0 <= onset < len(mem):
        raise ValueError(f"onset {onset} outside series of length {len(mem)}")
    rng = rng or np.random.default_rng(0)
    hours = np.maximum(np.arange(len(mem)) - onset, 0) * step_s / 3600.0
    amp = rate_per_hour * _baseline(mem)
    if shape == "linear":
        add = amp * hours
    elif shape == "step":
        period = max(1, int(900 / step_s))
        inc = np.zeros(len(mem))
        burst_idx = np.arange(onset + period, len(mem), period)
        inc[burst_idx] = amp * period * step_s / 3600.0 * rng.uniform(0.5, 1.5, len(burst_idx))
        add = np.cumsum(inc)  # leaked memory never frees
    elif shape == "sqrt":
        add = amp * np.sqrt(hours * 24.0)
    else:  # load_coupled
        load = np.nan_to_num(cpu, nan=0.0) / max(np.nanmean(cpu), 1e-9)
        add = np.cumsum(np.where(hours > 0, load, 0.0)) * amp * step_s / 3600.0
    return Injection(np.clip(mem + add, 0, 100), 1, shape, onset, rate_per_hour)


def inject_negative(mem: np.ndarray, cpu: np.ndarray, shape: str, onset: int,
                    magnitude: float = 0.3, step_s: int = 60) -> Injection:
    """Add healthy behaviour that a naive trend detector mistakes for a leak.

    load_growth: memory follows a 24 h ramp in load. The caller must scale CPU by the same `ramp`,
                 otherwise this is indistinguishable from a leak by construction.
    warmup: saturating cache fill, 1 - exp(-t / 2 h).
    level_shift: new deployment with a higher steady state.
    """
    if shape not in NEGATIVE_SHAPES:
        raise ValueError(f"unknown negative shape {shape!r}; expected one of {NEGATIVE_SHAPES}")
    hours = np.maximum(np.arange(len(mem)) - onset, 0) * step_s / 3600.0
    base = magnitude * _baseline(mem)
    if shape == "load_growth":
        add = base * ramp(len(mem), onset, step_s)
    elif shape == "warmup":
        add = base * (1 - np.exp(-hours / 2.0))
    else:
        add = np.where(hours > 0, base, 0.0)
    return Injection(np.clip(mem + add, 0, 100), 0, shape, onset, 0.0)


def ramp(n: int, onset: int, step_s: int = 60, hours: float = 24.0) -> np.ndarray:
    """0 before onset, linear to 1 over `hours`, then 1. Apply to CPU too for load_growth negatives."""
    t = (np.arange(n) - onset) * step_s / 3600.0
    return np.clip(t / hours, 0.0, 1.0)
