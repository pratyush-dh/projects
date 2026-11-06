#!/usr/bin/env python3
"""30 Day Map Challenge 2026 - Day 5: Sight. Animated 360-degree sweeps.

Top of each panel: circular map centred on the viewpoint. A sweep line rotates clockwise
from N and reveals the terrain in line of sight, coloured by distance (cool = near,
warm = far). Below it: the panorama in the current heading (terrain layers coloured by
distance), a heading read-out and running totals.

Method: radial sweep (horizon method). For each azimuth the terrain is sampled every
STEP m out to R_MAX with the same curvature + refraction model as day05_sight_pokhara.py.
A ground cell is visible if its elevation angle is >= the running maximum angle of
everything nearer along that ray. The panorama is the same data: for each azimuth, each
elevation angle shows the nearest surface that reaches it.

Usage:
    python day05_sight_pokhara_anim.py grid          # all viewpoints on one page (MP4 + GIF)
    python day05_sight_pokhara_anim.py single [name] # one animation per viewpoint
Needs the same environment as day05_sight_pokhara.py plus Pillow and imageio-ffmpeg.
"""
from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import imageio_ffmpeg
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from matplotlib.colors import LightSource, LinearSegmentedColormap
from matplotlib.patches import Circle
from PIL import Image
from pyproj import Transformer
from scipy.ndimage import binary_dilation, map_coordinates

import day05_sight_pokhara as m

log = logging.getLogger("day05anim")

# ----------------------------------------------------------------- config ---
R_MAX = 75_000.0  # radius of the sweep (m)
STEP = 40.0  # sample spacing along each ray (m)
AZ_DEG = 0.075  # azimuth resolution (deg)
FOV = 100.0  # width of the panorama window (deg)
ANG_MIN, ANG_MAX = -18.0, 20.0  # panorama vertical range (deg, exaggerated)
PANO_H = 360
SWEEP_STEP_DEG = 2.0
HOLD_FRAMES = 12
FRAME_MS = 67  # 15 fps
GIF_W = 800  # width of the GIF (the MP4 is full size)

BG = "#050b14"
CMAP = LinearSegmentedColormap.from_list(
    "dist", ["#00c8ff", "#2f7bff", "#7a5cff", "#d24fd8", "#ff4d8d", "#ffa040"])
WINDS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
         "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
SHORT = {"Dhaulagiri I": "Dhaul. I", "Annapurna I": "Ann. I", "Annapurna II": "Ann. II",
         "Annapurna III": "Ann. III", "Annapurna IV": "Ann. IV", "Annapurna South": "Ann. S",
         "Machhapuchhre": "Machh.", "Gangapurna": "Gang.", "Manaslu": "Manaslu"}


def compass(az: float) -> str:
    return WINDS[int((az % 360) / 22.5 + 0.5) % 16]


# ------------------------------------------------------------------- data ---
def radial_sweep(dem, tr, vx, vy, oz):
    """Running-max angle M [A, D], visible [A, D], inside-DEM [A, D], distances d [D]."""
    R = 6_371_000.0
    az = np.radians(np.arange(0.0, 360.0, AZ_DEG))
    d = np.arange(STEP, R_MAX + STEP / 2, STEP)
    xs = vx + np.outer(np.sin(az), d)
    ys = vy + np.outer(np.cos(az), d)
    rows = (tr.f - ys) / m.RES_M - 0.5
    cols = (xs - tr.c) / m.RES_M - 0.5
    inside = (rows >= 0) & (rows <= dem.shape[0] - 1) & (cols >= 0) & (cols <= dem.shape[1] - 1)
    z = map_coordinates(dem, [rows, cols], order=1, mode="nearest")
    ang = np.degrees(np.arctan2(z - oz - m.CURV_COEFF * d[None, :] ** 2 / (2 * R), d[None, :]))
    ang = np.where(inside, ang, -90.0)
    M = np.maximum.accumulate(ang, axis=1)
    prev = np.concatenate([np.full((M.shape[0], 1), -np.inf), M[:, :-1]], axis=1)
    vis = (ang >= prev) & inside
    return M, vis, inside, d


