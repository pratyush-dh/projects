#!/usr/bin/env python3
"""HTCD 4 side project, step 1: FIA's own modeled heights (HTCD 4, "estimated with a model") vs a regional height-diameter
model trained only on field-measured (HTCD 1) trees, applied to the same trees.

old_ht = the height stored in FIADB for HTCD 4 trees (FIA's own, undocumented, imputation).
new_ht = our species x ecodivision Curtis-Arney/Wykoff model, fitted only on HTCD 1 trees of the 80% TRAINING plots
         (see paper/fit_height_models.py); these are current-evaluation trees, not necessarily on held-out plots, so this
         is a comparison of two IMPUTATION METHODS on trees whose true height is unknown to either -- not a validation
         against ground truth. For that, this script also folds in two things that already have ground truth:
  (a) side_htcd2/out/t8_division.csv: the SAME regional model's own bias/RMSE on intact MEASURED trees on plots it never
      saw, division by division -- the benchmark for "how good is this model here anyway".
  (b) paper/out/heldout_check.csv (t11b rows): the held-out check from the main study, which pretends measured trees on
      current-evaluation plots in CA+OR+WA (99.4% of all HTCD 4 trees) are unmeasured and imputes them -- the closest
      thing to an accuracy number for the region where nearly all HTCD 4 trees live.
Outputs: out/summary.json, out/t1_by_dbh.csv, out/t2_by_division.csv, out/t3_by_state.csv, out/t4_by_species.csv,
         out/resid_sample.pkl, figures/fig1-5 (PNG + PDF).
"""
import json
import numpy as np, pandas as pd

rng = np.random.default_rng(3); B = 500
d = pd.read_csv("../paper/data/targets_current.csv", low_memory=False)
h4 = d[d.old_htcd == 4.0].copy()
sp = pd.read_csv("../paper/data/ref_species.csv").drop_duplicates("spcd").set_index("spcd")
h4["common"] = h4.spcd.map(sp.common_name).fillna(h4.spcd.astype(str))
h4["lr"] = np.log(h4.old_ht / h4.new_ht); h4["r"] = h4.old_ht - h4.new_ht
BINS = [1, 5, 10, 15, 20, 30, 61]; LAB = ["1-4.9", "5-9.9", "10-14.9", "15-19.9", "20-29.9", "30+"]
h4["dclass"] = pd.cut(h4.dia, BINS, labels=LAB, right=False)
S = {"n": len(h4), "n_states": int(h4.statecd.nunique()), "n_divisions": int(h4.division.nunique()),
     "share_species_division_tier": float((h4.model_tier == "species_division").mean()),
     "old_ht": h4.old_ht.describe().round(1).to_dict(), "new_ht": h4.new_ht.describe().round(1).to_dict(),
     "n_old_gt_200": int((h4.old_ht > 200).sum()), "n_new_gt_200": int((h4.new_ht > 200).sum())}


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


# ---------------------------------------------------------------- overall + by DBH class
tot, m, ci = cluster_mean(h4, "dclass", ["lr", "r"])
T1 = pd.DataFrame({"dbh_class": LAB, "n": tot.astype(int), "bias_pct": 100 * (np.exp(m["lr"]) - 1),
                   "bias_pct_lo": 100 * (np.exp(ci["lr"][0]) - 1), "bias_pct_hi": 100 * (np.exp(ci["lr"][1]) - 1),
                   "bias_ft": m["r"], "bias_ft_lo": ci["r"][0], "bias_ft_hi": ci["r"][1]})
T1.to_csv("out/t1_by_dbh.csv", index=False)
allrow = h4.assign(one=pd.Categorical(np.zeros(len(h4), int)))
tot0, m0, ci0 = cluster_mean(allrow, "one", ["lr", "r"])
S["overall"] = dict(bias_pct=float(100 * (np.exp(m0["lr"][0]) - 1)), ci_pct=[float(100 * (np.exp(ci0["lr"][0][0]) - 1)), float(100 * (np.exp(ci0["lr"][1][0]) - 1))],
                    bias_ft=float(m0["r"][0]), sd_lr=float(h4.lr.std()))
