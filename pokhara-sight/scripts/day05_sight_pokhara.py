#!/usr/bin/env python3
"""30 Day Map Challenge 2026 - Day 5: Sight.

How many Himalayan giants can you see from Pokhara?

Method (terrain-profile line of sight)
--------------------------------------
For every map cell (and every viewpoint) and every target summit, sample the 30 m DSM
along the straight path between them and test whether the sight line clears the terrain,
with a curvature + refraction drop of CURV_COEFF * d * (D - d) / (2R). The observer is
2 m above the ground cell, the target is the summit cell. Summing the booleans over the
nine summits gives "number of giants in line of sight per cell" (see `sees_summit`).

Why not `gdal_viewshed` from the summits? GDAL's result is not reciprocal for grazing
lines (summit -> ground and ground -> summit disagreed on the Sarangkot-Machhapuchhre
line, and the whole Pokhara window came out empty), so the test is done explicitly.

Requirements: Python with GDAL bindings (only to download/warp the DEM), rasterio, numpy,
scipy, pyproj, matplotlib. conda-forge is the easy route on Windows:
    conda install -c conda-forge gdal rasterio scipy pyproj matplotlib numpy
Outputs go to ./day05_sight/. The companion script day05_sight_pokhara_anim.py makes the
animated sweeps and needs Pillow and imageio-ffmpeg as well.

Key assumptions (also printed on the map)
-----------------------------------------
* DEM: Copernicus GLO-30 DSM (30 m, ~EGM2008 heights, includes canopy and
  buildings), streamed from the public AWS bucket, reprojected to EPSG:32644
  (UTM 44N) with bilinear resampling. Units: metres. The same DEM file is used by
  the animation script so the table, map and animation agree.
* Curvature + refraction: coefficient 0.85714 (standard atmospheric refraction).
  No haze, cloud or atmospheric extinction -> this is geometric line-of-sight only,
  not "visible on a typical day".
* Summit coordinates below are approximate. Each is snapped to the DEM maximum
  within SNAP_RADIUS_M and the snapped elevation is checked against the known
  elevation; peaks that fail the check are skipped with a warning. Viewpoints get the
  same check (own snap radius and tolerance).
* Some lines of sight graze a ridge (Annapurna II from the Pokhara viewpoints). Sub-metre
  DEM differences can flip them, so treat those counts as +/- 1.
"""
from __future__ import annotations

import csv
import logging
import textwrap
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from matplotlib.colors import BoundaryNorm, LightSource, LinearSegmentedColormap, Normalize
from osgeo import gdal
from scipy.ndimage import map_coordinates
from pyproj import Transformer
from rasterio.transform import rowcol, xy
from rasterio.warp import transform_bounds
from rasterio.windows import bounds as win_bounds
from rasterio.windows import from_bounds

log = logging.getLogger("day05")

# ----------------------------------------------------------------- config ---
WORK = Path("day05_sight")
CRS = "EPSG:32644"  # UTM 44N (Pokhara ~83.98 E)
RES_M = 30.0
DEM_BBOX_LL = (83.10, 27.45, 84.80, 28.95)  # lon/lat window for the DEM (covers a 75 km radius round Pokhara)
MAP_BBOX_LL = (83.88, 28.10, 84.12, 28.34)  # lon/lat window for the map
TILES = ["N27_00_E083_00", "N27_00_E084_00", "N28_00_E083_00", "N28_00_E084_00"]
TILE_URL = (
    "/vsicurl/https://copernicus-dem-30m.s3.amazonaws.com/"
    "Copernicus_DSM_COG_10_{t}_DEM/Copernicus_DSM_COG_10_{t}_DEM.tif"
)
TARGET_H_M = 2.0  # eye height of the person on the ground
OBSERVER_H_M = 0.0  # height above the summit DSM cell
CURV_COEFF = 0.85714
MAX_DIST_M = 120_000
SNAP_RADIUS_M = 1500.0
PANO_MAX_DIST_M = 150_000  # skyline range for the horizon panoramas
STRIDE = 2 # evaluate every n-th DEM cell inside the map window (2 -> 60 m)
ELEV_TOL_M = 150.0


@dataclass(frozen=True)
class Peak:
    name: str
    lon: float
    lat: float
    elev_m: float  # published elevation, used only as a sanity check


