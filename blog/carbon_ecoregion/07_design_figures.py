#!/usr/bin/env python3
"""Carbon-by-ecoregion, step 7: figure for the design-weighted spread (sd/mean) at ecodivision vs. state level.
Single hue (the two groups are labeled on the axis, so no categorical legend or palette is needed).
Reads out/d4_spread_by_level.csv (written by 05_design_estimates.py).
-> figures/fig8_design_spread_state_vs_division.png/.pdf
"""
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats

BLUE, INK, MUTE, GRID = "#2a78d6", "#0b0b0b", "#52514e", "#e6e5e1"
plt.rcParams.update({"font.family": "Arial", "font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.7, "axes.axisbelow": True,
                     "pdf.fonttype": 42, "savefig.dpi": 200, "axes.labelcolor": MUTE, "xtick.color": MUTE,
                     "ytick.color": MUTE, "text.color": INK})

d4 = pd.read_csv("out/d4_spread_by_level.csv")
st = d4[d4.level == "state"].wcv.values
dv = d4[d4.level == "division"].wcv.values
u, p = stats.mannwhitneyu(dv, st, alternative="two-sided")
rng = np.random.default_rng(42)

fig, ax = plt.subplots(figsize=(6.2, 6.2))
groups = [dv, st]
ax.boxplot(groups, positions=[0, 1], widths=0.45, patch_artist=True, showfliers=False,
           boxprops=dict(facecolor=BLUE, edgecolor=BLUE, alpha=0.3), medianprops=dict(color=BLUE, linewidth=1.8),
           whiskerprops=dict(color=BLUE), capprops=dict(color=BLUE))
for i, g in enumerate(groups):
    ax.scatter(np.full(len(g), i) + rng.uniform(-0.12, 0.12, len(g)), g, color=BLUE, s=18, alpha=0.6,
               edgecolor="white", linewidth=0.4, zorder=3)
ax.set_xticks([0, 1], [f"Ecodivision\n(n={len(dv)})", f"State\n(n={len(st)})"])
ax.set_ylabel("Design-weighted coefficient of variation (sd / mean)")
ax.set_title("Carbon-density spread by level, FIA post-stratification weights", pad=8, loc="left",
             fontweight="bold")
ax.text(0.98, 0.98, f"Mann-Whitney p = {p:.3f}\nmedians: {np.median(dv):.2f} vs. {np.median(st):.2f}",
        transform=ax.transAxes, ha="right", va="top", fontsize=8.5, color=MUTE)
for ext in ("png", "pdf"):
    fig.savefig(f"figures/fig8_design_spread_state_vs_division.{ext}", bbox_inches="tight")
print(f"div n={len(dv)} median={np.median(dv):.3f}; state n={len(st)} median={np.median(st):.3f}; p={p:.4f}")
