#!/usr/bin/env python3
"""Side project, step 7: box plots of residuals, regional bias graphs, maps and regional model curves (HTCD 2 vs HTCD 1-derived model).
Palette: reference-palette blue/red diverging pair with a grey midpoint (bias sign), grey = intact measured control, blue = HTCD 2, orange = model.
Outputs: figures/fig4 ... fig11 (PNG 200 dpi + PDF)."""
import numpy as np, pandas as pd, geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import cm, colors
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Patch
from shapely import affinity

BLUE, ORANGE, RED, GREY, INK, MUTE, GRID = "#2a78d6", "#eb6834", "#e34948", "#8a8a86", "#0b0b0b", "#52514e", "#e6e5e1"
plt.rcParams.update({"font.family": "Arial", "font.size": 10, "axes.labelsize": 10, "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlelocation": "left",
                     "text.color": INK, "axes.labelcolor": MUTE, "xtick.color": MUTE, "ytick.color": MUTE, "axes.edgecolor": "#b9b8b2", "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": False, "figure.facecolor": "white", "pdf.fonttype": 42, "savefig.dpi": 200, "figure.constrained_layout.use": True,
                     "legend.frameon": False, "hatch.linewidth": 0.5})
DIV = LinearSegmentedColormap.from_list("bwr_grey", [BLUE, "#f0efec", RED])
SEQ = LinearSegmentedColormap.from_list("seq_teal", ["#e8f5ef", "#1baf7a", "#0a4d36"])   # magnitude only; blue/red are reserved for the sign of a bias
NODATA = "#e4e3df"
P = "../paper/data/"
LAB = ["1-4.9", "5-9.9", "10-14.9", "15-19.9", "20-29.9", "30+"]
T8 = pd.read_csv("out/t8_division.csv", dtype={"division": str}); T9 = pd.read_csv("out/t9_state.csv"); INV = pd.read_csv("out/t10_model_inventory.csv", dtype={"division": str})
T11 = pd.read_csv("out/t11_division_by_dbh.csv", dtype={"division": str}); smp = pd.read_pickle("out/resid_samples.pkl")
def save(fig, n):
    for ext in ("png", "pdf"):
        try:
            fig.savefig(f"figures/{n}.{ext}", bbox_inches="tight")
        except OSError:   # file open in a viewer (PermissionError / Errno 22): write next to it instead of failing
            fig.savefig(f"figures/{n}_new.{ext}", bbox_inches="tight"); print("locked, wrote", f"{n}_new.{ext}")
    plt.close(fig)

# ---------------------------------------------------------------- geometry
div = gpd.read_file(P + "eco_divisions_5070.gpkg"); div = div[div.division_code != "Water"].rename(columns={"division_code": "division"})
st_ll = gpd.read_file(P + "states-10m.json", layer="states").set_crs(4326)
st_conus = st_ll[(st_ll.id.astype(int) <= 56) & (~st_ll.id.astype(int).isin([2, 15]))].to_crs(5070)
XMIN, YMIN, XMAX, YMAX = st_conus.total_bounds
st_alb = gpd.read_file(P + "states-albers-10m.json", layer="states"); st_alb["statecd"] = st_alb.id.astype(int)
st_alb["geometry"] = st_alb.geometry.apply(lambda g: affinity.scale(g, yfact=-1, origin=(0, 0)))   # us-atlas screen coordinates -> north up


def frame(ax, conus=True):
    ax.set_axis_off(); ax.set_aspect("equal")
    if conus: ax.set_xlim(XMIN - 5e4, XMAX + 5e4); ax.set_ylim(YMIN - 5e4, YMAX + 5e4)


def dmap(ax, col, cmap, norm, title, hatch_col=None, minn=None, ncol=None):
    g = div.merge(T8, on="division", how="left")
    ok = g[col].notna() & ((g[ncol] >= minn) if ncol else True)
    g[~ok].plot(ax=ax, color=NODATA, edgecolor="white", linewidth=0.3)
    g[ok].plot(column=col, cmap=cmap, norm=norm, ax=ax, edgecolor="white", linewidth=0.3)
    if hatch_col is not None:
        ns = g[ok & ~g[hatch_col].fillna(False).astype(bool)]
        ns.plot(ax=ax, facecolor="none", edgecolor="0.35", hatch="////", linewidth=0)
    st_conus.boundary.plot(ax=ax, color="0.3", linewidth=0.25); frame(ax); ax.set_title(title, pad=4)


