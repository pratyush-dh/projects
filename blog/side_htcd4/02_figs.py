#!/usr/bin/env python3
"""HTCD 4 side project, step 2: figures. Academic style matching the HTCD 2 post (sampled points + median/IQR/5-95pct
bands, error-bar bias plots, ecodivision choropleths). Palette: blue = FIA's own HTCD 4 height, orange = our regional
model (trained only on HTCD 1)."""
import json
import numpy as np, pandas as pd, geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import colors
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Patch
from shapely import affinity

BLUE, ORANGE, RED, GREY, INK, MUTE, GRID = "#2a78d6", "#eb6834", "#e34948", "#8a8a86", "#0b0b0b", "#52514e", "#e6e5e1"
plt.rcParams.update({"font.family": "Arial", "font.size": 10, "axes.labelsize": 10, "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlelocation": "left",
                     "text.color": INK, "axes.labelcolor": MUTE, "xtick.color": MUTE, "ytick.color": MUTE, "axes.edgecolor": "#b9b8b2", "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.7, "axes.axisbelow": True, "figure.facecolor": "white",
                     "pdf.fonttype": 42, "savefig.dpi": 200, "figure.constrained_layout.use": True, "legend.frameon": False})
DIV = LinearSegmentedColormap.from_list("bwr_grey", [BLUE, "#f0efec", RED])
NODATA = "#e4e3df"
P = "../paper/data/"


def save(fig, n):
    for ext in ("png", "pdf"):
        try: fig.savefig(f"figures/{n}.{ext}", bbox_inches="tight")
        except OSError: fig.savefig(f"figures/{n}_new.{ext}", bbox_inches="tight"); print("locked ->", f"{n}_new.{ext}")
    plt.close(fig)


h4 = pd.read_pickle("out/resid_sample.pkl")
T1 = pd.read_csv("out/t1_by_dbh.csv"); T2 = pd.read_csv("out/t2_by_division.csv", dtype={"division": str}); T3 = pd.read_csv("out/t3_by_state.csv")
LAB = ["1-4.9", "5-9.9", "10-14.9", "15-19.9", "20-29.9", "30+"]
names = {1: "AL", 5: "AR", 6: "CA", 12: "FL", 13: "GA", 21: "KY", 22: "LA", 28: "MS", 37: "NC", 40: "OK", 41: "OR", 45: "SC", 47: "TN", 48: "TX", 51: "VA", 53: "WA"}

# ---------------------------------------------------------------- Fig 1: overall distributions + bias by DBH class
fig, axs = plt.subplots(1, 2, figsize=(11, 4.6), gridspec_kw=dict(width_ratios=[1, 1.1]))
a = axs[0]
edges = np.linspace(-1.0, 1.0, 81)
h, _ = np.histogram(h4.lr, bins=edges, density=True); a.stairs(h, edges, color=BLUE, lw=1.8, fill=True, alpha=0.25)
a.stairs(h, edges, color=BLUE, lw=1.8)
a.axvline(0, color=INK, lw=0.9); a.axvline(h4.lr.mean(), color=RED, lw=1.4, ls=(0, (4, 3)))
a.set_xlabel("ln(FIA modeled height / our regional model)"); a.set_ylabel("Density"); a.set_xlim(-1, 1)
a.set_title("Same trees, two imputation methods", pad=8)
a.text(0.97, 0.95, f"mean = {h4.lr.mean():+.3f}\n(+{100*(np.exp(h4.lr.mean())-1):.2f}%)\nSD = {h4.lr.std():.2f}\nn = {len(h4):,}", transform=a.transAxes, ha="right", va="top", fontsize=9.5, color=INK)
b = axs[1]; x = np.arange(len(T1))
b.axhline(0, color=INK, lw=0.9)
b.errorbar(x, T1.bias_pct, yerr=[T1.bias_pct - T1.bias_pct_lo, T1.bias_pct_hi - T1.bias_pct], fmt="o-", color=BLUE, lw=1.8, ms=6, capsize=3)
b.set_xticks(x, LAB); b.set_xlabel("Diameter class (in)"); b.set_ylabel("FIA modeled height vs our regional model (%)")
b.set_title("Bias grows for mid-to-large trees", pad=8)
fig.text(0.0, -0.02, "\"Our regional model\": species x ecodivision Curtis-Arney/Wykoff, fitted only on field-measured (HTCD 1) trees. Positive = FIA's stored height is taller.", fontsize=9, color=MUTE)
save(fig, "fig1_overall_and_dbh")

