#!/usr/bin/env python3
"""Distribution check, step 2: summary statistics and distribution figures for per-tree diameter, height,
biomass, and volume (live trees, latest evaluations -- see 01_extract.py for scope and known data quirks).

Raw tree counts (Fig 1, 2) answer "what did the sample look like"; they are not population-representative on
their own because FIA samples small trees (DIA < 5in) on a smaller-radius microplot and larger trees on the
full subplot, which mechanically distorts simple tree counts right at that 5in threshold (visible as a dip-then-
spike in the raw DIA histogram). Fig 3 weights each tree by tpa_adj (TPA_UNADJ x the microplot/subplot ADJ factor,
the standard FIA per-plot expansion used throughout this project) to show the size-class shape corrected for that
design effect -- this is a shape correction, not a population total (no acreage expansion applied).

Outputs: out/summary_stats.csv, out/weighted_summary_stats.csv,
         figures/fig1_distributions, fig2_log_distributions, fig3_tpa_weighted.png/.pdf
"""
import numpy as np, pandas as pd
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

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


d = pd.read_csv("data/tree_measurements.csv", low_memory=False)
print(f"{len(d):,} live trees total")

VARS = [
    ("dia", "Diameter at breast height (DIA)", "inches"),
    ("ht", "Total height (HT)", "feet"),
    ("biomass_lbs", "Aboveground + belowground dry biomass", "pounds"),
    ("volcfnet_cuft", "Net merchantable volume (VOLCFNET)", "cubic feet"),
]

# ---------------------------------------------------------------- summary statistics
rows = []
for col, label, unit in VARS:
    v = d[col].dropna()
    q = v.quantile([.01, .05, .25, .5, .75, .95, .99])
    rows.append(dict(
        variable=label, unit=unit, n=len(v), n_missing=d[col].isna().sum(),
        pct_missing=100 * d[col].isna().mean(), mean=v.mean(), sd=v.std(), skew=stats.skew(v),
        min=v.min(), p1=q[.01], p5=q[.05], p25=q[.25], median=q[.5], p75=q[.75], p95=q[.95], p99=q[.99], max=v.max(),
    ))
summary = pd.DataFrame(rows)
summary.to_csv("out/summary_stats.csv", index=False)
pd.set_option("display.width", 200)
print(summary.round(2).to_string(index=False))

neg_vol = (d.volcfnet_cuft < 0).sum()
print(f"negative VOLCFNET (defect-adjusted below zero, kept): {neg_vol:,} of {d.volcfnet_cuft.notna().sum():,} "
      f"({100 * neg_vol / d.volcfnet_cuft.notna().sum():.2f}%)")

# ---------------------------------------------------------------- Fig 1: linear-scale histograms, trimmed to p99.5
fig, axes = plt.subplots(2, 2, figsize=(11, 9), constrained_layout=True)
clip_hi = {"dia": d.dia.quantile(.995), "ht": d.ht.quantile(.995),
          "biomass_lbs": d.biomass_lbs.quantile(.995), "volcfnet_cuft": d.volcfnet_cuft.quantile(.995)}
for ax, (col, label, unit) in zip(axes.flat, VARS):
    v = d[col].dropna()
    v_plot = v[v <= clip_hi[col]]
    ax.hist(v_plot, bins=60, color=BLUE, alpha=0.85, edgecolor="white", linewidth=0.3)
    med, mean = v.median(), v.mean()
    ax.axvline(med, color=INK, lw=1.2, ls=(0, (4, 2)), label="Median")
    ax.axvline(mean, color=RED, lw=1.2, ls=(0, (1, 1)), label="Mean")
    ax.set_title(f"{label} ({unit})", pad=6)
    ax.set_ylabel("Number of trees")
    ax.text(0.98, 0.95, f"n = {len(v):,}\nmedian = {med:,.1f}\nmean = {mean:,.1f}\nskew = {stats.skew(v):.1f}",
            transform=ax.transAxes, ha="right", va="top", fontsize=8.5, color=MUTE)
axes.flat[0].legend(loc="upper left", bbox_to_anchor=(0.02, 0.98), frameon=False, fontsize=8.5)
fig.suptitle("Distribution of live-tree measurements (FIADB, latest evaluation per state), trimmed to the 99.5th percentile",
            ha="left", x=0.01, fontsize=11.5, fontweight="bold")
save(fig, "fig1_distributions")