def panorama_distance(M, d):
    """[A, H] distance (m) of the nearest surface reaching each elevation-angle bin; NaN = sky."""
    theta = np.linspace(ANG_MAX, ANG_MIN, PANO_H)
    out = np.full((M.shape[0], PANO_H), np.nan, dtype=np.float32)
    for a in range(M.shape[0]):
        k = np.searchsorted(M[a], theta, side="left")
        ok = k < M.shape[1]
        out[a, ok] = d[k[ok]]
    return out


def prepare(vp, vx, vy, vz, dem, tr, hs_small, peaks, npix):
    """Everything an animation panel needs for one viewpoint."""
    oz = vz + m.TARGET_H_M
    log.info("%s: radial sweep ...", vp)
    M, vis, inside, d = radial_sweep(dem, tr, vx, vy, oz)
    A, D = M.shape
    pano_d = panorama_distance(M, d)
    sky = np.array([0.04, 0.07, 0.13])
    pano_rgb = np.where(np.isnan(pano_d)[..., None], sky, CMAP(np.nan_to_num(pano_d) / R_MAX)[..., :3])
    shade = np.linspace(1.0, 0.72, PANO_H)[None, :, None]
    pano_rgb = np.where(np.isnan(pano_d)[..., None], pano_rgb, pano_rgb * shade).astype(np.float32)

    pk = []
    for p, (sx, sy, sz) in peaks:
        dist = float(np.hypot(sx - vx, sy - vy))
        if dist > R_MAX * 1.02:
            continue
        b = float(np.degrees(np.arctan2(sx - vx, sy - vy)) % 360)
        e = float(np.degrees(np.arctan2(sz - oz - m.CURV_COEFF * dist**2 / (2 * 6_371_000.0), dist)))
        ok = bool(m.sees_summit(dem, tr, (sx, sy, sz), np.array([vx]), np.array([vy]))[0])
        pk.append((p.name, b, e, dist, ok, sx - vx, sy - vy))
    pk.sort(key=lambda t: t[1])

    lin = np.linspace(-R_MAX, R_MAX, npix)
    X, Y = np.meshgrid(lin, lin[::-1])
    r = np.hypot(X, Y)
    in_c = r <= R_MAX
    az_px = np.degrees(np.arctan2(X, Y)) % 360
    ai = (az_px / AZ_DEG).astype(int) % A
    di = np.clip((r / STEP).astype(int) - 1, 0, D - 1)
    vis_px = binary_dilation(vis[ai, di] & in_c, iterations=1) & in_c
    valid_px = inside[ai, di] & in_c
    rows = (tr.f - (vy + Y)) / (m.RES_M * 4) - 0.5
    cols = (vx + X - tr.c) / (m.RES_M * 4) - 0.5
    hs = np.clip(map_coordinates(hs_small, [rows, cols], order=1, mode="nearest"), 0, 1)
    dist_rgb = CMAP(r / R_MAX)[..., :3]
    bgc = np.array([0.02, 0.043, 0.078])
    L_unswept = np.clip(np.array([0.13, 0.16, 0.24]) * 0.8 + hs[..., None] * 0.30, 0, 1)
    L_hidden = np.clip(0.035 + hs[..., None] * 0.10, 0, 1) * np.array([1.0, 1.0, 1.3])
    L_vis = np.clip(dist_rgb * (0.50 + 0.50 * hs[..., None]), 0, 1)
    for L in (L_unswept, L_hidden, L_vis):
        L[~valid_px] = 0.0
        L[~in_c] = bgc

    w = d[None, :] * inside
    cum = np.cumsum((vis * w).sum(axis=1)) / w.sum() * 100.0
    return dict(vp=vp, vz=vz, A=A, pk=pk, cum=cum, vis_px=vis_px, az_px=az_px, L_unswept=L_unswept,
                L_hidden=L_hidden, L_vis=L_vis, pano_rgb=pano_rgb, skyline=M[:, -1], npix=npix)


