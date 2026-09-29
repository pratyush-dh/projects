#!/usr/bin/env python3
"""Side project, step 5: three figures for the article (PNG 200 dpi + PDF).  Palette: blue = crew (HTCD 2), orange = model, grey = intact measured control.
Colour slots 1-2 of the validated reference palette (validate_palette.js: all checks pass); text is always ink, never the series colour."""
import json
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BLUE, ORANGE, GREY, INK, MUTE, GRID = "#2a78d6", "#eb6834", "#8a8a86", "#0b0b0b", "#52514e", "#e6e5e1"
plt.rcParams.update({"font.family": "Arial", "font.size": 11, "axes.labelsize": 11, "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlelocation": "left",
                     "text.color": INK, "axes.labelcolor": MUTE, "xtick.color": MUTE, "ytick.color": MUTE, "axes.edgecolor": "#b9b8b2", "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.7, "axes.axisbelow": True, "figure.facecolor": "white",
                     "pdf.fonttype": 42, "savefig.dpi": 200, "figure.constrained_layout.use": True, "legend.frameon": False})
S = json.load(open("out/summary.json")); R = json.load(open("out/summary_robust.json")); SIM = json.load(open("out/sim_coupling.json"))
T1 = pd.read_csv("out/t1_by_dbh_class.csv"); T2 = pd.read_csv("out/t2_severity_percentile.csv"); T7 = pd.read_csv("out/t7_anchor_robustness.csv")
pct = lambda lr: 100 * (np.exp(lr) - 1)

# ---------------------------------------------------------------- Figure 1: crew vs model, by DBH class and overall distribution
d = pd.read_pickle("data/analysis_trees.pkl", compression=None)
d["lr"] = np.log(d.ht / d.hat)
ctl = d[(d.htcd == 1) & (d.actualht.isna() | (d.actualht == d.ht))].lr.sample(400000, random_state=1)
h2 = d[(d.htcd == 2) & (d.actualht < d.ht)].lr
fig, (a, b) = plt.subplots(1, 2, figsize=(11, 4.6), gridspec_kw=dict(width_ratios=[1.05, 1]))
x = np.arange(len(T1))
a.axhline(0, color=INK, lw=0.8)
a.plot(x, pct(T1.mean_lr_control), "o-", color=GREY, ms=6, lw=1.6, zorder=3)
lo, hi = pct(T1.mean_lr_htcd2 - (T1.diff_lr - T1.diff_lo)), pct(T1.mean_lr_htcd2 + (T1.diff_hi - T1.diff_lr))   # 95% plot-clustered CI of the mean
a.vlines(x, lo, hi, color=BLUE, lw=2, zorder=3)
a.plot(x, pct(T1.mean_lr_htcd2), "o-", color=BLUE, ms=6, lw=1.6, zorder=4)
a.set_xticks(x, T1.dbh_class); a.set_xlabel("Diameter class (in)"); a.set_ylabel("Height relative to model prediction (%)")
a.set_title("Crews sit about 3% below the model", pad=8)
a.text(x[-1] + 0.12, pct(T1.mean_lr_htcd2.iloc[-1]), "Crew-reconstructed\n(HTCD 2)", color=INK, va="center", fontsize=10)
a.text(x[-1] + 0.12, pct(T1.mean_lr_control.iloc[-1]) + 0.3, "Measured, intact\n(HTCD 1, unseen plots)", color=INK, va="center", fontsize=10)
a.set_xlim(-0.3, x[-1] + 1.9)
edges = np.linspace(-1.0, 1.0, 81)
for arr, col, lab in ((ctl, GREY, None), (h2, BLUE, None)):
    h, _ = np.histogram(arr, bins=edges, density=True)
    b.stairs(h, edges, color=col, lw=1.8)
b.axvline(0, color=INK, lw=0.8)
b.set_xlabel("ln(height / model prediction)"); b.set_ylabel("Density"); b.set_xlim(-1, 1)
b.set_title("...and the spread is as wide as the model's own error", pad=8)
b.text(0.62, 1.55, f"SD control {ctl.std():.2f}\nSD HTCD 2 {h2.std():.2f}", color=INK, fontsize=10)
b.text(-0.95, 1.9, "Grey: measured intact trees\nBlue: crew-reconstructed", color=MUTE, fontsize=10, va="top")
fig.savefig("figures/fig1_crew_vs_model.png"); fig.savefig("figures/fig1_crew_vs_model.pdf"); plt.close(fig)

