#!/usr/bin/env python3
"""Drought-index engine: turn the PRISM annual-precipitation rasters into drought indices
that drought.html can map and chart.

    python drought_engine.py                       # 1991-2023, baseline 1991-2020
    python drought_engine.py --years 1991 2023 --baseline 1991 2020

Per-year layers (one grid per year, int16/int8, see LAYERS) written to
drought_data/prism-<start>-<end>/<layer>.bin.gz as [year][row][col]:

    spi      Standardized Precipitation Index, 12-month scale (annual total), gamma fit
    pn       Percent of Normal (% of baseline mean)
    z        Z-score (standardized anomaly)
    rai      Rainfall Anomaly Index (van Rooy 1965)
    decile   Precipitation decile 1-10 (1 = driest 10% of baseline years)
    deficit  Departure from baseline mean (mm; negative = drier than normal)
    dryrun   Consecutive years with SPI < 0, ending that year

Period summaries (float32, summary.bin.gz, one grid each, see SUMMARY): drought frequency,
severity, worst SPI and when, longest dry spell, coefficient of variation.

The baseline (default 1991-2020, the current 30-year normal) is used for every fit, so
years after it are scored against it. Deps: numpy scipy rasterio (via rain_engine).
"""
from __future__ import annotations

import argparse
import gzip
import json
import time
from pathlib import Path

import numpy as np
from scipy.special import gammainc
from scipy.stats import norm

import rain_engine as eng

OUT = eng.ROOT / "drought_data"
NA16, NA8 = -32768, -128

# name: (label, unit, numpy dtype, scale: stored = value * scale)
LAYERS = {
    "spi":     ("SPI (12-month)",        "",    "<i2", 1000),
    "pn":      ("Percent of normal",     "%",   "<i2", 10),
    "z":       ("Z-score",               "",    "<i2", 1000),
    "rai":     ("Rainfall Anomaly Index", "",   "<i2", 1000),
    "decile":  ("Precipitation decile",  "",    "i1",  1),
    "deficit": ("Departure from normal", "mm",  "<i2", 1),
    "dryrun":  ("Consecutive dry years", "yr",  "i1",  1),
}
SUMMARY = ["freq", "severity", "min_spi", "worst_year", "longest_dry", "cv"]
DROUGHT_SPI = -1.0                         # "drought" = SPI at or below this (moderate or worse)


def load_stack(start: int, end: int, progress=None) -> tuple[np.ndarray, list[str], dict]:
    srcs = eng.fetch_prism(start, end, progress)
    grid, native = eng.target_grid(srcs[0].path)
    f = eng.choose_decimation(*grid.shape, len(srcs))
    frames = [eng.block_nanmean(eng.read_period(s, grid, native), f) for s in srcs]
    stack = np.stack(frames).astype("float32")
    t = grid.transform
    rows, cols = stack.shape[1:]
    dx, dy = t.a * f, -t.e * f
    geo = dict(rows=rows, cols=cols, decimate=f, bounds=[t.c, t.f - rows * dy, t.c + cols * dx, t.f])
    return stack, [s.label for s in srcs], geo


def gamma_fit(base: np.ndarray):
    """Per-cell gamma parameters (Thom 1958 MLE approximation) plus the zero fraction."""
    zero = (base == 0).mean(axis=0)
    pos = np.where(base > 0, base, np.nan)
    with np.errstate(all="ignore"):
        m = np.nanmean(pos, axis=0)
        a = np.log(m) - np.nanmean(np.log(pos), axis=0)
        alpha = (1 + np.sqrt(1 + 4 * a / 3)) / (4 * a)
        beta = m / alpha
    bad = ~np.isfinite(alpha) | (alpha <= 0) | ~np.isfinite(beta)
    return np.where(bad, np.nan, alpha), np.where(bad, np.nan, beta), zero


def compute(stack: np.ndarray, base_idx: np.ndarray) -> dict[str, np.ndarray]:
    base = stack[base_idx]
    valid = np.isfinite(base).all(axis=0)
    stack = np.where(valid, stack, np.nan)
    base = stack[base_idx]
    with np.errstate(all="ignore"):
        mean, std = base.mean(axis=0), base.std(axis=0, ddof=1)
        alpha, beta, q0 = gamma_fit(base)
        cdf = q0 + (1 - q0) * gammainc(alpha, stack / beta)
        cdf = np.clip(cdf, 1e-4, 1 - 1e-4)
        spi = np.clip(norm.ppf(cdf), -3.5, 3.5)
        srt = np.sort(base, axis=0)
        k = max(1, round(base.shape[0] * 0.1))
        hi, lo = srt[-k:].mean(axis=0), srt[:k].mean(axis=0)
        dep = stack - mean
        rai = np.where(dep >= 0, 3 * dep / (hi - mean), -3 * dep / (lo - mean))
        decile = np.clip(np.ceil(cdf * 10), 1, 10)
        dry = (spi < 0)
        run = np.zeros_like(spi)
        for i in range(stack.shape[0]):
            run[i] = np.where(dry[i], (run[i - 1] if i else 0) + 1, 0)
        out = dict(spi=spi, pn=stack / mean * 100, z=dep / std, rai=rai, decile=decile,
                   deficit=dep, dryrun=run)
    for k_, v in out.items():
        v[~np.isfinite(v) | ~valid[None]] = np.nan
    return out, valid, spi, mean