# CA/OR/WA hold 99.3% of all HTCD 4 trees; the remaining trees are scattered singles/dozens across 13 other states and
# are not a representative sample of anything -- report them separately, never on a map.
core = h4.statecd.isin([6, 41, 53])
S["core3_n"] = int(core.sum()); S["core3_share"] = float(core.mean())
S["core3_bias_pct"] = float(100 * (np.exp(h4[core].lr.mean()) - 1))
S["other_states_n"] = int((~core).sum()); S["other_states_bias_pct"] = float(100 * (np.exp(h4[~core].lr.mean()) - 1))

# ---------------------------------------------------------------- by division (merge with the model's own benchmark bias)
tot, m, ci = cluster_mean(h4, "division", ["lr", "r"])
divs = pd.Categorical(h4.division).categories
T2 = pd.DataFrame({"division": divs, "n": tot.astype(int), "htcd4_bias_pct": 100 * (np.exp(m["lr"]) - 1),
                   "lo": 100 * (np.exp(ci["lr"][0]) - 1), "hi": 100 * (np.exp(ci["lr"][1]) - 1)})
t8 = pd.read_csv("../side_htcd2/out/t8_division.csv", dtype={"division": str})[["division", "division_name", "ctl_bias_pct", "ctl_rmse_ft", "n_ctl"]]
T2 = T2.merge(t8, on="division", how="left")
T2["excess_pct"] = T2.htcd4_bias_pct - T2.ctl_bias_pct
T2["significant"] = (T2.lo - T2.ctl_bias_pct > 0) | (T2.hi - T2.ctl_bias_pct < 0)
T2 = T2.sort_values("n", ascending=False)
T2.to_csv("out/t2_by_division.csv", index=False)
S["n_divisions_significant"] = int(T2[T2.n >= 200].significant.sum()); S["n_divisions_tested"] = int((T2.n >= 200).sum())

# ---------------------------------------------------------------- by state
tot, m, ci = cluster_mean(h4, "statecd", ["lr", "r"])
sts = pd.Categorical(h4.statecd).categories
T3 = pd.DataFrame({"statecd": sts, "n": tot.astype(int), "bias_pct": 100 * (np.exp(m["lr"]) - 1),
                   "lo": 100 * (np.exp(ci["lr"][0]) - 1), "hi": 100 * (np.exp(ci["lr"][1]) - 1)}).sort_values("n", ascending=False)
T3.to_csv("out/t3_by_state.csv", index=False)

# ---------------------------------------------------------------- by species (top 12)
top_sp = h4.common.value_counts().head(12).index
rows = []
for c in top_sp:
    z = h4[h4.common == c]
    rows.append(dict(species=c, n=len(z), bias_pct=100 * (np.exp(z.lr.mean()) - 1), mean_old_ft=z.old_ht.mean(), mean_new_ft=z.new_ht.mean()))
T4 = pd.DataFrame(rows); T4.to_csv("out/t4_by_species.csv", index=False)

# ---------------------------------------------------------------- the ground-truth pieces (a)+(b), copied in for the write-up
ho = pd.read_csv("../paper/out/heldout_check.csv")
row = ho[(ho.set == "held-out plots") & (ho.quantity == "biomass") & (ho.accounting == "ratio")]
S["heldout_by_model"] = row[["model", "bias_pct", "lo", "hi"]].round(3).to_dict("records")

h4.to_pickle("out/resid_sample.pkl")
json.dump(S, open("out/summary.json", "w"), indent=1, default=float)
pd.set_option("display.width", 250)
print(json.dumps({k: S[k] for k in S if k not in ("old_ht", "new_ht")}, indent=1, default=float))
print(T1.round(2).to_string())
print(T2[T2.n >= 100].round(2).to_string())
print(T4.round(1).to_string())