# ----------------------------------------------------------------- panels ---
class Panel:
    """One viewpoint: circular sweep map + panorama + read-outs, drawn in given figure rects.

    rect_* are (left, bottom, width, height) in figure fractions; fs scales every font."""

    def __init__(self, fig, st, rect_map, rect_pano, xy_head, xy_pct, xy_cnt, fs=1.0,
                 center_label=True, short_names=False, pano_w=700):
        self.st, self.fs, self.short, self.pano_w = st, fs, short_names, pano_w
        self.dyn = []
        self.xs_pano = np.linspace(-FOV / 2, FOV / 2, pano_w)
        ax = fig.add_axes(rect_map, facecolor=BG)
        ax.set_xlim(-R_MAX, R_MAX)
        ax.set_ylim(-R_MAX, R_MAX)
        ax.axis("off")
        self.im = ax.imshow(st["L_unswept"], extent=(-R_MAX, R_MAX, -R_MAX, R_MAX), origin="upper",
                            interpolation="nearest")
        for km in (25, 50, 75):
            ax.add_patch(Circle((0, 0), km * 1000, fill=False, ec="white", lw=0.4, alpha=0.35, ls=(0, (3, 4))))
            ax.text(km * 1000 * 0.707, -km * 1000 * 0.707, f"{km} km", color="white", fontsize=5.5 * fs,
                    alpha=0.7, ha="left", va="top")
        for lab, a in (("N", 0), ("E", 90), ("S", 180), ("W", 270)):
            ax.text(1.06 * R_MAX * np.sin(np.radians(a)), 1.06 * R_MAX * np.cos(np.radians(a)), lab,
                    color="white", fontsize=7.5 * fs, ha="center", va="center")
        for j, (name, b, e, dist, ok, px, py) in enumerate(st["pk"]):
            ax.scatter(px, py, marker="^", s=26 * fs * fs, c="white" if ok else "none", ec="white", lw=0.8, zorder=5)
            label = SHORT.get(name, name) if short_names else name.replace("Annapurna", "Ann.")
            ax.text(px, py + (3000 if j % 2 == 0 else -5600), label, color="white", fontsize=5.5 * fs,
                    ha="center", zorder=6, alpha=0.95)
        ax.scatter(0, 0, s=18 * fs * fs, c="white", ec="#25c7ff", zorder=7)
        if center_label:
            ax.text(-2500, 1500, f"{st['vp']}  {st['vz']:,.0f} m", color="white", fontsize=7 * fs,
                    weight="bold", ha="right")
        (self.sweep,) = ax.plot([0, 0], [0, R_MAX], color="white", lw=1.6 * max(fs, 0.8), zorder=8)

        axp = fig.add_axes(rect_pano, facecolor=BG)
        self.axp = axp
        self.pim = axp.imshow(np.zeros((PANO_H, pano_w, 3)), extent=(-FOV / 2, FOV / 2, ANG_MIN, ANG_MAX),
                              aspect="auto", origin="upper", interpolation="bilinear")
        axp.axhline(0, color="white", lw=0.5, ls=(0, (4, 3)), alpha=0.7)
        axp.text(-FOV / 2 + 0.8, 0.6, "eye level", color="white", fontsize=5.0 * fs, alpha=0.8)
        (self.sky_line,) = axp.plot([], [], color="white", lw=0.9, alpha=0.95)
        axp.set_xlim(-FOV / 2, FOV / 2)
        axp.set_ylim(ANG_MIN, ANG_MAX)
        axp.set_yticks([])
        axp.tick_params(colors="white", labelsize=6.5 * fs, length=2)
        for s in axp.spines.values():
            s.set_color("white")
            s.set_linewidth(0.6)
        self.head = fig.text(*xy_head, "", color="white", fontsize=10 * fs, weight="bold", va="bottom")
        self.pct = fig.text(*xy_pct, "", color="#25c7ff", fontsize=9 * fs, ha="right", va="bottom")
        self.cnt = fig.text(*xy_cnt, "", color="white", fontsize=8 * fs, ha="right", va="bottom")

    def update(self, az_now: float) -> None:
        st, fs = self.st, self.fs
        A = st["A"]
        swept = st["az_px"] <= min(az_now, 359.95)
        self.im.set_data(np.where(swept[..., None], np.where(st["vis_px"][..., None], st["L_vis"], st["L_hidden"]),
                                  st["L_unswept"]))
        a = np.radians(az_now)
        self.sweep.set_data([0, R_MAX * np.sin(a)], [0, R_MAX * np.cos(a)])
        cols = ((az_now + self.xs_pano) / AZ_DEG).round().astype(int) % A
        self.pim.set_data(st["pano_rgb"][cols].transpose(1, 0, 2))
        self.sky_line.set_data(self.xs_pano, st["skyline"][cols])
        for art in self.dyn:
            art.remove()
        self.dyn.clear()
        n_in = 0
        for name, b, e, dist, ok, *_ in st["pk"]:
            diff = (b - az_now + 180) % 360 - 180
            if abs(diff) > FOV / 2 - 1:
                continue
            n_in += 1
            y_lab = e + 0.8 + 2.8 * (n_in % 3)
            label = SHORT.get(name, name) if self.short else f"{name.replace('Annapurna', 'Ann.')} {dist / 1000:.0f} km"
            if not ok and not self.short:
                label += " (hidden)"
            self.dyn.append(self.axp.scatter(diff, e, marker="^", s=22 * fs * fs, c="white" if ok else "none",
                                             ec="white", lw=0.8, zorder=6))
            self.dyn.append(self.axp.text(diff, y_lab, label, color="white" if ok else "#9fb0c8",
                                          fontsize=5.5 * fs, ha="center", va="bottom", zorder=7))
            self.dyn.append(self.axp.plot([diff, diff], [e + 0.4, y_lab], color="white", lw=0.3, alpha=0.6)[0])
        ticks = [(k * 22.5 - az_now + 180) % 360 - 180 for k in range(16)]
        keep = [(t, WINDS[k]) for k, t in enumerate(ticks) if abs(t) <= FOV / 2 - 3]
        self.axp.set_xticks([t for t, _ in keep])
        self.axp.set_xticklabels([lab for _, lab in keep])
        self.head.set_text(f"Looking {compass(az_now)} · {int(round(az_now)) % 360:03d}°")
        k = min(int(az_now / AZ_DEG), A - 1)
        self.pct.set_text(f"{st['cum'][k]:.1f}% of area in sight")
        n_seen = sum(1 for _, b, _, _, ok, *_ in st["pk"] if ok and b <= az_now + 1e-6)
        self.cnt.set_text(f"{n_seen} of {len(st['pk'])} giants")