def summaries(spi: np.ndarray, years: list[str], stack: np.ndarray, valid: np.ndarray) -> np.ndarray:
    T = spi.shape[0]
    drought = spi <= DROUGHT_SPI
    best, cur = np.zeros(spi.shape[1:]), np.zeros(spi.shape[1:])
    for i in range(T):                                       # longest run of SPI < 0
        cur = np.where(spi[i] < 0, cur + 1, 0)
        best = np.maximum(best, cur)
    with np.errstate(all="ignore"):
        s = dict(
            freq=drought.mean(axis=0) * 100,
            severity=np.where(drought, -spi, 0).sum(axis=0),
            min_spi=np.nanmin(spi, axis=0),
            worst_year=np.array([int(y) for y in years], dtype="float32")[np.nanargmin(np.where(valid, spi, 9), axis=0)],
            longest_dry=best,
            cv=np.nanstd(stack, axis=0, ddof=1) / np.nanmean(stack, axis=0) * 100,
        )
    out = np.stack([s[k] for k in SUMMARY]).astype("float32")
    out[:, ~valid] = np.nan
    return out


def quantize(a: np.ndarray, dtype: str, scale: int) -> np.ndarray:
    na = NA8 if dtype == "i1" else NA16
    hi = 127 if dtype == "i1" else 32767
    q = np.clip(np.rint(a * scale), -hi, hi)
    return np.where(np.isfinite(a), q, na).astype(dtype)


def gz(b: bytes) -> bytes:
    return gzip.compress(b, 9, mtime=0)       # browsers unzip with DecompressionStream


def build(start: int, end: int, b0: int, b1: int, progress=None) -> dict:
    say = progress or (lambda p, m: None)
    say(0.0, "Loading PRISM annual precipitation")
    stack, years, geo = load_stack(start, end, progress)
    ys = np.array([int(y) for y in years])
    base_idx = (ys >= b0) & (ys <= b1)
    if base_idx.sum() < 20:
        raise eng.EngineError("Baseline needs at least 20 years for a stable gamma fit")
    say(0.6, "Computing indices")
    layers, valid, spi, mean = compute(stack, base_idx)

    d = OUT / f"prism-{start}-{end}"
    d.mkdir(parents=True, exist_ok=True)
    meta_layers = {}
    for name, (label, unit, dtype, scale) in LAYERS.items():
        say(0.7 + 0.2 * len(meta_layers) / len(LAYERS), f"Writing {name}")
        (d / f"{name}.bin.gz").write_bytes(gz(quantize(layers[name], dtype, scale).tobytes()))
        meta_layers[name] = dict(label=label, unit=unit, dtype=dtype, scale=scale,
                                 na=NA8 if dtype == "i1" else NA16)
    summ = summaries(spi, years, stack, valid)
    (d / "summary.bin.gz").write_bytes(gz(summ.astype("<f4").tobytes()))
    meta = dict(id=d.name, years=years, baseline=[b0, b1], drought_spi=DROUGHT_SPI, layers=meta_layers,
                summary=SUMMARY, mean_range=[float(np.nanmin(mean)), float(np.nanmax(mean))],
                credit="PRISM Climate Group, Oregon State University, https://prism.oregonstate.edu "
                       "(annual precipitation, 4 km, averaged to ~8 km)",
                built=int(time.time()), **geo)
    (d / "meta.json").write_text(json.dumps(meta))
    say(1.0, "Done")
    return meta


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--years", type=int, nargs=2, default=[1991, 2023], metavar=("START", "END"))
    ap.add_argument("--baseline", type=int, nargs=2, default=[1991, 2020], metavar=("START", "END"))
    a = ap.parse_args()
    m = build(*a.years, *a.baseline, progress=lambda p, s: print(f"{p:4.0%} {s}"))
    print(f"wrote drought_data/{m['id']}: {len(m['years'])} years, {m['rows']}x{m['cols']} cells")


if __name__ == "__main__":
    try:
        main()
    except eng.EngineError as e:
        raise SystemExit(f"error: {e}")
