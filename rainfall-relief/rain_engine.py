#!/usr/bin/env python3
"""Rain-pulse engine: turn a stack of rasters (one per year/period) into a dataset
pulse.html can animate.

    pulse_data/<id>/years.bin   uint16 [period][row][col]; 65535 = no data; value =
                                store_min + q/65534 * (store_max - store_min)
    pulse_data/<id>/meta.json   labels, grid, bounds (lon/lat), ranges, palette, ...
    pulse_data/index.json       list of every dataset (read by the viewer)

Inputs: GeoTIFF / BIL / ASC / IMG rasters, loose or zipped (PRISM zips work as-is),
one file per period, or a single multi-band file with one band per period. Any CRS
with a definition: projected grids are reprojected to lon/lat, and rasters whose
grids differ from the first are resampled onto it. The grid is block-averaged so the
result stays browser-sized (<= ~300k cells, <= ~14M cell-periods).

Also: fetch_prism() downloads PRISM annual precipitation (4 km) for a year range.

Deps: numpy rasterio
"""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import time
import urllib.request
import warnings
import zipfile
from pathlib import Path
from typing import Callable, NamedTuple

# rasterio ships its own PROJ database; other installs (e.g. PostgreSQL/PostGIS) can
# shadow it via PROJ_LIB and break CRS lookups. Point at rasterio's before importing it.
try:
    import importlib.util
    _spec = importlib.util.find_spec("rasterio")
    if _spec and _spec.submodule_search_locations:
        _pd = Path(list(_spec.submodule_search_locations)[0]) / "proj_data"
        if _pd.is_dir():
            os.environ["PROJ_LIB"] = os.environ["PROJ_DATA"] = str(_pd)
except Exception:  # pragma: no cover - best effort only
    pass

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.warp import Resampling, calculate_default_transform, reproject

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "pulse_data"
RASTER_EXT = (".tif", ".tiff", ".bil", ".asc", ".img")
MAX_CELLS, MAX_CELL_PERIODS = 300_000, 14_000_000
Progress = Callable[[float, str], None]


class Source(NamedTuple):
    label: str
    path: Path
    band: int = 1


class EngineError(ValueError):
    """A problem with the user's data, worded for display in the UI."""