def smap(ax, col, cmap, norm, title, minn=None, ncol=None, hatch_col=None):
    g = st_alb.merge(T9.rename(columns={"statecd": "statecd"}), on="statecd", how="left")
    ok = g[col].notna() & ((g[ncol] >= minn) if ncol else True)
    g[~ok].plot(ax=ax, color=NODATA, edgecolor="white", linewidth=0.4)
    g[ok].plot(column=col, cmap=cmap, norm=norm, ax=ax, edgecolor="white", linewidth=0.4)
    if hatch_col is not None:
        g[ok & ~g[hatch_col].fillna(False).astype(bool)].plot(ax=ax, facecolor="none", edgecolor="0.35", hatch="////", linewidth=0)
    ax.set_axis_off(); ax.set_aspect("equal"); ax.set_title(title, pad=4)


def cbar(fig, ax, cmap, norm, label, ext="neither"):
    cb = fig.colorbar(cm.ScalarMappable(norm=norm, cmap=cmap), ax=ax, orientation="horizontal", shrink=0.62, pad=0.01, aspect=32, extend=ext)
    cb.set_label(label, fontsize=9); cb.outline.set_linewidth(0.4); cb.ax.tick_params(labelsize=8)


def bxp_stats(v, label):
    q = np.percentile(v, [5, 25, 50, 75, 95]); return dict(label=label, whislo=q[0], q1=q[1], med=q[2], q3=q[3], whishi=q[4], fliers=[])


def draw_boxes(ax, groups, sets, horizontal=False):
    """groups: list of (label, mask-key) ; sets: dict name->(dataframe, colour); boxes side by side"""
    w = 0.34; pos_ = np.arange(len(groups))
    for j, (nm, (df, colr)) in enumerate(sets.items()):
        st = [bxp_stats(df.loc[m, "v"].values, "") for m in [df.g == k for k in groups]]
        off = (j - 0.5) * (w + 0.04)
        ax.bxp(st, positions=pos_ + off, widths=w, vert=not horizontal, patch_artist=True, showfliers=False,
               boxprops=dict(facecolor=colr, edgecolor=colr, alpha=0.85, linewidth=0.8), medianprops=dict(color="white", linewidth=1.6),
               whiskerprops=dict(color=colr, linewidth=1.0), capprops=dict(color=colr, linewidth=1.0))
    return pos_


# ---------------------------------------------------------------- Fig 4: residual box plots
smp["dclass"] = pd.Categorical(smp.dclass, categories=LAB, ordered=True)
top = T8.sort_values("n_htcd2", ascending=False).head(12).division.tolist()
fig, axs = plt.subplots(1, 3, figsize=(15, 5.4), gridspec_kw=dict(width_ratios=[1, 1, 1.05]))
for ax, val, yl, ttl in ((axs[0], "lr", "ln(height / model height)", "Relative residual, by diameter class"), (axs[1], "r", "Height minus model height (ft)", "Residual in feet, by diameter class")):
    sets = {n: (pd.DataFrame({"v": smp.loc[smp.set == k, val].values, "g": smp.loc[smp.set == k, "dclass"].astype(str).values}), c) for n, k, c in (("Intact measured (HTCD 1)", "control", GREY), ("Crew-reconstructed (HTCD 2)", "htcd2", BLUE))}
    pos = draw_boxes(ax, LAB, sets); ax.axhline(0, color=INK, lw=0.8); ax.set_xticks(pos, LAB); ax.set_xlabel("Diameter class (in)"); ax.set_ylabel(yl); ax.set_title(ttl, pad=6)
    ax.grid(axis="y", color=GRID, lw=0.7); ax.set_axisbelow(True)
fig.legend(handles=[Patch(color=GREY, label="Intact measured (HTCD 1, unseen plots)"), Patch(color=BLUE, label="Crew-reconstructed (HTCD 2)")], loc="lower center", ncol=2, fontsize=10, labelcolor=INK, bbox_to_anchor=(0.5, -0.07))
lab = [f"{d} {T8.set_index('division').division_name[d]}" for d in top]
sets = {n: (pd.DataFrame({"v": smp.loc[smp.set == k, "lr"].values, "g": smp.loc[smp.set == k, "division"].values}), c) for n, k, c in (("c", "control", GREY), ("h", "htcd2", BLUE))}
ax = axs[2]; pos = draw_boxes(ax, top, sets, horizontal=True); ax.axvline(0, color=INK, lw=0.8); ax.set_yticks(pos, lab); ax.invert_yaxis(); ax.set_xlabel("ln(height / model height)")
ax.set_title("Relative residual, 12 largest ecodivisions", pad=6); ax.grid(axis="x", color=GRID, lw=0.7); ax.set_axisbelow(True)
fig.text(0.0, -0.075, "Boxes: 25th-75th percentile; white line: median; whiskers: 5th-95th percentile.", fontsize=9, color=MUTE)
save(fig, "fig4_residual_boxplots")

