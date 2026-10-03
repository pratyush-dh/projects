#!/usr/bin/env python3
"""Carbon-by-ecoregion, step 8: design-weighted figures for the blog post.
  fig3_map_mean_carbon      -- design-based mean carbon per forested acre by ecodivision (out/d2_division_design.csv)
  fig5_variance_by_division -- design-weighted CV by division, ordered by number of forested plots
  fig6_cv_vs_nplots         -- design-weighted CV vs number of forested plots (log scale) with OLS trend on log(n)
Single hue throughout (BLUE / sequential green), so no categorical palette needs validation.
"""
import numpy as np, pandas as pd, geopandas as gpd
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.patheffects as pe
from matplotlib.colors import LinearSegmentedColormap

MIN_N = 100
BLUE, RED, INK, MUTE, GRID = "#2a78d6", "#e34948", "#0b0b0b", "#52514e", "#e6e5e1"
plt.rcParams.update({"font.family": "Arial", "font.size": 10, "axes.labelsize": 10, "axes.titlesize": 11,
                     "axes.titleweight": "bold", "axes.titlelocation": "left", "text.color": INK,
                     "axes.labelcolor": MUTE, "xtick.color": MUTE, "ytick.color": MUTE, "axes.edgecolor": "#b9b8b2",
                     "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": GRID,
                     "grid.linewidth": 0.7, "axes.axisbelow": True, "figure.facecolor": "white", "pdf.fonttype": 42,
                     "savefig.dpi": 200})


def save(fig, name):
    for ext in ("png", "pdf"):
        fig.savefig(f"figures/{name}.{ext}", bbox_inches="tight")
    plt.close(fig)


d2 = pd.read_csv("out/d2_division_design.csv")
b = d2[d2.n_forest >= MIN_N].sort_values("n_forest").reset_index(drop=True)

# fig5: design-weighted CV in ascending order of forested plots
fig, ax = plt.subplots(figsize=(14, 6))
pos = np.arange(len(b))
ax.scatter(pos, b.wcv, color=BLUE, s=36, alpha=0.9, edgecolor="white", linewidth=0.6, zorder=3)
ax.set_xticks(pos, b.division, fontsize=7.5, rotation=90)
ax.set_xlabel("Ecodivision (sorted by number of forested plots, ascending)")
ax.set_ylabel("Design-weighted coefficient of variation (sd / mean)")
ax.set_title("Design-weighted coefficient of variation of carbon density by ecodivision", pad=8)
save(fig, "fig5_variance_by_division")

# fig6: design-weighted CV vs n, trend on log(n)
r, p = stats.pearsonr(np.log(b.n_forest), b.wcv)
slope, intercept = np.polyfit(np.log(b.n_forest), b.wcv, 1)
fig, ax = plt.subplots(figsize=(9, 7))
ax.scatter(b.n_forest, b.wcv, color=BLUE, s=36, alpha=0.9, edgecolor="white", linewidth=0.6, zorder=3)
for dv, xn, yv in zip(b.division, b.n_forest, b.wcv):
    ax.annotate(dv, (xn, yv), xytext=(4, 3), textcoords="offset points", fontsize=6.5, color=MUTE)
xx = np.linspace(np.log(b.n_forest).min(), np.log(b.n_forest).max(), 100)
ax.plot(np.exp(xx), slope * xx + intercept, color=RED, lw=1.4, ls=(0, (5, 3)), zorder=2)
ax.set_xscale("log")
ax.set_xlabel("Number of forested plots (n), log scale")
ax.set_ylabel("Design-weighted coefficient of variation (sd / mean)")
ax.set_title("Design-weighted CV vs. number of plots, by ecodivision", pad=8)
ax.text(0.98, 0.97, f"Pearson r = {r:.2f} (log n vs. CV), p = {p:.3f}\nfitted line: OLS of CV on log(n)",
        transform=ax.transAxes, ha="right", va="top", fontsize=8.5, color=MUTE)
save(fig, "fig6_cv_vs_nplots")
print(f"CV vs log(n): r={r:.3f}, p={p:.4f}, n={len(b)}")

# fig3: map of design-based means
st_ll = gpd.read_file("../paper/data/states-10m.json", layer="states").set_crs(4326)
st_conus = st_ll[(st_ll.id.astype(int) <= 56) & (~st_ll.id.astype(int).isin([2, 15]))].to_crs(5070)
XMIN, YMIN, XMAX, YMAX = st_conus.total_bounds
div_poly = gpd.read_file("../paper/data/eco_divisions_5070.gpkg").rename(columns={"division_code": "division"})
div_poly = div_poly[div_poly.division != "Water"].merge(
    d2[["division", "mean_tC_per_acre", "n_forest"]], on="division", how="left")
SEQ = LinearSegmentedColormap.from_list("seq_green", ["#eef6ee", "#1baf7a", "#0a4d36"])
norm = mcolors.Normalize(0, 60)
ok = div_poly.mean_tC_per_acre.notna() & (div_poly.n_forest >= MIN_N)
fig, ax = plt.subplots(figsize=(9, 6))
div_poly[~ok].plot(ax=ax, color="#e4e3df", edgecolor="none", zorder=1)
div_poly[ok].plot(column="mean_tC_per_acre", cmap=SEQ, norm=norm, ax=ax, edgecolor="none", zorder=1)
st_conus.boundary.plot(ax=ax, color="0.75", linewidth=0.4, zorder=2)
div_poly.dissolve(by="division", as_index=False).plot(ax=ax, facecolor="none", edgecolor="0.2", linewidth=0.8, zorder=3)
lbl = div_poly.dissolve(by="division", as_index=False)
for r_ in lbl.itertuples():
    rep = r_.geometry.representative_point()
    ax.annotate(r_.division, xy=(rep.x, rep.y), fontsize=5, ha="center", va="center", color="#1a1a1a", zorder=4,
                path_effects=[pe.withStroke(linewidth=1.6, foreground="white")])
ax.set_axis_off(); ax.set_aspect("equal")
ax.set_xlim(XMIN - 5e4, XMAX + 5e4); ax.set_ylim(YMIN - 5e4, YMAX + 5e4)
ax.set_title("Design-based mean live-tree carbon density by ecodivision", pad=8)
cb = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=SEQ), ax=ax, orientation="horizontal", shrink=0.55,
                  pad=0.01, aspect=30, extend="max")
cb.set_label("Tons C per forested acre (FIA post-stratified estimate)", fontsize=9)
save(fig, "fig3_map_mean_carbon")
print("done")