# ---------------------------------------------------------------- Fig 2: ecodivision map of excess bias (vs the model's own regional bias on measured trees)
div = gpd.read_file(P + "eco_divisions_5070.gpkg"); div = div[div.division_code != "Water"].rename(columns={"division_code": "division"})
st_ll = gpd.read_file(P + "states-10m.json", layer="states").set_crs(4326)
st_conus = st_ll[(st_ll.id.astype(int) <= 56) & (~st_ll.id.astype(int).isin([2, 15]))].to_crs(5070)
XMIN, YMIN, XMAX, YMAX = st_conus.total_bounds
fig, axs = plt.subplots(1, 2, figsize=(12.5, 4.9))
for ax, col, ttl, norm, lab in ((axs[0], "htcd4_bias_pct", "a  FIA modeled (HTCD 4) height vs our model", colors.Normalize(-4, 4), "Mean HTCD 4 / model - 1 (%)"),
                                (axs[1], "excess_pct", "b  Excess: (a) minus the model's own bias here", colors.Normalize(-4, 4), "Percentage points; hatched = not distinguishable")):
    g = div.merge(T2, on="division", how="left"); ok = g[col].notna() & (g.n >= 1000)  # keeps only divisions genuinely inside CA/OR/WA (see fig3 note)
    g[~ok].plot(ax=ax, color=NODATA, edgecolor="white", linewidth=0.3)
    g[ok].plot(column=col, cmap=DIV, norm=norm, ax=ax, edgecolor="white", linewidth=0.3)
    if col == "excess_pct":
        g[ok & ~g.significant.fillna(False).astype(bool)].plot(ax=ax, facecolor="none", edgecolor="0.35", hatch="////", linewidth=0)
    st_conus.boundary.plot(ax=ax, color="0.3", linewidth=0.25); ax.set_axis_off(); ax.set_aspect("equal")
    ax.set_xlim(XMIN - 5e4, XMAX + 5e4); ax.set_ylim(YMIN - 5e4, YMAX + 5e4); ax.set_title(ttl, pad=4)
    cb = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=DIV), ax=ax, orientation="horizontal", shrink=0.55, pad=0.01, aspect=30, extend="both")
    cb.set_label(lab, fontsize=8.5)
axs[0].legend(handles=[Patch(color=NODATA, label="Fewer than 1,000 HTCD 4 trees / no data")], loc="lower left", fontsize=8, labelcolor=INK)
fig.text(0.0, -0.02, "Only divisions with 1,000+ HTCD 4 trees are colored: these six, all inside CA/OR/WA, hold 99.1% of all HTCD 4 trees nationally. Outside these states HTCD 4 is a handful of scattered records per state (Fig. 3) and is not mapped.", fontsize=8.5, color=MUTE)
save(fig, "fig2_maps_ecodivision")