# ---------------------------------------------------------------- Fig 5: bias by ecodivision (dumbbell + excess with CI)
T = T8[T8.n_htcd2 >= 500].sort_values("excess_pct").reset_index(drop=True)
y = np.arange(len(T)); lab = [f"{r.division} {r.division_name}" for r in T.itertuples()]
fig, (a, b) = plt.subplots(1, 2, figsize=(13, 0.34 * len(T) + 2.2), sharey=True, gridspec_kw=dict(width_ratios=[1, 1]))
a.axvline(0, color=INK, lw=0.8); a.hlines(y, T.htcd2_bias_pct, T.ctl_bias_pct, color="#c9c8c2", lw=2, zorder=1)
a.scatter(T.ctl_bias_pct, y, s=46, color=GREY, zorder=3, label="Intact measured trees (model's own bias)"); a.scatter(T.htcd2_bias_pct, y, s=46, color=BLUE, zorder=3, label="Crew-reconstructed (HTCD 2)")
a.set_yticks(y, lab); a.set_xlabel("Mean height relative to model prediction (%)"); a.set_title("Model bias vs crew bias", pad=6); a.legend(loc="lower right", fontsize=9, labelcolor=INK)
a.grid(axis="x", color=GRID, lw=0.7); a.set_axisbelow(True)
b.axvline(0, color=INK, lw=0.8)
for i, r in T.iterrows():
    c = BLUE if r.significant and r.excess_pct < 0 else (RED if r.significant else GREY)
    b.hlines(i, r.excess_pct_lo, r.excess_pct_hi, color=c, lw=2.2, zorder=2); b.scatter(r.excess_pct, i, s=46, color=c, zorder=3)
    b.text(b.get_xlim()[1] if False else 8.6, i, f"n = {int(r.n_htcd2):,}", va="center", fontsize=8.5, color=MUTE)
b.set_xlim(-8, 11.5); b.set_xlabel("Excess bias of HTCD 2 over intact trees (%, 95% CI)"); b.set_title("Difference between the two", pad=6); b.grid(axis="x", color=GRID, lw=0.7); b.set_axisbelow(True)
b.legend(handles=[Patch(color=BLUE, label="Crews lower than model (CI excludes 0)"), Patch(color=RED, label="Crews higher"), Patch(color=GREY, label="No detectable difference")], loc="upper left", fontsize=8.5, labelcolor=INK)
save(fig, "fig5_bias_by_ecodivision")

# ---------------------------------------------------------------- Fig 6: division maps: regional model quality and the HTCD 2 bias
fig, axs = plt.subplots(2, 2, figsize=(13, 8.4))
n1 = colors.Normalize(0, 14); dmap(axs[0, 0], "ctl_rmse_ft", SEQ, n1, "a  Regional model error on intact trees (RMSE, ft)", minn=200, ncol="n_ctl"); cbar(fig, axs[0, 0], SEQ, n1, "RMSE on unseen plots (ft)")
n2 = colors.Normalize(-4, 4); dmap(axs[0, 1], "ctl_bias_pct", DIV, n2, "b  Regional model bias on intact trees (%)", minn=200, ncol="n_ctl"); cbar(fig, axs[0, 1], DIV, n2, "Mean measured / model - 1 (%)", "both")
n3 = colors.Normalize(-8, 8); dmap(axs[1, 0], "htcd2_bias_pct", DIV, n3, "c  Crew-reconstructed (HTCD 2) height vs model (%)", minn=100, ncol="n_htcd2"); cbar(fig, axs[1, 0], DIV, n3, "Mean HTCD 2 / model - 1 (%)", "both")
dmap(axs[1, 1], "excess_pct", DIV, n3, "d  Excess bias: (c) minus (b)", hatch_col="significant", minn=100, ncol="n_htcd2"); cbar(fig, axs[1, 1], DIV, n3, "Percentage points; hatched = CI includes 0", "both")
axs[0, 0].legend(handles=[Patch(color=NODATA, label="Too few trees")], loc="lower left", fontsize=8.5, labelcolor=INK)
save(fig, "fig6_maps_ecodivision_bias")