# ---------------------------------------------------------------- Figure 2: the severity 'trend' is produced by model error alone
fig, ax = plt.subplots(figsize=(8.6, 5.0))
xc = np.arange(5, 100, 10)
ax.axhline(0, color=INK, lw=0.8)
ax.plot(xc, T2.control_mean_lr, "o-", color=GREY, ms=6, lw=1.6, label="Measured, intact trees (ranked on their own height)")
ax.plot(xc, T2.htcd2_mean_lr, "o-", color=BLUE, ms=6, lw=1.6, label="HTCD 2 (ranked on ACTUALHT)")
sim = SIM["crew_noise_0.0"]["ACTUALHT (rank)"]
ax.plot(np.arange(10, 100, 20), sim, "D", color=ORANGE, ms=8, mec="white", mew=1.2, zorder=5, label="Simulation: perfectly accurate crews, same model error")
ax.set_xlabel("Rank of the measured stem length (ACTUALHT) within its 2-inch diameter class (percentile)")
ax.set_ylabel("Mean ln(crew height / model height)")
ax.set_title("A severity trend appears even when the crew is perfect", pad=10)
ax.legend(loc="upper left", fontsize=10, labelcolor=INK)
fig.savefig("figures/fig2_severity_artefact.png"); fig.savefig("figures/fig2_severity_artefact.pdf"); plt.close(fig)

# ---------------------------------------------------------------- Figure 3: against the tree's EARLIER measured height
rows = T7[T7.subset.str.startswith("HTCD 2, HT != previous, DBH")].copy(); rows["cls"] = rows.subset.str.split("DBH ").str[1]
ref = T7[T7.subset.str.startswith("control")].iloc[0]; allrow = T7[T7.subset == "HTCD 2, HT != previous HT"].iloc[0]
fig, (a, b) = plt.subplots(1, 2, figsize=(11, 4.6), gridspec_kw=dict(width_ratios=[1.25, 1]))
x = np.arange(len(rows)); w = 0.36
a.bar(x - w / 2, 100 * rows.crew_rmse, w, color=BLUE, label="Crew-reconstructed height")
a.bar(x + w / 2, 100 * rows.model_rmse, w, color=ORANGE, label="Model height")
a.axhline(100 * ref.crew_rmse, color=INK, lw=1.2, ls=(0, (4, 3)))
a.annotate("Dashed line: a fresh field measurement vs\nits own earlier measurement (intact trees), 17%", xy=(0.2, 100 * ref.crew_rmse), xytext=(-0.45, 33.2), fontsize=9.5, color=INK, va="bottom",
           arrowprops=dict(arrowstyle="-", color=MUTE, lw=0.8))
a.set_xticks(x, rows.cls); a.set_xlabel("Diameter class (in)"); a.set_ylabel("Typical error vs earlier measured height (RMSE, %)")
a.set_title("Crews track the earlier measurement better", pad=8); a.legend(loc="upper right", fontsize=10, labelcolor=INK); a.set_ylim(0, 41)
eras = list(R["copied_share_by_era"].keys()); v = [100 * R["copied_share_by_era"][e] for e in eras]
b.bar(np.arange(len(eras)), v, 0.6, color=BLUE)
b.axhline(100 * R["copied_share_control"], color=GREY, lw=1.6); b.text(len(eras) - 0.35, 100 * R["copied_share_control"], "Measured trees\n(by chance): 8%", color=INK, fontsize=9.5, va="center")
for i, val in enumerate(v): b.text(i, val + 1.2, f"{val:.0f}%", ha="center", color=INK, fontsize=10)
b.set_xticks(np.arange(len(eras)), eras); b.set_xlabel("Inventory year"); b.set_ylabel("HTCD 2 trees whose HT equals the previous HT (%)"); b.set_ylim(0, 62); b.set_xlim(-0.5, len(eras) + 0.9)
b.set_title("But many crew values repeat the old one", pad=8)
fig.savefig("figures/fig3_anchor_test.png"); fig.savefig("figures/fig3_anchor_test.pdf"); plt.close(fig)
print("ok")
