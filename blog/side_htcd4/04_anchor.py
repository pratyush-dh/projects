#!/usr/bin/env python3
"""HTCD 4 side project, step 4: the anchor test. For the current-evaluation HTCD 4 trees (same 190,356 trees as
01_compare.py), keep those whose PREV_TRE_CN points to a tree that was itself field-measured (HTCD 1) and intact at
the earlier visit. Grow that earlier measured height forward (median growth rate from HTCD1-to-HTCD1 remeasurement
pairs within CA/OR/WA, by diameter class -- Pacific Coast growth, not the national rate used in side_htcd2) to get an
independent "truth" this population's own history, never used to fit either height. Compare FIA's stored HTCD 4
height and our regional model against that truth.
Outputs: out/summary_anchor.json, out/t5_anchor_by_dbh.csv, figures/fig6_anchor_test.
"""
import json
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BLUE, ORANGE, GREY, INK, MUTE, GRID = "#2a78d6", "#eb6834", "#8a8a86", "#0b0b0b", "#52514e", "#e6e5e1"
plt.rcParams.update({"font.family": "Arial", "font.size": 10, "axes.labelsize": 10, "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlelocation": "left",
                     "text.color": INK, "axes.labelcolor": MUTE, "xtick.color": MUTE, "ytick.color": MUTE, "axes.edgecolor": "#b9b8b2", "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.7, "axes.axisbelow": True, "figure.facecolor": "white",
                     "pdf.fonttype": 42, "savefig.dpi": 200, "figure.constrained_layout.use": True, "legend.frameon": False})
rng = np.random.default_rng(9); B = 500

h4c = pd.read_pickle("out/resid_sample.pkl")  # the 190,356 current-eval HTCD4 trees, with new_ht already predicted
h4x = pd.read_csv("data/htcd4_trees.csv", dtype={"cn": "int64", "prev_tre_cn": "Int64", "plt_cn": "int64"}, low_memory=False)
h4x = h4x[h4x.cn.isin(h4c.tree_cn)][["cn", "invyr", "prev_tre_cn"]].rename(columns={"cn": "tree_cn"})
h4 = h4c.merge(h4x, on="tree_cn", how="left")
print("current-eval HTCD4 trees:", len(h4), "with a PREV_TRE_CN:", h4.prev_tre_cn.notna().sum())

meas = pd.read_csv("../side_htcd2/data/trees_htcd123.csv", dtype={"cn": "int64", "prev_tre_cn": "Int64", "plt_cn": "int64"}, low_memory=False,
                   usecols=["cn", "plt_cn", "statecd", "invyr", "dia", "ht", "actualht", "htcd", "prev_tre_cn"])
prev = meas.rename(columns=lambda c: "p_" + c if c != "cn" else "prev_tre_cn").drop_duplicates("prev_tre_cn")
h4 = h4.merge(prev, on="prev_tre_cn", how="left")
h4 = h4[(h4.p_htcd == 1) & (h4.p_actualht.isna() | (h4.p_actualht == h4.p_ht)) & h4.p_ht.notna()].copy()
h4["dt"] = h4.invyr - h4.p_invyr
h4 = h4[h4.dt.between(1, 12) & (h4.p_ht >= 4.5)]
print("with a measured, intact earlier record and dt in range:", len(h4))
BINS = [1, 5, 10, 15, 20, 30, 61]; LAB = ["1-4.9", "5-9.9", "10-14.9", "15-19.9", "20-29.9", "30+"]
h4["dclass"] = pd.cut(h4.dia, BINS, labels=LAB, right=False)

# Pacific Coast growth rate: HTCD1-to-HTCD1 remeasurement pairs within CA/OR/WA (not the national rate from side_htcd2)
pc = meas[meas.statecd.isin([6, 41, 53]) & (meas.htcd == 1) & (meas.actualht.isna() | (meas.actualht == meas.ht))].copy()
pcp = pc.rename(columns=lambda c: "p_" + c if c != "cn" else "prev_tre_cn").drop_duplicates("prev_tre_cn")
gpairs = pc.merge(pcp[["prev_tre_cn", "p_dia", "p_ht", "p_invyr"]], on="prev_tre_cn", how="inner")
gpairs["dt"] = gpairs.invyr - gpairs.p_invyr; gpairs = gpairs[gpairs.dt.between(1, 12) & (gpairs.p_ht >= 4.5)]
gpairs["dclass"] = pd.cut(gpairs.dia, BINS, labels=LAB, right=False)
gr = (np.log(gpairs.ht / gpairs.p_ht) / gpairs.dt).groupby(gpairs.dclass, observed=True).median()
print("Pacific Coast growth rate (ln/yr) by class, n =", len(gpairs)); print(gr)

h4["truth"] = h4.p_ht * np.exp(h4.dclass.map(gr).astype(float) * h4.dt)
h4["e_fia"] = h4.old_ht - h4.truth; h4["e_mod"] = h4.new_ht - h4.truth
h4["same"] = h4.old_ht == h4.p_ht