def add_colorbar(fig, rect, fs=1.0):
    cax = fig.add_axes(rect)
    cax.imshow(np.linspace(0, 1, 256)[None, :], aspect="auto", cmap=CMAP, extent=(0, 75, 0, 1))
    cax.set_yticks([])
    cax.set_xticks([0, 25, 50, 75])
    cax.tick_params(colors="white", labelsize=6 * fs, length=1.5)
    cax.set_title("Distance from the viewpoint (km)", color="white", fontsize=6.5 * fs, pad=2)
    for s in cax.spines.values():
        s.set_visible(False)


def render(fig, panels, out: Path, width_px: int, height_px: int) -> None:
    """Sweep all panels together; write MP4 (full size) and GIF (GIF_W wide)."""
    width_px, height_px = fig.canvas.get_width_height()
    assert width_px % 2 == 0 and height_px % 2 == 0, (width_px, height_px)  # H.264 needs even sizes
    ff = subprocess.Popen(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{width_px}x{height_px}", "-r", f"{1000 / FRAME_MS:.3f}", "-i", "-", "-c:v", "libx264",
         "-crf", "14", "-preset", "slow", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
         str(out.with_suffix(".mp4"))], stdin=subprocess.PIPE)
    frames = []
    az_list = list(np.arange(0.0, 360.0 + 1e-6, SWEEP_STEP_DEG)) + [360.0] * HOLD_FRAMES
    last = None
    for az_now in az_list:
        for p in panels:
            p.update(az_now)
        fig.canvas.draw()
        buf = np.asarray(fig.canvas.buffer_rgba())[..., :3].copy()
        ff.stdin.write(buf.tobytes())
        last = Image.fromarray(buf)
        frames.append(last.resize((GIF_W, int(GIF_W * height_px / width_px)), Image.Resampling.LANCZOS))
    ff.stdin.close()
    ff.wait()
    plt.close(fig)
    q = [f.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG) for f in frames]
    q[0].save(out.with_suffix(".gif"), save_all=True, append_images=q[1:], duration=FRAME_MS, loop=0,
              optimize=False, disposal=1)
    last.save(m.WORK / (out.name + "_last.png"))
    log.info("-> %s (mp4 %.1f MB, gif %.1f MB)", out.name, out.with_suffix(".mp4").stat().st_size / 1e6,
             out.with_suffix(".gif").stat().st_size / 1e6)


