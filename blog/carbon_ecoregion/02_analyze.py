#!/usr/bin/env python3
"""Carbon-by-ecoregion, step 2: is live-tree carbon density (tons C/acre) different across Cleland ecodivisions, and
is that difference statistically defensible given (a) the FIA sample design and (b) the fact that per-plot carbon
density is strongly right-skewed and heteroscedastic across regions?

Unit of analysis: one FORESTED plot = one observation (carbon_tons_acre > 0 on each state's latest EXPCURR
evaluation; AK/HI/territories excluded, no ecodivision assigned). Divisions below MIN_N are summarized but excluded
from the significance tests (unstable with few plots). Plots are treated as the sampling units -- FIA's base grid is
an equal-probability systematic sample, so an unweighted per-division mean is a valid estimate of that division's
mean plot-level density; EXPNS (used to scale to population *totals*) is not needed for a density comparison, but a
weighted-mean sensitivity check is included since strata are not sampled at exactly equal rates everywhere.

Tests, in order of how much they're trusted here:
  1. Levene's (Brown-Forsythe, median-centered) test of equal variances -- almost certainly rejected; motivates 2-3.
  2. Welch's one-way ANOVA (does not assume equal variances) -- primary omnibus test.
  3. Kruskal-Wallis (rank-based, no distributional assumption at all) -- robustness check on the omnibus result.
  4. Classic (Fisher) one-way ANOVA -- reported for completeness/comparability, not trusted alone given 1.
  5. Post-hoc: Games-Howell (pairs with Welch's ANOVA, unequal-variance safe) and Dunn's test with Holm correction
     (pairs with Kruskal-Wallis, rank-based) -- both saved in full; a compact ranked plot carries the headline result.
  6. Same battery repeated on log1p(carbon density), since the raw scale is heavily right-skewed.
Outputs: out/t1_division_summary.csv, out/anova_results.json, out/pairwise_gameshowell.csv, out/pairwise_dunn.csv,
         out/pairwise_gameshowell_log.csv, figures/fig1-3.
"""
import json
import numpy as np, pandas as pd, geopandas as gpd
from scipy import stats
import pingouin as pg
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

MIN_N = 100
rng = np.random.default_rng(42)

BLUE, ORANGE, RED, GREY, INK, MUTE, GRID = "#2a78d6", "#eb6834", "#e34948", "#8a8a86", "#0b0b0b", "#52514e", "#e6e5e1"
plt.rcParams.update({"font.family": "Arial", "font.size": 10, "axes.labelsize": 10, "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlelocation": "left",
                     "text.color": INK, "axes.labelcolor": MUTE, "xtick.color": MUTE, "ytick.color": MUTE, "axes.edgecolor": "#b9b8b2", "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.7, "axes.axisbelow": True, "figure.facecolor": "white",
                     "pdf.fonttype": 42, "savefig.dpi": 200, "figure.constrained_layout.use": True, "legend.frameon": False})