# Approximate coordinates - verify against OSM natural=peak / Wikidata.
PEAKS = [
    Peak("Dhaulagiri I", 83.4933, 28.6975, 8167),
    Peak("Annapurna I", 83.8203, 28.5961, 8091),
    Peak("Annapurna South", 83.8056, 28.5189, 7219),
    Peak("Machhapuchhre", 83.9489, 28.4947, 6993),
    Peak("Annapurna III", 84.0000, 28.5853, 7555),
    Peak("Annapurna II", 84.1219, 28.5342, 7937),
    Peak("Annapurna IV", 84.0875, 28.5350, 7525),
    Peak("Gangapurna", 83.9633, 28.6039, 7455),
    Peak("Manaslu", 84.5597, 28.5497, 8163),
]

# Established viewpoints: name -> (lon, lat, published elevation m, snap radius m).
# Coordinates from Wikipedia / tourism listings (approximate). Each is snapped to the
# highest DSM cell within its radius and checked against the published elevation
# (VP_ELEV_TOL_M); viewpoints that fail are skipped with a warning. Lakeside is a
# low reference point on the shore (no snapping).
VIEWPOINTS = {
    "Sarangkot": (83.9452, 28.2435, 1592, 300),
    "World Peace Pagoda": (83.9449, 28.2012, 1100, 200),
    "Kahun Danda": (84.0050, 28.2350, 1430, 1500),
    "Pumdikot": (83.9298, 28.1999, 1350, 60),  # Google Maps pin "Pumdikot Shiva statue"; DSM ~1350 m
    "Kaskikot": (83.9014, 28.2719, 1750, 1000),
    "Naudanda": (83.8684, 28.2814, 1500, 60),  # Google Maps pin "Naudanda View Tower"; DSM ~1480-1500 m
    "Lakeside (Phewa)": (83.9568, 28.2086, 820, 0),
}
VP_ELEV_TOL_M = 150.0


