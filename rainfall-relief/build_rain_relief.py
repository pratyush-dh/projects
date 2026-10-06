#!/usr/bin/env python3
"""Rainfall-as-relief tile builder.

Turns a PRISM annual precipitation normal (mm) into everything the MapLibre
viewer (index.html) needs:

    out/tiles/dem_linear/{z}/{x}/{y}.png   Mapbox terrain-RGB, height = mm
    out/tiles/dem_sqrt/{z}/{x}/{y}.png     Mapbox terrain-RGB, height = sqrt(mm * mm_max)
    out/tiles/color/{z}/{x}/{y}.png        RGBA colour ramp with baked hillshade
    out/isohyets.geojson                   contour lines (true mm values)
    out/meta.json                          mm_max, bounds, zooms, ramp, levels

Input: PRISM 800 m (or 4 km) annual precipitation normal, e.g. the 1991-2020
normals from https://prism.oregonstate.edu/normals/ (BIL or GeoTIFF, mm,
geographic NAD83, nodata -9999). A .bil needs its .hdr/.prj sidecars.

Deps: numpy scipy rasterio scikit-image shapely pyproj pillow affine

Assumptions worth knowing:
  * Resampling is applied to precipitation VALUES, never to encoded RGB.
    Bilinear for z >= 7, average for z <= 6 (coarser than the source grid).
  * Ocean / nodata is height 0 in the DEM tiles and transparent in the colour
    tiles, so land stands as a plateau above a flat sea. Coastlines of wet
    regions therefore read as cliffs. That's real data, not an artifact.
  * Tiles are Web Mercator (EPSG:3857) because the viewer is. Heights are in
    "metres" 1:1 with mm (linear) so MapLibre's exaggeration slider is the
    only vertical scale. Hillshade is baked at --shade-ve and does not react
    to the slider.
  * Memory: the full source array is held in RAM as float32
    (800 m CONUS ~ 7025 x 3105 ~ 90 MB). Contouring decimates first.
  * Whole-tile reprojection from one in-memory array is simple, not fast.
    Expect minutes for z3-8 at 800 m. Use --zmax 7 for a quick pass.
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import warnings
from pathlib import Path

import numpy as np
import rasterio
from affine import Affine
from PIL import Image
from pyproj import Transformer
from rasterio.crs import CRS
from rasterio.transform import array_bounds, from_bounds
from rasterio.warp import Resampling, reproject, transform_bounds
from scipy import ndimage as ndi
from shapely.geometry import LineString
from skimage import measure

log = logging.getLogger("rain_relief")

ORIGIN = 20037508.342789244  # half the Web Mercator world width, metres
TILE = 256

# (mm, colour) stops; interpolated in sqrt(mm) space so the dry end keeps detail.
RAMP: list[tuple[float, str]] = [
    (0, "#6b3d1e"),
    (150, "#b57a3c"),
    (300, "#d9b66a"),
    (500, "#e8e2a6"),
    (800, "#a9d18e"),
    (1100, "#5fb58a"),
    (1500, "#2a9d9a"),
    (2000, "#1f7aa8"),
    (3000, "#2a4fa0"),
    (4500, "#432a85"),
    (6000, "#7a2a8f"),
]

DEFAULT_LEVELS = [100, 200, 300, 400, 500, 750, 1000, 1250, 1500, 1750,
                  2000, 2500, 3000, 4000, 5000]
MAJOR_LEVELS = {250, 500, 1000, 2000, 3000, 4000}


# --------------------------------------------------------------------------
# Input
# --------------------------------------------------------------------------
def load_precip(path: Path) -> tuple[np.ndarray, Affine, CRS]:
    """Read band 1 as float32 mm with NaN for nodata. Returns (data, transform, crs)."""
    if not path.exists():
        raise FileNotFoundError(f"Input raster not found: {path}")
    with rasterio.open(path) as ds:
        if ds.crs is None:
            raise ValueError(f"{path} has no CRS (is the .prj/.hdr sidecar next to it?)")
        data = ds.read(1, masked=True).astype("float32").filled(np.nan)
        transform, crs = ds.transform, ds.crs
    data[data < 0] = np.nan  # belt and braces for unflagged -9999
    if not np.isfinite(data).any():
        raise ValueError("Raster contains no valid precipitation cells")
    log.info("Loaded %s: %s, CRS=%s, range %.0f-%.0f mm",
             path.name, data.shape, crs.to_string(),
             np.nanmin(data), np.nanmax(data))
    return data, transform, crs


# --------------------------------------------------------------------------
# Tile maths
# --------------------------------------------------------------------------
def tile_bounds(z: int, x: int, y: int) -> tuple[float, float, float, float]:
    """(left, bottom, right, top) in EPSG:3857 metres for an XYZ tile."""
    size = 2 * ORIGIN / 2**z
    left = -ORIGIN + x * size
    top = ORIGIN - y * size
    return left, top - size, left + size, top


def tiles_in_bbox(z: int, bbox: tuple[float, float, float, float]):
    """Yield (x, y) XYZ tiles at zoom z intersecting a 3857 bbox."""
    size = 2 * ORIGIN / 2**z
    n = 2**z
    minx, miny, maxx, maxy = bbox
    x0 = max(0, int(math.floor((minx + ORIGIN) / size)))
    x1 = min(n - 1, int(math.floor((maxx + ORIGIN) / size)))
    y0 = max(0, int(math.floor((ORIGIN - maxy) / size)))
    y1 = min(n - 1, int(math.floor((ORIGIN - miny) / size)))
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            yield x, y


def warp_tile(data: np.ndarray, src_tf: Affine, src_crs: CRS,
              bounds: tuple[float, float, float, float], z: int,
              margin: int = 1) -> np.ndarray:
    """Reproject precip into a (TILE+2*margin)^2 EPSG:3857 window (NaN = no data)."""
    n = TILE + 2 * margin
    left, bottom, right, top = bounds
    res = (right - left) / TILE
    dst_tf = from_bounds(left - margin * res, bottom - margin * res,
                         right + margin * res, top + margin * res, n, n)
    dst = np.full((n, n), np.nan, dtype="float32")
    reproject(
        source=data, destination=dst,
        src_transform=src_tf, src_crs=src_crs,
        dst_transform=dst_tf, dst_crs=CRS.from_epsg(3857),
        src_nodata=np.nan, dst_nodata=np.nan,
        resampling=Resampling.average if z <= 6 else Resampling.bilinear,
    )
    return dst


# --------------------------------------------------------------------------
# Encoding / rendering
# --------------------------------------------------------------------------
def to_height(precip: np.ndarray, mode: str, mm_max: float) -> np.ndarray:
    """Relief height in metres. NaN -> 0 (flat sea).

    linear: h = mm
    sqrt:   h = sqrt(mm * mm_max)  (same max as linear, lifts the dry/mid range)
    """
    p = np.nan_to_num(precip, nan=0.0)
    if mode == "linear":
        return p
    if mode == "sqrt":
        return np.sqrt(p * mm_max)
    raise ValueError(mode)


def encode_terrain_rgb(h: np.ndarray) -> np.ndarray:
    """Mapbox terrain-RGB: h = -10000 + (R*65536 + G*256 + B) * 0.1."""
    v = np.clip(np.round((h + 10000.0) * 10.0), 0, 2**24 - 1).astype(np.uint32)
    return np.dstack([(v >> 16) & 255, (v >> 8) & 255, v & 255]).astype(np.uint8)


def _hex(c: str) -> tuple[int, int, int]:
    return int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)


def apply_ramp(precip: np.ndarray) -> np.ndarray:
    """(H, W) mm -> (H, W, 3) float RGB 0-255, interpolated in sqrt(mm)."""
    xs = np.sqrt([s[0] for s in RAMP])
    cols = np.array([_hex(s[1]) for s in RAMP], dtype="float32")
    x = np.sqrt(np.nan_to_num(precip, nan=0.0))
    return np.dstack([np.interp(x, xs, cols[:, i]) for i in range(3)])


def hillshade(h: np.ndarray, cell: float, ve: float,
              azimuth: float = 315.0, altitude: float = 45.0) -> np.ndarray:
    """Lambertian shade, normalised so a flat surface == 1.0. cell in metres."""
    gy, gx = np.gradient(h.astype("float64"), cell)
    dzdx, dzdy = gx, -gy  # rows run south, so flip for north-positive
    nx, ny, nz = -ve * dzdx, -ve * dzdy, np.ones_like(h, dtype="float64")
    norm = np.sqrt(nx**2 + ny**2 + nz**2)
    az, alt = math.radians(azimuth), math.radians(altitude)
    lx, ly, lz = math.cos(alt) * math.sin(az), math.cos(alt) * math.cos(az), math.sin(alt)
    shade = (nx * lx + ny * ly + nz * lz) / norm
    return np.clip(shade / math.sin(alt), 0.0, 1.8)


def fill_nearest(a: np.ndarray) -> np.ndarray:
    """Fill NaN with nearest valid value (for shading only, avoids coast cliffs)."""
    bad = ~np.isfinite(a)
    if not bad.any():
        return a
    if bad.all():
        return np.zeros_like(a)
    idx = ndi.distance_transform_edt(bad, return_distances=False, return_indices=True)
    return a[tuple(idx)]


def render_color_tile(window: np.ndarray, z: int, mm_max: float, ve: float) -> np.ndarray:
    """RGBA uint8 tile (TILE x TILE) from a 1-px-margin precip window."""
    res = 2 * ORIGIN / 2**z / TILE
    h_fill = to_height(fill_nearest(window), "sqrt", mm_max)
    shade = hillshade(h_fill, res, ve)[1:-1, 1:-1]
    core = window[1:-1, 1:-1]
    rgb = apply_ramp(core) * (0.4 + 0.6 * shade)[..., None]
    alpha = np.where(np.isfinite(core), 255, 0)
    return np.dstack([np.clip(rgb, 0, 255), alpha]).astype(np.uint8)


def _save(arr: np.ndarray, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(arr).save(path)


def build_tiles(data: np.ndarray, tf: Affine, crs: CRS, out: Path,
                zmin: int, zmax: int, mm_max: float, ve: float) -> tuple:
    """Render all three tile sets. Returns the WGS84 bounds (w, s, e, n)."""
    h, w = data.shape
    bbox = transform_bounds(crs, CRS.from_epsg(3857), *array_bounds(h, w, tf))
    wgs = transform_bounds(crs, CRS.from_epsg(4326), *array_bounds(h, w, tf))
    for z in range(zmin, zmax + 1):
        tiles = list(tiles_in_bbox(z, bbox))
        log.info("z%d: %d tiles", z, len(tiles))
        for x, y in tiles:
            win = warp_tile(data, tf, crs, tile_bounds(z, x, y), z)
            core = win[1:-1, 1:-1]
            for mode in ("linear", "sqrt"):
                _save(encode_terrain_rgb(to_height(core, mode, mm_max)),
                      out / "tiles" / f"dem_{mode}" / str(z) / str(x) / f"{y}.png")
            _save(render_color_tile(win, z, mm_max, ve),
                  out / "tiles" / "color" / str(z) / str(x) / f"{y}.png")
    return wgs


# --------------------------------------------------------------------------
# Isohyets
# --------------------------------------------------------------------------
def block_nanmean(a: np.ndarray, f: int) -> np.ndarray:
    h, w = (a.shape[0] // f) * f, (a.shape[1] // f) * f
    blocks = a[:h, :w].reshape(h // f, f, w // f, f)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        return np.nanmean(blocks, axis=(1, 3))


def build_isohyets(data: np.ndarray, tf: Affine, crs: CRS, levels: list[int],
                   decimate: int = 3, sigma: float = 1.0,
                   simplify_deg: float = 0.004, min_len_deg: float = 0.25) -> dict:
    """Contour the decimated, lightly smoothed grid. Output is WGS84 GeoJSON.

    Smoothing (gaussian, `sigma` in decimated cells) removes stair-stepping but
    shifts contours slightly in steep terrain: cosmetic, not for measurement.
    Contours are masked to land so lines don't trace the coast.
    """
    small = block_nanmean(data, decimate)
    valid = np.isfinite(small)
    smooth = ndi.gaussian_filter(fill_nearest(small), sigma)
    tf_s = tf * Affine.scale(decimate)
    to_wgs = None if crs.is_geographic else Transformer.from_crs(crs, 4326, always_xy=True)

    feats = []
    for level in levels:
        for line in measure.find_contours(smooth, level, mask=valid):
            rows, cols = line[:, 0] + 0.5, line[:, 1] + 0.5
            xs = tf_s.a * cols + tf_s.b * rows + tf_s.c
            ys = tf_s.d * cols + tf_s.e * rows + tf_s.f
            if to_wgs is not None:
                xs, ys = to_wgs.transform(xs, ys)
            if len(xs) < 3:
                continue
            geom = LineString(np.column_stack([xs, ys])).simplify(simplify_deg)
            if geom.length < min_len_deg:
                continue
            coords = [[round(x, 4), round(y, 4)] for x, y in geom.coords]
            feats.append({
                "type": "Feature",
                "properties": {"mm": level, "major": level in MAJOR_LEVELS,
                               "label": f"{level:,} mm"},
                "geometry": {"type": "LineString", "coordinates": coords},
            })
    log.info("Isohyets: %d lines across %d levels", len(feats), len(levels))
    return {"type": "FeatureCollection", "features": feats}


# --------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--src", type=Path, required=True, help="PRISM annual precip raster (mm)")
    ap.add_argument("--out", type=Path, default=Path("rain_relief_out"))
    ap.add_argument("--zmin", type=int, default=3)
    ap.add_argument("--zmax", type=int, default=8)
    ap.add_argument("--shade-ve", type=float, default=6.0, help="baked hillshade vertical exaggeration")
    ap.add_argument("--levels", type=int, nargs="+", default=DEFAULT_LEVELS, help="isohyet levels, mm")
    ap.add_argument("--contour-decimate", type=int, default=3)
    ap.add_argument("--skip-tiles", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    data, tf, crs = load_precip(args.src)
    mm_max = float(np.nanmax(data))
    args.out.mkdir(parents=True, exist_ok=True)

    bounds = tuple(transform_bounds(crs, CRS.from_epsg(4326),
                                    *array_bounds(*data.shape, tf)))
    if not args.skip_tiles:
        bounds = build_tiles(data, tf, crs, args.out, args.zmin, args.zmax, mm_max, args.shade_ve)

    iso = build_isohyets(data, tf, crs, sorted(args.levels), decimate=args.contour_decimate)
    (args.out / "isohyets.geojson").write_text(json.dumps(iso, separators=(",", ":")))

    meta = {"mm_max": mm_max, "bounds": list(bounds), "zmin": args.zmin, "zmax": args.zmax,
            "ramp": RAMP, "levels": sorted(args.levels)}
    (args.out / "meta.json").write_text(json.dumps(meta))
    log.info("Done -> %s  (serve the folder containing index.html and this output)", args.out)


if __name__ == "__main__":
    main()