# ---------------------------------------------------------------- Fig 7: state maps
fig, axs = plt.subplots(2, 2, figsize=(13, 8.6))
smap(axs[0, 0], "excess_pct", DIV, n3, "a  Excess bias of HTCD 2 over intact trees (%)", minn=200, ncol="n_htcd2", hatch_col="significant"); cbar(fig, axs[0, 0], DIV, n3, "Percentage points; hatched = CI includes 0", "both")
nn = colors.LogNorm(200, T9.n_htcd2.max()); smap(axs[0, 1], "n_htcd2", SEQ, nn, "b  HTCD 2 trees with a reconstructed height (count)"); cbar(fig, axs[0, 1], SEQ, nn, "Trees, log scale")
n4 = colors.Normalize(0, 0.7); smap(axs[1, 0], "copied_share", SEQ, n4, "c  HTCD 2 heights identical to the earlier recorded height", minn=1, ncol="n_pairs_all"); cbar(fig, axs[1, 0], SEQ, n4, "Share of HTCD 2 trees with an earlier record whose HT is identical to it", "max")
n5 = colors.Normalize(-8, 8); smap(axs[1, 1], "crew_vs_earlier_pct", DIV, n5, "d  Crew height vs earlier measured height (%)", minn=200, ncol="n_anchor"); cbar(fig, axs[1, 1], DIV, n5, "Mean crew / earlier - 1 (%); trees with HT != previous HT", "both")
fig.text(0.0, -0.012, "Alaska and Hawaii have no ecodivision assignment and are not modeled (grey). Grey = fewer than 200 trees.", fontsize=9, color=MUTE)
save(fig, "fig7_maps_state_bias")

# ---------------------------------------------------------------- Fig 8: division maps, crew vs model against the earlier measured height
fig, axs = plt.subplots(1, 3, figsize=(16, 4.9))
dmap(axs[0], "crew_vs_earlier_pct", DIV, n5, "a  Crew height vs earlier measured (%)", minn=100, ncol="n_anchor"); cbar(fig, axs[0], DIV, n5, "Mean crew / earlier - 1 (%)", "both")
dmap(axs[1], "model_vs_earlier_pct", DIV, n5, "b  Model height vs earlier measured (%)", minn=100, ncol="n_anchor"); cbar(fig, axs[1], DIV, n5, "Mean model / earlier - 1 (%)", "both")
T8["rmse_ratio"] = T8.model_rmse / T8.crew_rmse; n6 = colors.Normalize(1.0, 2.0)
dmap(axs[2], "rmse_ratio", SEQ, n6, "c  Model error / crew error (RMSE ratio)", minn=100, ncol="n_anchor"); cbar(fig, axs[2], SEQ, n6, "Values above 1: crew closer to the earlier measurement", "max")
axs[0].text(0.0, -0.08, "Trees whose HT equals the earlier HT are excluded; grey = fewer than 100 such trees.", transform=axs[0].transAxes, fontsize=8.5, color=MUTE)
save(fig, "fig8_maps_anchor")

# ---------------------------------------------------------------- Fig 9: heatmap division x diameter class
M = T11.pivot(index="division", columns="dclass", values="excess_pct").reindex(columns=LAB)
ordr = T8.set_index("division").n_htcd2.reindex(M.index).sort_values(ascending=False).index; M = M.loc[ordr]
nm = T8.set_index("division").division_name
fig, ax = plt.subplots(figsize=(7.6, 0.33 * len(M) + 1.6))
im = ax.imshow(M.values, cmap=DIV, norm=colors.Normalize(-10, 10), aspect="auto")
for i in range(M.shape[0]):
    for j in range(M.shape[1]):
        v = M.values[i, j]
        if np.isfinite(v): ax.text(j, i, "0" if abs(v) < 0.5 else f"{v:+.0f}", ha="center", va="center", fontsize=8, color=INK)
ax.set_xticks(range(len(LAB)), LAB); ax.set_yticks(range(len(M)), [f"{d} {nm[d]}" for d in M.index]); ax.set_xlabel("Diameter class (in)")
ax.set_title("Excess bias of HTCD 2 by ecodivision and size (%)", pad=8); ax.tick_params(length=0)
for s in ax.spines.values(): s.set_visible(False)
cb = fig.colorbar(im, ax=ax, shrink=0.5, pad=0.02, extend="both"); cb.set_label("Percentage points", fontsize=9)
fig.text(0.01, -0.01, "Cells with fewer than 100 HTCD 2 or 100 control trees are blank. Divisions ordered by number of HTCD 2 trees.", fontsize=8.5, color=MUTE)
save(fig, "fig9_heatmap_division_dbh")

