"""Load and resample per-container usage from the Alibaba cluster-trace v2018."""

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Schema of container_usage.csv (no header) in alibaba/clusterdata cluster-trace-v2018.
ALIBABA_COLUMNS = [
    "container_id", "machine_id", "time_stamp", "cpu_util_percent", "mem_util_percent",
    "cpi", "mem_gps", "mpki", "net_in", "net_out", "disk_io_percent",
]
KEEP = ["container_id", "time_stamp", "cpu_util_percent", "mem_util_percent"]
_HASH_BUCKETS = 10_000


def _keep_mask(ids: pd.Series, keep_frac: float) -> np.ndarray:
    """Deterministic container subsample: same ids kept on every run and every chunk."""
    h = pd.util.hash_pandas_object(ids, index=False).to_numpy()
    return (h % _HASH_BUCKETS) < int(keep_frac * _HASH_BUCKETS)


def load_alibaba(path: Path | str, chunksize: int = 5_000_000, keep_frac: float = 1.0,
                 bin_s: int | None = None) -> pd.DataFrame:
    """Stream container_usage.csv in chunks, keeping only CPU/memory columns.

    The full trace (29 GB gzipped) does not fit in RAM or on a small disk, so it can be piped in
    (`path="-"`, e.g. `curl ... | tar -xzO | prepare.py`) and reduced chunk by chunk.

    Args:
        path: Path to container_usage.csv, or "-" for stdin.
        chunksize: Rows per chunk.
        keep_frac: Fraction of containers to keep (hash-based, deterministic).
        bin_s: If set, reduce each chunk to per-container max over `bin_s`-second bins.
            Memory then scales with containers x bins, not with rows.

    Returns:
        Long-format frame with columns container_id, time_stamp (s), cpu, mem (percent of machine).
    """
    src = sys.stdin if str(path) == "-" else Path(path)
    if isinstance(src, Path) and not src.exists():
        raise FileNotFoundError(f"Alibaba trace not found: {src}")
    parts = []
    reader = pd.read_csv(src, header=None, names=ALIBABA_COLUMNS, usecols=KEEP, chunksize=chunksize,
                         dtype={"container_id": str, "time_stamp": np.int64,
                                "cpu_util_percent": np.float32, "mem_util_percent": np.float32})
    for i, chunk in enumerate(reader):
        if keep_frac < 1.0:
            chunk = chunk[_keep_mask(chunk["container_id"], keep_frac)]
        chunk = chunk.dropna()
        if bin_s:
            chunk = (chunk.assign(time_stamp=chunk["time_stamp"] // bin_s * bin_s)
                     .groupby(["container_id", "time_stamp"], as_index=False).max())
        parts.append(chunk)
        if i % 20 == 0:
            if bin_s:  # the trace is not time-sorted, so one bin recurs across chunks: merge to bound RAM
                parts = [_merge_bins(parts)]
            logger.info("chunk %d: kept %d rows (%d so far)", i, len(chunk), sum(map(len, parts)))
    if not parts:
        return pd.DataFrame(columns=["container_id", "time_stamp", "cpu", "mem"])
    df = _merge_bins(parts) if bin_s else pd.concat(parts, ignore_index=True)
    return df.rename(columns={"cpu_util_percent": "cpu", "mem_util_percent": "mem"})


def _merge_bins(parts: list[pd.DataFrame]) -> pd.DataFrame:
    return pd.concat(parts, ignore_index=True).groupby(["container_id", "time_stamp"], as_index=False).max()


def resample(df: pd.DataFrame, step_s: int = 60) -> dict[str, pd.DataFrame]:
    """Resample each container to a regular grid (max within bin, then forward-fill short gaps).

    Max, not mean, because the gate reasons about peak demand (OOM risk).
    Gaps longer than 5 steps stay NaN so selection can reject sparse containers.
    """
    out: dict[str, pd.DataFrame] = {}
    for cid, g in df.groupby("container_id"):
        g = g.assign(t=pd.to_datetime(g["time_stamp"], unit="s")).set_index("t").sort_index()
        r = g[["cpu", "mem"]].resample(f"{step_s}s").max().ffill(limit=5)
        out[str(cid)] = r
    return out