# ---------------------------------------------------------------- helpers ---
def build_dem(path: Path) -> None:
    """Mosaic GLO-30 tiles and warp to CRS at RES_M (bilinear). Cached."""
    if path.exists():
        return
    gdal.UseExceptions()
    gdal.SetConfigOption("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
    gdal.SetConfigOption("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif")

    vrt_path = WORK / "glo30.vrt"
    vrt = gdal.BuildVRT(str(vrt_path), [TILE_URL.format(t=t) for t in TILES])
    if vrt is None:
        raise RuntimeError("Could not open Copernicus tiles (network/allowlist?)")
    vrt = None  # flush to disk

    l, b, r, t = transform_bounds("EPSG:4326", CRS, *DEM_BBOX_LL, densify_pts=21)
    bounds = (
        np.floor(l / RES_M) * RES_M,
        np.floor(b / RES_M) * RES_M,
        np.ceil(r / RES_M) * RES_M,
        np.ceil(t / RES_M) * RES_M,
    )
    log.info("Warping DEM to %s ...", CRS)
    gdal.Warp(
        str(path),
        str(vrt_path),
        options=gdal.WarpOptions(
            dstSRS=CRS,
            outputBounds=bounds,
            xRes=RES_M,
            yRes=RES_M,
            resampleAlg="bilinear",
            dstNodata=-9999,
            outputType=gdal.GDT_Float32,
            creationOptions=["COMPRESS=DEFLATE", "TILED=YES"],
            multithread=True,
        ),
    )


def snap_to_summit(
    dem: np.ndarray, transform: rasterio.Affine, x: float, y: float, nodata: float,
    radius_m: float = SNAP_RADIUS_M,
) -> tuple[float, float, float]:
    """Return (x, y, z) of the DEM maximum within SNAP_RADIUS_M of (x, y)."""
    r = int(round(radius_m / RES_M))
    row, col = rowcol(transform, x, y)
    r0, r1 = max(row - r, 0), min(row + r + 1, dem.shape[0])
    c0, c1 = max(col - r, 0), min(col + r + 1, dem.shape[1])
    if r0 >= r1 or c0 >= c1:
        raise ValueError("Peak lies outside the DEM window")
    win = np.where(dem[r0:r1, c0:c1] == nodata, -np.inf, dem[r0:r1, c0:c1])
    i, j = np.unravel_index(np.argmax(win), win.shape)
    sx, sy = xy(transform, r0 + i, c0 + j)
    return float(sx), float(sy), float(win[i, j])


def sees_summit(
    dem: np.ndarray, transform: rasterio.Affine, summit: tuple[float, float, float],
    tx: np.ndarray, ty: np.ndarray, chunk: int = 500,
) -> np.ndarray:
    """Boolean per target point (UTM x, y): does an observer standing there
    (ground + TARGET_H_M) have line of sight to the summit (+OBSERVER_H_M)?

    Own symmetric test, used instead of gdal_viewshed because GDAL's result is
    NOT reciprocal for grazing lines (summit->ground and ground->summit
    disagreed on the Sarangkot-Machhapuchhre line). The terrain is sampled
    (bilinear, every ~RES_M) along the straight path and compared with the
    sight line; earth curvature + refraction drop = CURV_COEFF * d*(D-d)/(2R),
    which is symmetric in the two end points.
    """
    sx, sy, sz = summit
    R = 6_371_000.0
    dist = np.hypot(tx - sx, ty - sy)
    order = np.argsort(dist)
    vis = np.zeros(tx.shape, dtype=bool)
    for i in range(0, len(order), chunk):
        idx = order[i:i + chunk]
        D = dist[idx][:, None]
        n = max(int(np.ceil(D.max() / RES_M)) + 1, 6)
        f = np.linspace(0.0, 1.0, n)[None, :]  # 0 = observer cell, 1 = summit
        xs = tx[idx][:, None] + (sx - tx[idx][:, None]) * f
        ys = ty[idx][:, None] + (sy - ty[idx][:, None]) * f
        z = map_coordinates(
            dem, [(transform.f - ys) / RES_M - 0.5, (xs - transform.c) / RES_M - 0.5],
            order=1, mode="nearest")
        z0 = z[:, :1] + TARGET_H_M
        z1 = sz + OBSERVER_H_M
        line = z0 + (z1 - z0) * f
        d = f * D
        drop = CURV_COEFF * d * (D - d) / (2 * R)
        vis[idx] = (line - (z + drop))[:, 1:-1].min(axis=1) > 0
    return vis


def horizon_profile(
    dem: np.ndarray, transform: rasterio.Affine, ox: float, oy: float, oz: float,
    az_deg: np.ndarray, max_dist: float = PANO_MAX_DIST_M, step: float = 60.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Skyline seen from (ox, oy, oz): per azimuth, the max elevation angle (deg)
    of the terrain, and the distance (m) at which it occurs. Same curvature +
    refraction model as sees_summit(). Samples outside the DEM are ignored."""
    R = 6_371_000.0
    d = np.arange(step, max_dist + step, step)[None, :]
    a = np.radians(az_deg)[:, None]
    xs, ys = ox + d * np.sin(a), oy + d * np.cos(a)
    cols, rows = (xs - transform.c) / RES_M - 0.5, (transform.f - ys) / RES_M - 0.5
    inside = (rows >= 0) & (rows <= dem.shape[0] - 1) & (cols >= 0) & (cols <= dem.shape[1] - 1)
    z = map_coordinates(dem, [rows, cols], order=1, mode="nearest")
    ang = np.degrees(np.arctan2(z - oz - CURV_COEFF * d**2 / (2 * R), d))
    ang = np.where(inside, ang, -90.0)
    k = ang.argmax(axis=1)
    return ang[np.arange(len(k)), k], d[0, k]


def make_panoramas(dem, transform, valid, vp_xy, rows) -> None:
    """One 360-degree skyline panorama per viewpoint (peaks marked), plus a stacked sheet."""
    az = np.arange(0.0, 360.0, 0.25)
    seen_by_vp = {r[0]: set(r[2].split("; ")) for r in rows}
    cmap = plt.get_cmap("viridis_r")
    fig_all, axes_all = plt.subplots(len(vp_xy), 1, figsize=(14, 3.6 * len(vp_xy)), dpi=150)
    for ax_all, (vp, (vx, vy)) in zip(np.atleast_1d(axes_all), vp_xy.items()):
        r, c = rowcol(transform, vx, vy)
        oz = float(dem[r, c]) + TARGET_H_M
        sky, dist = horizon_profile(dem, transform, vx, vy, oz, az)
        info = []
        for p, (sx, sy, sz) in valid:
            D = float(np.hypot(sx - vx, sy - vy))
            bearing = float(np.degrees(np.arctan2(sx - vx, sy - vy)) % 360)
            elev = float(np.degrees(np.arctan2(sz - oz - CURV_COEFF * D**2 / (2 * 6_371_000.0), D)))
            info.append((p.name, bearing, elev, D / 1000, p.name in seen_by_vp[vp]))
        ymax = max(i[2] for i in info) + 9  # sized to the peaks; near hills may clip off the top
        for ax in (ax_all, None):
            fig = None
            if ax is None:
                fig, ax = plt.subplots(figsize=(14, 4), dpi=200)
            ax.vlines(az, -3, sky, colors=cmap(np.clip(dist / PANO_MAX_DIST_M, 0, 1)), lw=1.3)
            ax.plot(az, sky, color="black", lw=0.6)
            for j, (name, b, e, dkm, ok) in enumerate(sorted(info, key=lambda i: i[1])):
                ax.scatter(b, e, s=55 if ok else 30, marker="^", zorder=5,
                           c="crimson" if ok else "white", ec="black", lw=0.8)
                ax.annotate(f"{name} {dkm:.0f} km" + ("" if ok else " (hidden)"), (b, e),
                            xytext=(0, 7 + 16 * (j % 2)), textcoords="offset points", rotation=60, ha="left",
                            va="bottom", fontsize=7, zorder=6, annotation_clip=False)
            ax.set_xlim(-8, 368)
            ax.set_ylim(-3, ymax)
            ax.set_xticks([0, 45, 90, 135, 180, 225, 270, 315, 360])
            ax.set_xticklabels(["N", "NE", "E", "SE", "S", "SW", "W", "NW", "N"], fontsize=8)
            ax.set_ylabel("Elevation angle (deg)", fontsize=8)
            ax.set_title(f"{vp}: horizon panorama, {sum(i[4] for i in info)} of {len(info)} peaks in line of sight",
                         loc="left", fontsize=10, weight="bold", pad=8)
            ax.grid(alpha=0.25, lw=0.4)
            if fig is not None:
                fig.text(0.01, 0.01, f"Observer {oz:.0f} m (DSM + {TARGET_H_M:g} m); skyline to {PANO_MAX_DIST_M/1000:.0f} km, "
                         "coloured by distance to the skyline (dark = far). Red = in line of sight, white = hidden. "
                         "Copernicus GLO-30.", fontsize=6.5)
                fig.tight_layout(rect=(0, 0.03, 1, 1))
                fig.savefig(WORK / f"day05_panorama_{vp.lower().replace(' ', '_').replace('(', '').replace(')', '')}.png")
                plt.close(fig)
    fig_all.tight_layout()
    fig_all.savefig(WORK / "day05_panoramas_all.png")
    plt.close(fig_all)


def draw_graticule(ax, extent: tuple[float, float, float, float], step: float = 0.05):
    """Lon/lat graticule drawn on a UTM axes, with edge labels."""
    to_utm = Transformer.from_crs("EPSG:4326", CRS, always_xy=True)
    to_ll = Transformer.from_crs(CRS, "EPSG:4326", always_xy=True)
    xmin, xmax, ymin, ymax = extent
    lon_min, lat_min = to_ll.transform(xmin, ymin)
    lon_max, lat_max = to_ll.transform(xmax, ymax)
    lons = np.arange(np.ceil(lon_min / step) * step, lon_max, step)
    lats = np.arange(np.ceil(lat_min / step) * step, lat_max, step)
    for lon in lons:
        xs, ys = to_utm.transform(np.full(50, lon), np.linspace(lat_min - 0.05, lat_max + 0.05, 50))
        ax.plot(xs, ys, color="white", lw=0.5, ls=(0, (3, 3)), alpha=0.7)
    for lat in lats:
        xs, ys = to_utm.transform(np.linspace(lon_min - 0.05, lon_max + 0.05, 50), np.full(50, lat))
        ax.plot(xs, ys, color="white", lw=0.5, ls=(0, (3, 3)), alpha=0.7)
    ax.set_xticks([to_utm.transform(lon, lat_min)[0] for lon in lons])
    ax.set_xticklabels([f"{lon:.2f}°E" for lon in lons], fontsize=8)
    ax.set_yticks([to_utm.transform(lon_min, lat)[1] for lat in lats])
    ax.set_yticklabels([f"{lat:.2f}°N" for lat in lats], fontsize=8)
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)


def draw_scale_bar(ax, extent, length_m: float = 5000.0) -> None:
    xmin, xmax, ymin, ymax = extent
    x0 = xmin + 0.04 * (xmax - xmin)
    y0 = ymin + 0.04 * (ymax - ymin)
    ax.plot([x0, x0 + length_m], [y0, y0], color="black", lw=4, solid_capstyle="butt",
            path_effects=None, zorder=10)
    ax.plot([x0, x0 + length_m / 2], [y0, y0], color="white", lw=2, solid_capstyle="butt", zorder=11)
    ax.text(x0 + length_m / 2, y0 + 0.012 * (ymax - ymin), f"{length_m / 1000:.0f} km",
            ha="center", fontsize=8, zorder=12,
            bbox=dict(fc="white", ec="none", alpha=0.7, pad=1))


# ------------------------------------------------------------------- main ---
def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    WORK.mkdir(exist_ok=True)

    dem_path = WORK / "dem_utm44n_30m.tif"
    build_dem(dem_path)

    with rasterio.open(dem_path) as src:
        if src.crs is None or src.crs.to_string() != CRS:
            raise ValueError(f"DEM CRS {src.crs} != {CRS}")
        dem = src.read(1)
        transform, nodata, profile = src.transform, src.nodata, src.profile
    if nodata is None:
        raise ValueError("DEM has no nodata value set")

    to_utm = Transformer.from_crs("EPSG:4326", CRS, always_xy=True)

    # 1) snap + verify summits, 2) viewshed per summit
    valid: list[tuple[Peak, tuple[float, float, float]]] = []
    for p in PEAKS:
        x, y = to_utm.transform(p.lon, p.lat)
        try:
            sx, sy, sz = snap_to_summit(dem, transform, x, y, nodata)
        except ValueError as e:
            log.warning("SKIP %s: %s", p.name, e)
            continue
        if abs(sz - p.elev_m) > ELEV_TOL_M:
            log.warning("SKIP %s: DEM max %.0f m vs published %.0f m (fix coords)",
                        p.name, sz, p.elev_m)
            continue
        log.info("%s: snapped, DEM %.0f m (published %.0f m)", p.name, sz, p.elev_m)
        valid.append((p, (sx, sy, sz)))
    if not valid:
        raise SystemExit("No peaks passed the elevation check.")

    dem_calc = np.where(dem == nodata, 0.0, dem).astype(np.float32)

    # 3) count raster over the map window only (every STRIDE-th DEM cell)
    n = len(valid)
    mb = transform_bounds("EPSG:4326", CRS, *MAP_BBOX_LL, densify_pts=21)
    win = from_bounds(*mb, transform=transform).round_offsets().round_lengths()
    r0, c0 = int(win.row_off), int(win.col_off)
    rr = np.arange(r0, r0 + int(win.height), STRIDE)
    cc = np.arange(c0, c0 + int(win.width), STRIDE)
    gr, gc = np.meshgrid(rr, cc, indexing="ij")
    tx, ty = xy(transform, gr.ravel(), gc.ravel())
    tx, ty = np.asarray(tx), np.asarray(ty)
    count = np.zeros(tx.shape, dtype=np.uint8)
    for p, summit in valid:
        v = sees_summit(dem_calc, transform, summit, tx, ty)
        log.info("%-16s visible from %.1f%% of map cells", p.name, 100 * v.mean())
        count += v
    count = count.reshape(gr.shape)
    count_path = WORK / "peaks_visible_count.tif"
    cprof = profile.copy()
    cprof.update(dtype="uint8", count=1, nodata=None, compress="deflate",
                 height=count.shape[0], width=count.shape[1],
                 transform=transform * rasterio.Affine.translation(c0, r0) * rasterio.Affine.scale(STRIDE))
    with rasterio.open(count_path, "w", **cprof) as dst:
        dst.write(count, 1)

    # 4) per-viewpoint table (viewpoint snapped to the local DSM maximum)
    rows = []
    vp_xy = {}
    for vp, (lon, lat, vp_elev, snap_m) in VIEWPOINTS.items():
        x, y = to_utm.transform(lon, lat)
        try:
            vx, vy, vz = snap_to_summit(dem, transform, x, y, nodata, radius_m=snap_m)
        except ValueError as e:
            log.warning("SKIP viewpoint %s: %s", vp, e)
            continue
        if abs(vz - vp_elev) > VP_ELEV_TOL_M:
            log.warning("SKIP viewpoint %s: DEM %.0f m vs published %.0f m (fix coords)", vp, vz, vp_elev)
            continue
        log.info("viewpoint %s: DEM %.0f m (published %d m)", vp, vz, vp_elev)
        vp_xy[vp] = (vx, vy)
        seen = [p.name for p, summit in valid
                if sees_summit(dem_calc, transform, summit, np.array([vx]), np.array([vy]))[0]]
        rows.append((vp, len(seen), "; ".join(seen)))
        log.info("%-20s %d  %s", vp, len(seen), "; ".join(seen))
    with open(WORK / "viewpoints.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["viewpoint", "n_visible", "peaks"])
        w.writerows(rows)
    make_panoramas(dem_calc, transform, valid, vp_xy, rows)

    # 5) map
    with rasterio.open(dem_path) as sd:
        dem_w = sd.read(1, window=win)
        l, b, r_, t = win_bounds(win, sd.transform)
    cnt_w = count
    extent = (l, r_, b, t)

    valid_px = dem_w != nodata
    if not valid_px.any():
        raise ValueError("Map window contains only nodata")
    dem_f = np.where(valid_px, dem_w, np.nan)
    hill = LightSource(azdeg=315, altdeg=40).hillshade(
        np.nan_to_num(dem_f, nan=float(np.nanmin(dem_f))), vert_exag=2.0, dx=RES_M, dy=RES_M)

    # Elevation base: black (low) -> gray -> white (high), 2-98th pct stretch (metres)
    lo, hi = np.nanpercentile(dem_f, [2, 98])
    elev_norm = Normalize(vmin=lo, vmax=hi, clip=True)
    elev_cmap = LinearSegmentedColormap.from_list(
        "elev_bw", ["#000000", "#4d4d4d", "#9a9a9a", "#ffffff"])
    rgb = elev_cmap(elev_norm(np.where(valid_px, dem_w, lo)))[..., :3]
    rgb = rgb * (0.6 + 0.4 * hill)[..., None]  # hillshade modulates, keeps white->black ramp readable
    rgba = np.dstack([np.clip(rgb, 0, 1), valid_px.astype(float)])

    cmap = plt.get_cmap("plasma", n)
    norm = BoundaryNorm(np.arange(0.5, n + 1.5), n)

    fig, ax = plt.subplots(figsize=(9, 10.5), dpi=200)
    ax.imshow(rgba, extent=extent, origin="upper")
    im = ax.imshow(np.ma.masked_equal(cnt_w, 0), cmap=cmap, norm=norm,
                   extent=extent, origin="upper", alpha=0.55, interpolation="nearest")
    draw_graticule(ax, extent)
    draw_scale_bar(ax, extent)
    for vp, (x, y) in vp_xy.items():
        if not (extent[0] <= x <= extent[1] and extent[2] <= y <= extent[3]):
            continue  # viewpoint lies outside the map window (still in the panoramas)
        k = next(nv for name, nv, _ in rows if name == vp)
        ax.scatter(x, y, s=55, c="white", ec="black", zorder=20)
        ax.annotate(f"{vp} ({k})", (x, y), xytext=(6, 6), textcoords="offset points",
                    fontsize=8, zorder=21, bbox=dict(fc="white", ec="none", alpha=0.75, pad=1))
    ax.annotate("N", xy=(0.95, 0.95), xytext=(0.95, 0.89), xycoords="axes fraction",
                ha="center", fontsize=12, arrowprops=dict(arrowstyle="-|>", color="black"))
    cb = fig.colorbar(im, ax=ax, ticks=range(1, n + 1), shrink=0.6, pad=0.02)
    cb.set_label("Number of giants in line of sight (colour overlay)", fontsize=9)
    eb = fig.colorbar(plt.cm.ScalarMappable(norm=Normalize(lo, hi), cmap=elev_cmap),
                      ax=ax, orientation="horizontal", shrink=0.5, pad=0.05, aspect=30)
    eb.set_label("Ground elevation, m (black = low, white = high)", fontsize=9)
    ax.set_title("Sight: how many Himalayan giants can you see from Pokhara?",
                 fontsize=13, weight="bold", loc="left")
    note = (
        f"Peaks tested ({n}): " + ", ".join(p.name for p, _ in valid) + ". "
        "Data: Copernicus GLO-30 DSM (30 m; includes canopy and buildings), UTM 44N, bilinear; "
        "base = elevation grayscale (2-98th pct stretch) with hillshade. "
        f"Terrain-profile line of sight from each cell to each summit (snapped to DEM max, elevation-checked); "
        f"observer height {TARGET_H_M:g} m; curvature+refraction coeff {CURV_COEFF}; viewpoints snapped to the local DSM max "
        f"and elevation-checked. Geometric line of sight only: "
        "no haze, cloud or atmospheric extinction. Uncoloured = none of these peaks visible."
    )
    fig.text(0.06, 0.02, textwrap.fill(note, 120), fontsize=7, va="bottom")
    fig.subplots_adjust(bottom=0.12)
    fig.savefig(WORK / "day05_sight.png")
    log.info("Done -> %s", WORK / "day05_sight.png")


if __name__ == "__main__":
    main()