# ---------------------------------------------------------------- Fig 10: the regional models themselves (curves + data) for the four largest species x division groups
hm = pd.read_csv("../height_model_results.csv", low_memory=False); bd = hm[hm.scope == "B_division"]; best = bd.loc[bd.groupby("group_key").rmse.idxmin()].set_index("group_key")
sp = pd.read_csv(P + "ref_species.csv").drop_duplicates("spcd").set_index("spcd")
g = smp[smp.set == "htcd2"].groupby(["spcd", "division"]).size().sort_values(ascending=False).head(4)
fig, axs = plt.subplots(2, 4, figsize=(16, 8.2), sharex="col", sharey="col")
for j, ((s, dv), n) in enumerate(g.items()):
    key = f"{int(s)}|{dv}"; c = smp[(smp.spcd == s) & (smp.division == dv)]; r = best.loc[key]
    xs = np.linspace(1, min(60, c.dia.max()), 200)
    yh = 4.5 + r.b0 * np.exp(-r.b1 * xs ** (-r.b2)) if r.model_form == "curtis_arney" else 4.5 + np.exp(r.b0 + r.b1 / (xs + 1))
    for i, (nm, col, lab) in enumerate((("control", GREY, "Intact measured (HTCD 1, unseen plots; sample)"), ("htcd2", BLUE, "Crew-reconstructed (HTCD 2)"))):
        ax = axs[i, j]; z = c[c.set == nm]
        ax.scatter(z.dia, z.ht, s=4, color=col, alpha=0.3, linewidths=0, rasterized=True); ax.plot(xs, yh, color=ORANGE, lw=2.2)
        ax.grid(color=GRID, lw=0.6); ax.set_axisbelow(True); ax.text(0.03, 0.96, f"n = {len(z):,}", transform=ax.transAxes, va="top", fontsize=9, color=MUTE)
    axs[0, j].set_title(f"{sp.common_name.get(int(s), int(s))} in {dv}  (held-out RMSE {r.rmse:.1f} ft)", pad=4, fontsize=10.5); axs[1, j].set_xlabel("DBH (in)")
axs[0, 0].set_ylabel("Total height (ft): intact measured"); axs[1, 0].set_ylabel("Total height (ft): crew-reconstructed")
fig.legend(handles=[Patch(color=GREY, label="Intact measured (HTCD 1, unseen plots, sample)"), Patch(color=BLUE, label="Crew-reconstructed (HTCD 2)"), Patch(color=ORANGE, label="Regional species x ecodivision model (fitted on HTCD 1 training plots)")], loc="lower center", ncol=3, fontsize=10, labelcolor=INK, bbox_to_anchor=(0.5, -0.04))
save(fig, "fig10_regional_model_curves")

# ---------------------------------------------------------------- Fig 11: inventory of regional models (table image as bar chart)
I = INV.merge(T8[["division", "n_ctl", "ctl_rmse_ft", "ctl_bias_pct"]], on="division", how="left").sort_values("n_train_trees", ascending=True)
fig, (a, b) = plt.subplots(1, 2, figsize=(12, 0.3 * len(I) + 1.8), sharey=True)
y = np.arange(len(I)); a.barh(y, I.n_train_trees, color=BLUE, height=0.65); a.set_xscale("log"); a.set_yticks(y, [f"{r.division} {r.division_name}" for r in I.itertuples()])
a.set_xlabel("Training trees (HTCD 1, log scale)"); a.set_title("Regional models: training data", pad=6)
for i, r in enumerate(I.itertuples()): a.text(r.n_train_trees * 1.15, i, f"{r.n_species_models} species model" + ("" if r.n_species_models == 1 else "s"), va="center", fontsize=8.5, color=MUTE)
a.set_xlim(right=I.n_train_trees.max() * 12)
b.barh(y, I.heldout_rmse_ft, color=ORANGE, height=0.65); b.set_xlabel("Held-out RMSE (ft), pooled over species models"); b.set_title("Regional models: accuracy on unseen plots", pad=6)
for a_ in (a, b): a_.grid(axis="x", color=GRID, lw=0.6); a_.set_axisbelow(True)
save(fig, "fig11_regional_model_inventory")
print("done")