# ---------------------------------------------------------------- Fig 2: log-scale histograms, full range
# VOLCFNET can in principle be negative (a documented defect/cull adjustment, see 01_extract.py); this run has none,
# so it is shown on the same log axis as the others. If a rerun has negative values, switch that panel to symlog.
has_neg_vol = (d.volcfnet_cuft < 0).any()
fig, axes = plt.subplots(2, 2, figsize=(11, 9), constrained_layout=True)
for ax, (col, label, unit) in zip(axes.flat, VARS):
    v = d[col].dropna()
    if col == "volcfnet_cuft" and has_neg_vol:
        ax.hist(v, bins=np.linspace(v.min(), v.quantile(.995), 60), color=BLUE, alpha=0.85,
                edgecolor="white", linewidth=0.3)
        ax.set_xscale("symlog", linthresh=1)
        ax.set_xlabel(f"{unit} (symlog scale; {( v < 0).sum():,} trees have negative volume)")
    else:
        v = v[v > 0]
        bins = np.logspace(np.log10(max(v.min(), 1e-2)), np.log10(v.max()), 60)
        ax.hist(v, bins=bins, color=BLUE, alpha=0.85, edgecolor="white", linewidth=0.3)
        ax.set_xscale("log")
        ax.set_xlabel(f"{unit} (log scale)")
    ax.set_title(label, pad=6)
    ax.set_ylabel("Number of trees")
fig.suptitle("Same distributions, full range (log x-axis)", ha="left", x=0.01, fontsize=11.5, fontweight="bold")
save(fig, "fig2_log_distributions")

# ---------------------------------------------------------------- Fig 3: TPA-weighted (design-effect corrected) shape
def weighted_quantile(v, w, q):
    order = np.argsort(v.values)
    v_s, w_s = v.values[order], w.values[order]
    cw = np.cumsum(w_s) - 0.5 * w_s
    return np.interp(q, cw / w_s.sum(), v_s)

wrows = []
fig, axes = plt.subplots(2, 2, figsize=(11, 9), constrained_layout=True)
for ax, (col, label, unit) in zip(axes.flat, VARS):
    sub = d[[col, "tpa_adj"]].dropna()
    sub = sub[sub.tpa_adj > 0]
    v, w = sub[col], sub.tpa_adj
    wmean = np.average(v, weights=w)
    wmed = weighted_quantile(v, w, 0.5)
    wrows.append(dict(variable=label, weighted_mean=wmean, weighted_median=wmed,
                      unweighted_mean=v.mean(), unweighted_median=v.median()))
    hi = v.quantile(.995)
    m = v <= hi
    ax.hist(v[m], bins=60, weights=w[m], color=BLUE, alpha=0.85, edgecolor="white", linewidth=0.3)
    ax.axvline(wmed, color=INK, lw=1.2, ls=(0, (4, 2)), label="Weighted median")
    ax.axvline(wmean, color=RED, lw=1.2, ls=(0, (1, 1)), label="Weighted mean")
    ax.set_title(f"{label} ({unit})", pad=6)
    ax.set_ylabel("Trees per acre (relative; shape only)")
    ax.text(0.98, 0.95, f"weighted median = {wmed:,.1f}\nweighted mean = {wmean:,.1f}\n"
            f"(unweighted: {v.median():,.1f} / {v.mean():,.1f})", transform=ax.transAxes, ha="right", va="top",
            fontsize=8.5, color=MUTE)
axes.flat[0].legend(loc="upper left", bbox_to_anchor=(0.02, 0.98), frameon=False, fontsize=8.5)
fig.suptitle("Same measurements, weighted by trees-per-acre (TPA x plot ADJ factor) -- corrects the microplot /\n"
            "subplot sampling-design artifact visible in Fig. 1's diameter panel; shape only, not a population total",
            ha="left", x=0.01, fontsize=11, fontweight="bold")
save(fig, "fig3_tpa_weighted")
pd.DataFrame(wrows).to_csv("out/weighted_summary_stats.csv", index=False)
print(pd.DataFrame(wrows).round(2).to_string(index=False))

# ---------------------------------------------------------------- Fig 4: TPA-weighted, log x-axis (biomass/volume legible)
fig, axes = plt.subplots(2, 2, figsize=(11, 9), constrained_layout=True)
for ax, (col, label, unit) in zip(axes.flat, VARS):
    sub = d[[col, "tpa_adj"]].dropna()
    sub = sub[(sub.tpa_adj > 0) & (sub[col] > 0)]
    v, w = sub[col], sub.tpa_adj
    bins = np.logspace(np.log10(v.min()), np.log10(v.max()), 60)
    ax.hist(v, bins=bins, weights=w, color=BLUE, alpha=0.85, edgecolor="white", linewidth=0.3)
    ax.set_xscale("log")
    ax.set_title(label, pad=6)
    ax.set_ylabel("Trees per acre (relative; shape only)")
    ax.set_xlabel(f"{unit} (log scale)")
fig.suptitle("TPA-weighted distributions, log x-axis (same weighting as Fig. 3, full range)",
            ha="left", x=0.01, fontsize=11.5, fontweight="bold")
save(fig, "fig4_tpa_weighted_log")
print("done")