def save(fig, n):
    for ext in ("png", "pdf"):
        try: fig.savefig(f"figures/{n}.{ext}", bbox_inches="tight")
        except OSError: fig.savefig(f"figures/{n}_new.{ext}", bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------- load + join
pc = pd.read_csv("data/plot_carbon.csv", dtype={"plt_cn": "str"})
coords = pd.read_csv("../paper/data/plot_coords.csv", dtype={"plt_cn": "str"}, low_memory=False)
names = gpd.read_file("../paper/data/eco_divisions_5070.gpkg")[["division_code", "division_name", "domain_name"]].drop_duplicates("division_code")
d = pc.merge(coords[["plt_cn", "division"]], on="plt_cn", how="left")
d = d[d.division.notna() & (d.division != "Water")].copy()
print(f"{len(d):,} plots with an ecodivision ({(d.carbon_tons_acre > 0).sum():,} forested)")

forest = d[d.carbon_tons_acre > 0].copy()
forest["log_carbon"] = np.log1p(forest.carbon_tons_acre)
counts = forest.division.value_counts()
big = counts[counts >= MIN_N].index.tolist()
small = counts[counts < MIN_N].index.tolist()
print(f"{len(big)} divisions with >= {MIN_N} forested plots ({forest.division.isin(big).sum():,} plots); "
      f"{len(small)} smaller divisions set aside for the tests ({forest.division.isin(small).sum():,} plots): {small}")

# ---------------------------------------------------------------- descriptive table (all divisions, incl. small)
def wmean(g): return np.average(g.carbon_tons_acre, weights=g.expns)

desc = forest.groupby("division").apply(lambda g: pd.Series({
    "n": len(g), "mean": g.carbon_tons_acre.mean(), "median": g.carbon_tons_acre.median(), "sd": g.carbon_tons_acre.std(),
    "cv": g.carbon_tons_acre.std() / g.carbon_tons_acre.mean(), "skew": stats.skew(g.carbon_tons_acre),
    "p25": g.carbon_tons_acre.quantile(.25), "p75": g.carbon_tons_acre.quantile(.75),
    "weighted_mean": wmean(g), "se": g.carbon_tons_acre.std() / np.sqrt(len(g)),
}), include_groups=False).reset_index()
desc["ci_lo"] = desc["mean"] - 1.96 * desc.se; desc["ci_hi"] = desc["mean"] + 1.96 * desc.se
desc = desc.merge(names, left_on="division", right_on="division_code", how="left").drop(columns="division_code")
desc["included_in_tests"] = desc.division.isin(big)
desc["weighted_vs_unweighted_pct"] = 100 * (desc.weighted_mean / desc["mean"] - 1)
desc = desc.sort_values("mean", ascending=False)
desc.to_csv("out/t1_division_summary.csv", index=False)

grand_mean = forest.carbon_tons_acre.mean()
S = {"min_n": MIN_N, "n_divisions_total": int(forest.division.nunique()), "n_divisions_tested": len(big),
    "n_forested_plots": int(len(forest)), "n_forested_plots_tested": int(forest.division.isin(big).sum()),
    "grand_mean_tons_acre": float(grand_mean), "grand_median_tons_acre": float(forest.carbon_tons_acre.median()),
    "max_weighted_vs_unweighted_pct_gap": float(desc[desc.included_in_tests].weighted_vs_unweighted_pct.abs().max())}

groups = [forest[forest.division == dvn].carbon_tons_acre.values for dvn in big]
groups_log = [forest[forest.division == dvn].log_carbon.values for dvn in big]

# ---------------------------------------------------------------- 1. equal-variance check
lev = stats.levene(*groups, center="median")  # Brown-Forsythe
S["levene_brown_forsythe"] = {"stat": float(lev.statistic), "p": float(lev.pvalue)}

# ---------------------------------------------------------------- 2. Welch's ANOVA (primary)
wdf = forest[forest.division.isin(big)]
welch = pg.welch_anova(data=wdf, dv="carbon_tons_acre", between="division")
S["welch_anova"] = welch.round(6).to_dict("records")[0]
welch_log = pg.welch_anova(data=wdf, dv="log_carbon", between="division")
S["welch_anova_log1p"] = welch_log.round(6).to_dict("records")[0]

# ---------------------------------------------------------------- 3. Kruskal-Wallis (robustness)
kw = stats.kruskal(*groups)
n_tot = len(wdf); kw_eps2 = (kw.statistic - len(big) + 1) / (n_tot - len(big))  # epsilon-squared effect size
S["kruskal_wallis"] = {"H": float(kw.statistic), "df": len(big) - 1, "p": float(kw.pvalue), "epsilon_sq": float(kw_eps2)}

# ---------------------------------------------------------------- 4. classic ANOVA (for comparison only)
classic = stats.f_oneway(*groups)
ss_between = sum(len(g) * (g.mean() - wdf.carbon_tons_acre.mean()) ** 2 for g in groups)
ss_total = ((wdf.carbon_tons_acre - wdf.carbon_tons_acre.mean()) ** 2).sum()
eta2 = ss_between / ss_total
S["classic_anova"] = {"F": float(classic.statistic), "df_between": len(big) - 1, "df_within": n_tot - len(big),
                      "p": float(classic.pvalue), "eta_sq": float(eta2)}

# normality: Shapiro on a capped random subsample per division (full-n Shapiro is over-powered and scipy caps N)
shap = []
for dvn in big:
    v = forest.loc[forest.division == dvn, "carbon_tons_acre"].values
    samp = rng.choice(v, size=min(len(v), 2000), replace=False)
    sh = stats.shapiro(samp)
    shap.append({"division": dvn, "n_full": len(v), "n_sampled": len(samp), "shapiro_W": float(sh.statistic), "shapiro_p": float(sh.pvalue), "skew": float(stats.skew(v))})
shap = pd.DataFrame(shap)
S["normality"] = {"divisions_failing_shapiro_p01": int((shap.shapiro_p < 0.01).sum()), "of": len(shap), "median_skew": float(shap["skew"].median())}
shap.to_csv("out/t2_normality_by_division.csv", index=False)

# ---------------------------------------------------------------- post-hoc: Games-Howell (raw + log) and Dunn (rank, Holm)
gh = pg.pairwise_gameshowell(data=wdf, dv="carbon_tons_acre", between="division")
gh.to_csv("out/pairwise_gameshowell.csv", index=False)
gh_log = pg.pairwise_gameshowell(data=wdf, dv="log_carbon", between="division")
gh_log.to_csv("out/pairwise_gameshowell_log.csv", index=False)


def dunn_holm(groups, labels):
    """Dunn's test (rank-based, pairs with Kruskal-Wallis) with Holm step-down correction across all pairs."""
    all_v = np.concatenate(groups); ranks = stats.rankdata(all_v)
    sizes = [len(g) for g in groups]; idx = np.cumsum([0] + sizes)
    rbar = [ranks[idx[i]:idx[i + 1]].mean() for i in range(len(groups))]
    N = len(all_v)
    # tie correction term for the KW statistic's variance
    _, counts = np.unique(all_v, return_counts=True)
    tie_corr = 1 - (counts ** 3 - counts).sum() / (N ** 3 - N)
    rows = []
    for i in range(len(groups)):
        for j in range(i + 1, len(groups)):
            se = np.sqrt(tie_corr * N * (N + 1) / 12 * (1 / sizes[i] + 1 / sizes[j]))
            z = (rbar[i] - rbar[j]) / se
            p = 2 * (1 - stats.norm.cdf(abs(z)))
            rows.append({"A": labels[i], "B": labels[j], "z": z, "p_raw": p})
    df = pd.DataFrame(rows).sort_values("p_raw")
    m = len(df)
    ordered_p = df.p_raw.values
    adj = np.empty(m); running_max = 0.0
    for k in range(m):
        val = (m - k) * ordered_p[k]
        running_max = max(running_max, val)
        adj[k] = min(running_max, 1.0)
    df["p_holm"] = adj
    return df.sort_values(["A", "B"]).reset_index(drop=True)


dunn = dunn_holm(groups, big)
dunn.to_csv("out/pairwise_dunn_holm.csv", index=False)
S["pairwise"] = {"n_pairs": len(dunn), "n_sig_gameshowell_p05": int((gh.pval < 0.05).sum()),
                 "n_sig_dunn_holm_p05": int((dunn.p_holm < 0.05).sum())}

json.dump(S, open("out/anova_results.json", "w"), indent=1, default=float)
pd.set_option("display.width", 220, "display.max_rows", 50)
print(json.dumps({k: S[k] for k in S if k not in ("normality",)}, indent=1, default=float))
print(desc[["division", "division_name", "n", "mean", "median", "sd", "cv", "weighted_mean", "included_in_tests"]].round(2).to_string())

# ---------------------------------------------------------------- Fig 1: distribution by division (violin, Tukey-fence trimmed)
order = desc[desc.included_in_tests].sort_values("n", ascending=True).division.tolist()
fig, ax = plt.subplots(figsize=(14, 6.5))
pos = np.arange(len(order))
dvn = desc.set_index("division")
data_trim, tops = [], []
for dv in order:
    vals = forest.loc[forest.division == dv, "carbon_tons_acre"].values
    q1, q3 = np.percentile(vals, [25, 75]); iqr = q3 - q1
    lo, hi = max(0, q1 - 1.5 * iqr), q3 + 1.5 * iqr
    trimmed = vals[(vals >= lo) & (vals <= hi)]
    data_trim.append(trimmed); tops.append(trimmed.max())

vp = ax.violinplot(data_trim, positions=pos, vert=True, widths=0.75, showmedians=True, showextrema=True)
for body in vp["bodies"]:
    body.set_facecolor(BLUE); body.set_edgecolor(BLUE); body.set_alpha(0.7); body.set_linewidth(0.6)
for key in ("cmaxes", "cmins", "cbars"):
    vp[key].set_color(BLUE); vp[key].set_linewidth(1.0)
vp["cmedians"].set_color("white"); vp["cmedians"].set_linewidth(1.8)
ax.axhline(grand_mean, color=INK, lw=1.0, ls=(0, (5, 3)))
for i, dv in enumerate(order):
    n = int(dvn.loc[dv, "n"])
    ax.text(pos[i], tops[i] + 2.5, f"n={n:,}", rotation=90, ha="center", va="bottom", fontsize=6.5, color=MUTE)
ax.set_xticks(pos, order, fontsize=7.5, rotation=90)
ax.set_ylabel("Live-tree carbon density, forested plots (tons C / acre)"); ax.set_ylim(0, 245)
ax.set_title("Carbon density by ecodivision, ranked by sample size (violin: distribution, line: median; outliers beyond Tukey fences not shown)", pad=8)
ax.text(0.98, 0.97, f"Dashed line: grand mean ({grand_mean:.1f} tons/acre)", transform=ax.transAxes, ha="right", fontsize=9, color=MUTE)
save(fig, "fig1_boxplot_by_division")

# ---------------------------------------------------------------- Table 2 (replaces the old Fig 2 plot): ranked mean +/- 95% CI
desc_t = desc[desc.included_in_tests].sort_values("mean", ascending=False).reset_index(drop=True)
with open("out/t2_ranked_means_ci.md", "w", encoding="utf-8") as f:
    f.write("| Division | Name | n plots | Mean (tons C/acre) | 95% CI |\n|---|---|---|---|---|\n")
    for r in desc_t.itertuples():
        f.write(f"| {r.division} | {r.division_name} | {r.n:,.0f} | {r.mean:.1f} | {r.ci_lo:.1f}–{r.ci_hi:.1f} |\n")
desc_t.to_csv("out/t2_ranked_means_ci.csv", index=False)
print(f"wrote out/t2_ranked_means_ci.md ({len(desc_t)} rows)")

# ---------------------------------------------------------------- Fig 5: CV by division, x-axis sorted by n ascending
cv_vals = np.array([dvn.loc[dv, "cv"] for dv in order])
fig, ax = plt.subplots(figsize=(14, 6))
ax.scatter(pos, cv_vals, color=BLUE, s=36, alpha=0.9, edgecolor="white", linewidth=0.6, zorder=3)
ax.set_xticks(pos, order, fontsize=7.5, rotation=90)
ax.set_xlabel("Ecodivision (sorted by number of forested plots, ascending)")
ax.set_ylabel("Coefficient of variation (sd / mean)")
ax.set_title("Coefficient of variation of carbon density by ecodivision, sorted by sample size", pad=8)
save(fig, "fig5_variance_by_division")

# ---------------------------------------------------------------- Fig 6: CV vs. number of plots, with trend (does CV fall as n grows?)
n_vals = np.array([dvn.loc[dv, "n"] for dv in order])
log_n = np.log(n_vals)
r_pearson, p_pearson = stats.pearsonr(log_n, cv_vals)
slope, intercept = np.polyfit(log_n, cv_vals, 1)
fig, ax = plt.subplots(figsize=(9, 7))
ax.scatter(n_vals, cv_vals, color=BLUE, s=36, alpha=0.9, edgecolor="white", linewidth=0.6, zorder=3)
for dv, xn, yv in zip(order, n_vals, cv_vals):
    ax.annotate(dv, (xn, yv), xytext=(4, 3), textcoords="offset points", fontsize=6.5, color=MUTE)
xx = np.linspace(log_n.min(), log_n.max(), 100)
ax.plot(np.exp(xx), slope * xx + intercept, color=RED, lw=1.4, ls=(0, (5, 3)), zorder=2)
ax.set_xscale("log")
ax.set_xlabel("Number of forested plots (n), log scale")
ax.set_ylabel("Coefficient of variation (sd / mean)")
ax.set_title("Coefficient of variation vs. number of plots, by ecodivision", pad=8)
ax.text(0.98, 0.97, f"Pearson r = {r_pearson:.2f} (log n vs. CV), p = {p_pearson:.3f}\nfitted line: OLS of CV on log(n)",
        transform=ax.transAxes, ha="right", va="top", fontsize=8.5, color=MUTE)
save(fig, "fig6_cv_vs_nplots")
print(f"CV vs log(n): Pearson r={r_pearson:.3f}, p={p_pearson:.4f}")

# ---------------------------------------------------------------- Fig 7: CV at the ecodivision level vs. the state level
# Same forested-plot pool (`forest`), regrouped by STATECD instead of division -- FIA's sample design targets
# state/national estimates, so this checks whether ecodivision-level CV is high mainly because ecodivisions cut
# across that design, by comparing it to CV computed the way the survey *was* designed to support.
state_desc = forest.groupby("statecd").apply(lambda g: pd.Series({
    "n": len(g), "mean": g.carbon_tons_acre.mean(), "sd": g.carbon_tons_acre.std(),
    "cv": g.carbon_tons_acre.std() / g.carbon_tons_acre.mean(),
}), include_groups=False).reset_index()
state_names = gpd.read_file("../paper/data/states-10m.json", layer="states")[["id", "name"]]
state_names["statecd"] = state_names.id.astype(int)
state_desc = state_desc.merge(state_names[["statecd", "name"]], on="statecd", how="left")
state_big = state_desc[state_desc.n >= MIN_N].copy()
print(f"{len(state_big)} states with >= {MIN_N} forested plots (of {len(state_desc)} total)")

div_cv = desc[desc.included_in_tests].cv.values
st_cv = state_big.cv.values
mw_u, mw_p = stats.mannwhitneyu(div_cv, st_cv, alternative="two-sided")
print(f"Ecodivision CV: median={np.median(div_cv):.3f}, n={len(div_cv)}; State CV: median={np.median(st_cv):.3f}, "
      f"n={len(st_cv)}; Mann-Whitney p={mw_p:.4f}")

fig, ax = plt.subplots(figsize=(6.5, 6.5))
groups = [div_cv, st_cv]
bx = ax.boxplot(groups, positions=[0, 1], widths=0.45, patch_artist=True, showfliers=False,
                boxprops=dict(facecolor=BLUE, edgecolor=BLUE, alpha=0.3), medianprops=dict(color=BLUE, linewidth=1.8),
                whiskerprops=dict(color=BLUE), capprops=dict(color=BLUE))
for i, g in enumerate(groups):
    jitter = rng.uniform(-0.12, 0.12, size=len(g))
    ax.scatter(np.full(len(g), i) + jitter, g, color=BLUE, s=18, alpha=0.6, edgecolor="white", linewidth=0.4, zorder=3)
ax.set_xticks([0, 1], [f"Ecodivision\n(n={len(div_cv)} divisions)", f"State\n(n={len(st_cv)} states)"])
ax.set_ylabel("Coefficient of variation (sd / mean)")
ax.set_title("Carbon-density CV: ecodivision level vs. state level", pad=8)
ax.text(0.98, 0.02, f"Mann-Whitney p = {mw_p:.3f}\nmedians: {np.median(div_cv):.2f} vs. {np.median(st_cv):.2f}",
        transform=ax.transAxes, ha="right", va="bottom", fontsize=8.5, color=MUTE)
save(fig, "fig7_cv_division_vs_state")
state_desc.to_csv("out/t3_state_cv.csv", index=False)

# ---------------------------------------------------------------- Fig 3: map
st_ll = gpd.read_file("../paper/data/states-10m.json", layer="states").set_crs(4326)
st_conus = st_ll[(st_ll.id.astype(int) <= 56) & (~st_ll.id.astype(int).isin([2, 15]))].to_crs(5070)
XMIN, YMIN, XMAX, YMAX = st_conus.total_bounds
div_poly = gpd.read_file("../paper/data/eco_divisions_5070.gpkg").rename(columns={"division_code": "division"})
div_poly = div_poly[div_poly.division != "Water"].merge(desc, on="division", how="left")
fig, ax = plt.subplots(figsize=(9, 6))
from matplotlib.colors import LinearSegmentedColormap
SEQ = LinearSegmentedColormap.from_list("seq_green", ["#eef6ee", "#1baf7a", "#0a4d36"])
import matplotlib.colors as mcolors
norm = mcolors.Normalize(0, 60)
ok = div_poly["mean"].notna() & div_poly.included_in_tests
div_poly[~ok].plot(ax=ax, color="#e4e3df", edgecolor="none", zorder=1)
div_poly[ok].plot(column="mean", cmap=SEQ, norm=norm, ax=ax, edgecolor="none", zorder=1)
st_conus.boundary.plot(ax=ax, color="0.75", linewidth=0.4, zorder=2)
div_poly.dissolve(by="division", as_index=False).plot(ax=ax, facecolor="none", edgecolor="0.2", linewidth=0.8, zorder=3)
import matplotlib.patheffects as pe
lbl = div_poly.dissolve(by="division", as_index=False)
for r in lbl.itertuples():
    rep = r.geometry.representative_point()
    ax.annotate(r.division, xy=(rep.x, rep.y), fontsize=5, ha="center", va="center", color="#1a1a1a", zorder=4,
                path_effects=[pe.withStroke(linewidth=1.6, foreground="white")])
ax.set_axis_off(); ax.set_aspect("equal"); ax.set_xlim(XMIN - 5e4, XMAX + 5e4); ax.set_ylim(YMIN - 5e4, YMAX + 5e4)
ax.set_title("Mean live-tree carbon density by ecodivision", pad=8)
cb = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=SEQ), ax=ax, orientation="horizontal", shrink=0.55, pad=0.01, aspect=30, extend="max")
cb.set_label("Tons C / acre (forested plots)", fontsize=9)
save(fig, "fig3_map_mean_carbon")
print("done")