# ---------------------------------------------------------------- Fig 3: by state -- honestly: 3 real states + everything else pooled
S = json.load(open("out/summary.json"))
core = T3[T3.statecd.isin([6, 41, 53])].copy(); core["state"] = core.statecd.map(names)
other_n, other_pct = S["other_states_n"], S["other_states_bias_pct"]
rows = list(core[["state", "n", "bias_pct", "lo", "hi"]].itertuples(index=False, name=None))
rows.append(("13 other states\n(pooled, no CI)", other_n, other_pct, np.nan, np.nan))
lab_, n_, pct_, lo_, hi_ = zip(*sorted(rows, key=lambda r: r[2]))
fig, ax = plt.subplots(figsize=(8.0, 4.2)); y = np.arange(len(lab_))
ax.axvline(0, color=INK, lw=0.9)
for i, (p, l, h) in enumerate(zip(pct_, lo_, hi_)):
    col = MUTE if np.isnan(l) else BLUE
    if not np.isnan(l): ax.errorbar([p], [i], xerr=[[p - l], [h - p]], fmt="o", color=col, ms=7, lw=1.8, capsize=4)
    else: ax.plot(p, i, "D", color=col, ms=7)
ax.set_yticks(y, [f"{s}  (n = {n:,})" for s, n in zip(lab_, n_)]); ax.set_xlabel("FIA modeled (HTCD 4) height vs our regional model (%)")
ax.set_title("By state: where HTCD 4 actually lives", pad=8)
ax.text(0.0, -0.32, "CA, OR and WA hold 99.3% of all HTCD 4 trees. The other 13 states together hold 0.7% (scattered records, a handful to a few hundred per state) -- pooled here, not a reliable regional estimate.", transform=ax.transAxes, fontsize=8.5, color=MUTE)
save(fig, "fig3_by_state")

# ---------------------------------------------------------------- Fig 4: the tall-tree tail
fig, axs = plt.subplots(1, 2, figsize=(11.5, 4.8))
a = axs[0]
idx = np.random.default_rng(1).choice(len(h4), min(30000, len(h4)), replace=False)
a.scatter(h4.new_ht.values[idx], h4.old_ht.values[idx], s=3, c=MUTE, alpha=0.25, linewidths=0)
lims = (0, 290); a.plot(lims, lims, color=INK, lw=1.0, ls=(0, (5, 3)))
a.set_xlim(lims); a.set_ylim(lims); a.set_xlabel("Our regional model (ft)"); a.set_ylabel("FIA's stored HTCD 4 height (ft)")
a.set_title("a  Every HTCD 4 tree", pad=8)
b = axs[1]
qs = np.linspace(0.5, 1.0, 60)
b.plot(100 * qs, h4.old_ht.quantile(qs), color=BLUE, lw=2, label="FIA modeled (HTCD 4)")
b.plot(100 * qs, h4.new_ht.quantile(qs), color=ORANGE, lw=2, label="Our regional model")
b.set_xlabel("Percentile of the height distribution"); b.set_ylabel("Height (ft)"); b.set_title("b  Upper-tail quantiles", pad=8); b.legend(loc="upper left", labelcolor=INK)
b.axvline(99, color=MUTE, lw=0.7, ls=":")
fig.text(0.0, -0.02, "a: 30,000 sampled trees; dashed = 1:1. b: FIA's own values reach taller than our model can, almost entirely among Douglas-fir in the Marine (Pacific coast) ecodivision (952 of the 1,079 trees above 200 ft).", fontsize=8.5, color=MUTE)
save(fig, "fig4_tall_tree_tail")

# ---------------------------------------------------------------- Fig 5: species (top 12)
T4 = pd.read_csv("out/t4_by_species.csv").sort_values("n")
fig, ax = plt.subplots(figsize=(8.2, 5.0)); y = np.arange(len(T4))
ax.axvline(0, color=INK, lw=0.9); ax.barh(y, T4.bias_pct, color=[RED if v > 0 else BLUE for v in T4.bias_pct], height=0.65)
ax.set_yticks(y, [f"{s} (n = {n:,})" for s, n in zip(T4.species, T4.n)]); ax.set_xlabel("FIA modeled (HTCD 4) height vs our regional model (%)")
ax.set_title("The 12 most common HTCD 4 species", pad=8)
save(fig, "fig5_by_species")
print("done")