# --------------------------------------------------------------------------
# Input discovery
# --------------------------------------------------------------------------
def safe_extract(zpath: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    root = dest.resolve()
    with zipfile.ZipFile(zpath) as z:
        for m in z.infolist():
            target = (dest / m.filename).resolve()
            if root != target and root not in target.parents:
                raise EngineError(f"Unsafe path in zip: {m.filename}")
        z.extractall(dest)


def find_raster(folder: Path) -> Path | None:
    for ext in RASTER_EXT:                       # .tif beats .bil etc.
        hits = sorted(folder.rglob(f"*{ext}"))
        if hits:
            return hits[0]
    return None


def resolve_inputs(paths: list[Path], workdir: Path) -> list[Path]:
    """Unzip archives; return one raster path per input."""
    out = []
    for p in paths:
        if p.suffix.lower() == ".zip":
            dest = workdir / "unzipped" / p.stem
            safe_extract(p, dest)
            r = find_raster(dest)
            if r is None:
                raise EngineError(f"{p.name}: no raster ({', '.join(RASTER_EXT)}) inside the zip")
            out.append(r)
        elif p.suffix.lower() in RASTER_EXT:
            out.append(p)
        elif p.suffix.lower() in (".hdr", ".prj", ".xml", ".stx", ".aux", ".txt"):
            continue                              # sidecars travel with their raster
        else:
            raise EngineError(f"{p.name}: unsupported file type (use {', '.join(RASTER_EXT)} or .zip)")
    if not out:
        raise EngineError("No raster files found in the upload")
    return out


YEAR = re.compile(r"(?<!\d)(1[6-9]\d\d|20\d\d|21\d\d)(?!\d)")


def label_sources(paths: list[Path], start_label: int = 1) -> list[Source]:
    """Order rasters by the 4-digit year in their names; fall back to name order."""
    if len(paths) == 1:
        with rasterio.open(paths[0]) as ds:
            n = ds.count
        if n < 2:
            raise EngineError("Need at least 2 periods: upload 2+ files, or one multi-band file")
        return [Source(str(start_label + i), paths[0], i + 1) for i in range(n)]
    labelled = []
    for p in paths:
        m = YEAR.findall(p.stem)
        labelled.append((m[-1] if m else None, p))
    years = [y for y, _ in labelled]
    if all(years) and len(set(years)) == len(years):
        return [Source(y, p) for y, p in sorted(labelled, key=lambda t: int(t[0]))]
    return [Source(str(start_label + i), p) for i, p in enumerate(sorted(paths, key=lambda q: q.name.lower()))]


# --------------------------------------------------------------------------
# Raster handling
# --------------------------------------------------------------------------
def choose_decimation(h: int, w: int, nperiods: int) -> int:
    f = 1
    while (h // f) * (w // f) > MAX_CELLS or nperiods * (h // f) * (w // f) > MAX_CELL_PERIODS:
        f += 1
    return f


def block_nanmean(a: np.ndarray, f: int) -> np.ndarray:
    if f == 1:
        return a
    h, w = (a.shape[0] // f) * f, (a.shape[1] // f) * f
    blocks = a[:h, :w].reshape(h // f, f, w // f, f)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        return np.nanmean(blocks, axis=(1, 3))


class Grid(NamedTuple):
    crs: CRS
    transform: object
    shape: tuple[int, int]


def target_grid(path: Path) -> tuple[Grid, bool]:
    """Grid every period is put on. Returns (grid, needs_reproject_for_first)."""
    with rasterio.open(path) as ds:
        if ds.crs is None:
            raise EngineError(f"{path.name} has no coordinate system (CRS). Add a .prj / .hdr sidecar, "
                              "or save it as a GeoTIFF with a CRS.")
        t = ds.transform
        if t.b or t.d:
            raise EngineError(f"{path.name} is rotated/skewed; resample it to a north-up grid first.")
        if ds.crs.is_geographic:
            return Grid(ds.crs, t, (ds.height, ds.width)), False
        tf, w, h = calculate_default_transform(ds.crs, CRS.from_epsg(4326), ds.width, ds.height, *ds.bounds)
        return Grid(CRS.from_epsg(4326), tf, (h, w)), True


def read_period(src: Source, grid: Grid, first_native: bool) -> np.ndarray:
    with rasterio.open(src.path) as ds:
        a = ds.read(src.band, masked=True).astype("float32").filled(np.nan)
        same = (ds.crs == grid.crs and ds.transform == grid.transform and a.shape == grid.shape)
        crs, tf = ds.crs, ds.transform
    a[a <= -9000] = np.nan                        # unflagged -9999 style nodata
    a[~np.isfinite(a)] = np.nan
    if same:
        return a
    dst = np.full(grid.shape, np.nan, dtype="float32")
    reproject(a, dst, src_transform=tf, src_crs=crs, dst_transform=grid.transform, dst_crs=grid.crs,
              src_nodata=np.nan, dst_nodata=np.nan, resampling=Resampling.bilinear)
    return dst


# --------------------------------------------------------------------------
# Palettes shared with the viewer (positions are on the display axis 0..1)
# --------------------------------------------------------------------------
PALETTES = ("rain", "heat", "viridis", "blues")
PRISM_META = dict(label="US annual precipitation (PRISM)", unit="mm", palette="rain", scale="sqrt",
                  anomaly="ratio", disp_min=0.0, disp_max=6000.0, source="prism",
                  credit="PRISM Climate Group, Oregon State University, https://prism.oregonstate.edu "
                         "(annual precipitation, 4 km grid, averaged to ~8 km)")


# --------------------------------------------------------------------------
# Build
# --------------------------------------------------------------------------
def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40] or "dataset"


def build_dataset(sources: list[Source], out_dir: Path, *, label: str, unit: str = "",
                  palette: str = "viridis", scale: str = "linear", anomaly: str = "diff",
                  clip_outliers: bool = False, disp_min: float | None = None,
                  disp_max: float | None = None, source: str = "upload", credit: str = "",
                  progress: Progress | None = None) -> dict:
    say = progress or (lambda p, m: None)
    if len(sources) < 2:
        raise EngineError("Need at least 2 periods to animate")
    if palette not in PALETTES or scale not in ("sqrt", "linear") or anomaly not in ("ratio", "diff"):
        raise EngineError("Bad palette / scale / anomaly option")

    grid, native_first = target_grid(sources[0].path)
    f = choose_decimation(*grid.shape, len(sources))
    frames = []
    for i, s in enumerate(sources):
        say(0.05 + 0.75 * i / len(sources), f"Reading {s.label} ({i + 1}/{len(sources)})")
        frames.append(block_nanmean(read_period(s, grid, native_first), f))
    stack = np.stack(frames)
    if not np.isfinite(stack).any():
        raise EngineError("No valid (non-nodata) cells found in the rasters")

    smin, smax = float(np.nanmin(stack)), float(np.nanmax(stack))
    if smax <= smin:
        raise EngineError("All values are identical; nothing to animate")
    if disp_min is None or disp_max is None:
        if clip_outliers:
            disp_min, disp_max = (float(x) for x in np.nanpercentile(stack, [2, 98]))
        else:
            disp_min, disp_max = smin, smax
    if disp_max <= disp_min:
        disp_min, disp_max = smin, smax

    say(0.85, "Packing")
    rows, cols = stack.shape[1:]
    t = grid.transform
    dx, dy = t.a * f, -t.e * f
    if dy <= 0:
        raise EngineError("Raster rows run south-to-north; flip it to a north-up grid first.")
    bounds = [t.c, t.f - rows * dy, t.c + cols * dx, t.f]
    q = np.where(np.isfinite(stack),
                 np.clip(np.rint((stack - smin) / (smax - smin) * 65534), 0, 65534), 65535).astype("<u2")

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "years.bin").write_bytes(q.tobytes())
    meta = dict(id=out_dir.name, label=label, unit=unit, palette=palette, scale=scale, anomaly=anomaly,
                years=[s.label for s in sources], rows=rows, cols=cols, bounds=bounds, decimate=f,
                store_min=smin, store_max=smax, disp_min=float(disp_min), disp_max=float(disp_max),
                source=source, credit=credit, built=int(time.time()))
    (out_dir / "meta.json").write_text(json.dumps(meta))
    register(meta)
    say(1.0, "Done")
    return meta


def register(meta: dict) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    idx_path = DATA / "index.json"
    try:
        idx = json.loads(idx_path.read_text())
    except (FileNotFoundError, ValueError):
        idx = []
    keys = ("id", "label", "unit", "source", "built")
    entry = {k: meta[k] for k in keys} | {"first": meta["years"][0], "last": meta["years"][-1],
                                          "count": len(meta["years"])}
    idx = [e for e in idx if e["id"] != meta["id"]] + [entry]
    tmp = idx_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(sorted(idx, key=lambda e: (e["source"] != "prism", e["id"]))))
    tmp.replace(idx_path)


# --------------------------------------------------------------------------
# PRISM
# --------------------------------------------------------------------------
PRISM_URL = "https://services.nacse.org/prism/data/get/us/4km/ppt/{y}"


def prism_dir(y: int) -> Path:
    return ROOT / "prism_annual" / str(y)


def fetch_prism(start: int, end: int, progress: Progress | None = None) -> list[Source]:
    """Ensure PRISM annual precipitation for start..end is on disk; return its sources."""
    say = progress or (lambda p, m: None)
    if not (1895 <= start < end <= time.gmtime().tm_year):
        raise EngineError("Pick a range inside 1895 to the present, with at least 2 years")
    if end - start + 1 > 60:
        raise EngineError("Please keep the range to 60 years or fewer")
    base = ROOT / "prism_annual"
    base.mkdir(exist_ok=True)
    srcs = []
    n = end - start + 1
    for i, y in enumerate(range(start, end + 1)):
        raster = find_raster(prism_dir(y)) if prism_dir(y).is_dir() else None
        if raster is None:
            say(0.02 + 0.5 * i / n, f"Downloading PRISM {y} ({i + 1}/{n})")
            zpath = base / f"{y}.zip"
            try:
                with urllib.request.urlopen(PRISM_URL.format(y=y), timeout=120) as r, open(zpath, "wb") as fh:
                    shutil.copyfileobj(r, fh)
                safe_extract(zpath, prism_dir(y))
            except Exception as e:                # network, 404 for a year not published, bad zip
                zpath.unlink(missing_ok=True)
                raise EngineError(f"Could not get PRISM data for {y}: {e}") from e
            raster = find_raster(prism_dir(y))
            if raster is None:
                raise EngineError(f"PRISM {y}: download contained no raster")
            time.sleep(0.7)                       # be polite to the public service
        srcs.append(Source(str(y), raster))
    return srcs


def build_prism(start: int, end: int, progress: Progress | None = None) -> dict:
    srcs = fetch_prism(start, end, progress)
    meta = dict(PRISM_META)
    meta["label"] = f"US annual precipitation (PRISM) {start}-{end}"
    return build_dataset(srcs, DATA / f"prism-{start}-{end}", progress=_sub(progress, 0.5, 1.0), **meta)


def _sub(progress: Progress | None, lo: float, hi: float) -> Progress | None:
    if progress is None:
        return None
    return lambda p, m: progress(lo + (hi - lo) * p, m)