def cluster_mean(x, key, vals):
    codes = pd.Categorical(x[key]).codes; p = pd.factorize(x.plt_cn)[0]; k = codes.max() + 1
    n = np.zeros((p.max() + 1, k)); s = {v: np.zeros_like(n) for v in vals}
    ok = codes >= 0; np.add.at(n, (p[ok], codes[ok]), 1)
    for v in vals: np.add.at(s[v], (p[ok], codes[ok]), x[v].values[ok])
    tot = n.sum(0); out = {v: s[v].sum(0) / tot for v in vals}; R = {v: np.empty((B, k)) for v in vals}
    for b in range(B):
        w = np.bincount(rng.integers(0, len(n), len(n)), minlength=len(n)).astype(float); den = w @ n
        for v in vals: R[v][b] = (w @ s[v]) / den
    return tot, out, {v: (np.percentile(R[v], 2.5, axis=0), np.percentile(R[v], 97.5, axis=0)) for v in vals}


tot, m, ci = cluster_mean(h4, "dclass", ["e_fia", "e_mod"])
T5 = pd.DataFrame({"dbh_class": LAB, "n": tot.astype(int), "fia_error_ft": m["e_fia"], "fia_lo": ci["e_fia"][0], "fia_hi": ci["e_fia"][1],
                   "model_error_ft": m["e_mod"], "model_lo": ci["e_mod"][0], "model_hi": ci["e_mod"][1]})
T5["fia_rmse"] = [np.sqrt((h4[h4.dclass == c].e_fia ** 2).mean()) for c in LAB]
T5["model_rmse"] = [np.sqrt((h4[h4.dclass == c].e_mod ** 2).mean()) for c in LAB]
T5.to_csv("out/t5_anchor_by_dbh.csv", index=False)
allrow = h4.assign(one=pd.Categorical(np.zeros(len(h4), int)))
tot0, m0, ci0 = cluster_mean(allrow, "one", ["e_fia", "e_mod"])
S = dict(n_pairs=len(h4), n_pairs_noncopied=int((~h4.same).sum()), copied_share=float(h4.same.mean()),
        fia_bias_ft=float(m0["e_fia"][0]), fia_ci_ft=[float(ci0["e_fia"][0][0]), float(ci0["e_fia"][1][0])], fia_rmse_ft=float(np.sqrt((h4.e_fia ** 2).mean())),
        model_bias_ft=float(m0["e_mod"][0]), model_ci_ft=[float(ci0["e_mod"][0][0]), float(ci0["e_mod"][1][0])], model_rmse_ft=float(np.sqrt((h4.e_mod ** 2).mean())),
        fia_closer_share=float((h4.e_fia.abs() < h4.e_mod.abs()).mean()), growth_rate_ln_per_yr=gr.round(4).to_dict(), n_growth_pairs=len(gpairs))
h4nc = h4[~h4.same]
S["noncopied"] = dict(fia_bias_ft=float(h4nc.e_fia.mean()), fia_rmse_ft=float(np.sqrt((h4nc.e_fia ** 2).mean())),
                      model_bias_ft=float(h4nc.e_mod.mean()), model_rmse_ft=float(np.sqrt((h4nc.e_mod ** 2).mean())),
                      fia_closer_share=float((h4nc.e_fia.abs() < h4nc.e_mod.abs()).mean()))
json.dump(S, open("out/summary_anchor.json", "w"), indent=1, default=float)
pd.set_option("display.width", 200); print(json.dumps(S, indent=1, default=float)); print(T5.round(2).to_string())

# ---------------------------------------------------------------- figure
fig, axs = plt.subplots(1, 2, figsize=(11.5, 4.6))
x = np.arange(len(T5))
a = axs[0]; a.axhline(0, color=INK, lw=0.9)
a.errorbar(x - 0.08, T5.fia_error_ft, yerr=[T5.fia_error_ft - T5.fia_lo, T5.fia_hi - T5.fia_error_ft], fmt="o-", color=BLUE, lw=1.8, ms=6, capsize=3, label="FIA modeled (HTCD 4)")
a.errorbar(x + 0.08, T5.model_error_ft, yerr=[T5.model_error_ft - T5.model_lo, T5.model_hi - T5.model_error_ft], fmt="o-", color=ORANGE, lw=1.8, ms=6, capsize=3, label="Our regional model")
a.set_xticks(x, LAB); a.set_xlabel("Diameter class (in)"); a.set_ylabel("Error vs the earlier measured height (ft)"); a.set_title("a  Bias against an independent anchor", pad=8); a.legend(loc="upper left", labelcolor=INK, fontsize=9)
b = axs[1]; w = 0.35
b.bar(x - w / 2, T5.fia_rmse, w, color=BLUE, label="FIA modeled (HTCD 4)"); b.bar(x + w / 2, T5.model_rmse, w, color=ORANGE, label="Our regional model")
b.set_xticks(x, LAB); b.set_xlabel("Diameter class (in)"); b.set_ylabel("RMSE vs the earlier measured height (ft)"); b.set_title("b  Typical error", pad=8); b.legend(loc="upper left", labelcolor=INK, fontsize=9)
fig.text(0.0, -0.02, f"Trees on current-evaluation plots in CA/OR/WA whose PREV_TRE_CN was itself measured and intact (n = {len(h4):,}; growth-adjusted using {len(gpairs):,} Pacific Coast remeasurement pairs).", fontsize=8.5, color=MUTE)
for ext in ("png", "pdf"):
    try: fig.savefig(f"figures/fig6_anchor_test.{ext}", bbox_inches="tight")
    except OSError: fig.savefig(f"figures/fig6_anchor_test_new.{ext}", bbox_inches="tight")
plt.close(fig)
print("done")