def title_size(text: str, base: float, max_chars: int) -> float:
    return base if len(text) <= max_chars else base * max_chars / len(text)


# ---------------------------------------------------------------- outputs ---
def animate_single(st) -> None:
    FW, FH, DPI = 6.4, 8.2, 140
    fig = plt.figure(figsize=(FW, FH), dpi=DPI, facecolor=BG)
    title = f"How many Himalayan giants can you see from {st['vp']}?"
    fig.text(0.04, 0.965, title, color="white", fontsize=title_size(title, 12.5, 46), weight="bold", va="center")
    fig.text(0.04, 0.935, "A 360° sweep from the viewpoint, and what the view looks like",
             color="#25c7ff", fontsize=8, va="center")
    panel = Panel(fig, st, [0.03, 0.315, 0.94, 0.605], [0.05, 0.105, 0.90, 0.165],
                  (0.04, 0.318), (0.96, 0.318), (0.96, 0.292), fs=1.0, pano_w=800)
    fig.text(0.04, 0.02, f"#30DayMapChallenge | Day 5: Sight\nData: Copernicus GLO-30 DSM | Line of sight: radial sweep, "
             f"{m.TARGET_H_M:g} m eye height,\ncurvature + refraction. Area share within 75 km; "
             "panorama vertical scale exaggerated", color="#8794a8", fontsize=5, va="bottom", linespacing=1.4)
    add_colorbar(fig, [0.60, 0.050, 0.35, 0.011])
    name = st["vp"].lower().replace(" ", "_").replace("(", "").replace(")", "")
    render(fig, [panel], m.WORK / f"day05_sight_{name}", int(FW * DPI), int(FH * DPI))


def animate_grid(states) -> None:
    """All viewpoints on one page: 4 columns x 2 rows (last cell = legend / tally)."""
    COLS, ROWS, DPI = 4, 2, 130
    CW, CH = 2.4, 3.9  # cell size (in)
    TOP, BOT = 1.0, 0.6
    FW, FH = COLS * CW, TOP + ROWS * CH + BOT
    fig = plt.figure(figsize=(FW, FH), dpi=DPI, facecolor=BG)

    def fx(x_in):
        return x_in / FW

    def fy(y_in):
        return y_in / FH

    fig.text(fx(0.2), fy(FH - 0.38), "How many Himalayan giants can you see from Pokhara’s viewpoints?",
             color="white", fontsize=16, weight="bold", va="center")
    fig.text(fx(0.2), fy(FH - 0.72), "A 360° sweep from each viewpoint, all at once — and what the view looks like",
             color="#25c7ff", fontsize=9.5, va="center")
    panels = []
    tally = []
    for i, st in enumerate(states):
        r_i, c_i = divmod(i, COLS)
        x0 = c_i * CW
        y_top = FH - TOP - r_i * CH
        head = f"{st['vp']} · {st['vz']:,.0f} m"
        fig.text(fx(x0 + 0.12), fy(y_top - 0.20), head, color="white", fontsize=title_size(head, 9.5, 22),
                 weight="bold", va="center")
        map_side = CW - 0.5  # leave room for the N/E/S/W letters inside the cell
        rect_map = [fx(x0 + 0.25), fy(y_top - 0.42 - map_side), fx(map_side), fy(map_side)]
        pano_h = 0.72
        y_pano = y_top - 0.42 - map_side - 0.20 - pano_h
        rect_pano = [fx(x0 + 0.16), fy(y_pano), fx(CW - 0.28), fy(pano_h)]
        y_txt = y_pano - 0.52  # below the panorama tick labels
        panels.append(Panel(fig, st, rect_map, rect_pano,
                            (fx(x0 + 0.12), fy(y_txt + 0.02)), (fx(x0 + CW - 0.1), fy(y_txt + 0.17)),
                            (fx(x0 + CW - 0.1), fy(y_txt - 0.01)), fs=0.62, center_label=False,
                            short_names=True, pano_w=520))
        tally.append((st["vp"], sum(1 for t in st["pk"] if t[4]), len(st["pk"])))
    # legend / tally cell
    i = len(states)
    r_i, c_i = divmod(i, COLS)
    x0, y_top = c_i * CW, FH - TOP - r_i * CH
    fig.text(fx(x0 + 0.12), fy(y_top - 0.20), "Giants in line of sight", color="white", fontsize=9.5,
             weight="bold", va="center")
    for k, (vp, n_ok, n_all) in enumerate(sorted(tally, key=lambda t: -t[1])):
        yy = y_top - 0.60 - k * 0.27
        fig.text(fx(x0 + 0.12), fy(yy), vp, color="white", fontsize=7.5, va="center")
        fig.text(fx(x0 + CW - 0.12), fy(yy), f"{n_ok} of {n_all}", color="#25c7ff", fontsize=7.5, ha="right",
                 va="center", weight="bold")
    add_colorbar(fig, [fx(x0 + 0.2), fy(y_top - CH + 0.75), fx(CW - 0.4), fy(0.09)], fs=1.1)
    fig.text(fx(x0 + 0.12), fy(y_top - CH + 0.35),
             "Triangles on the map: the nine giants\n(filled = visible, hollow = hidden).\nSame distance colours everywhere.",
             color="#b8c4d6", fontsize=6.3, va="center", linespacing=1.4)
    fig.text(fx(0.2), fy(0.28),
             "#30DayMapChallenge | Day 5: Sight    Data: Copernicus GLO-30 DSM    Line of sight: radial sweep, "
             f"{m.TARGET_H_M:g} m eye height, earth curvature + refraction    Area share within 75 km; "
             "panorama vertical scale exaggerated", color="#8794a8", fontsize=6, va="center")
    render(fig, panels, m.WORK / "day05_sight_pokhara_grid", int(FW * DPI), int(FH * DPI))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    mode = sys.argv[1] if len(sys.argv) > 1 else "grid"
    want = [a.lower() for a in sys.argv[2:]]
    m.WORK.mkdir(exist_ok=True)
    dem_path = m.WORK / "dem_utm44n_30m.tif"  # the same DEM the map and table use
    m.build_dem(dem_path)
    with rasterio.open(dem_path) as src:
        dem_raw, tr, nodata = src.read(1), src.transform, src.nodata
    dem = np.where(dem_raw == nodata, 0.0, dem_raw).astype(np.float32)
    hs_small = LightSource(azdeg=315, altdeg=40).hillshade(
        dem[::4, ::4], vert_exag=2.5, dx=m.RES_M * 4, dy=m.RES_M * 4)
    to_utm = Transformer.from_crs("EPSG:4326", m.CRS, always_xy=True)

    peaks = []
    for p in m.PEAKS:
        x, y = to_utm.transform(p.lon, p.lat)
        sx, sy, sz = m.snap_to_summit(dem_raw, tr, x, y, nodata)
        if abs(sz - p.elev_m) <= m.ELEV_TOL_M:
            peaks.append((p, (sx, sy, sz)))

    states = []
    for vp, (lon, lat, vp_elev, snap_m) in m.VIEWPOINTS.items():
        if want and not any(w in vp.lower() for w in want):
            continue
        x, y = to_utm.transform(lon, lat)
        try:
            vx, vy, vz = m.snap_to_summit(dem_raw, tr, x, y, nodata, radius_m=snap_m)
        except ValueError as e:
            log.warning("SKIP %s: %s", vp, e)
            continue
        if abs(vz - vp_elev) > m.VP_ELEV_TOL_M:
            log.warning("SKIP %s: DEM %.0f m vs published %.0f m", vp, vz, vp_elev)
            continue
        st = prepare(vp, vx, vy, vz, dem, tr, hs_small, peaks, npix=1100 if mode == "single" else 460)
        if mode == "single":
            animate_single(st)
        else:
            states.append(st)
    if mode == "grid":
        animate_grid(states)


if __name__ == "__main__":
    main()
