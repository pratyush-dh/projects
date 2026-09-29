#!/usr/bin/env python3
"""Side project, step 6: regional (ecodivision and state) models, residuals and biases for HTCD 2 vs HTCD 1-derived model heights.

'Excess bias' = mean ln(HT/HT_hat) of HTCD 2 trees minus that of intact measured HTCD 1 trees (unseen plots) in the same region
(and DBH class where stated); it removes the model's own regional bias.  Intervals: plot-clustered bootstrap (B = 500).
Anchor comparison: HTCD 2 trees whose earlier measured intact height exists and whose HT differs from it (see 04_robustness.py).
Outputs: out/t8_division.csv, out/t9_state.csv, out/t10_model_inventory.csv, out/t11_division_by_dbh.csv, out/resid_samples.pkl
"""
import json
import numpy as np, pandas as pd

rng = np.random.default_rng(7)
B = 500
d = pd.read_pickle("data/analysis_trees.pkl")
d["lr"] = np.log(d.ht / d.hat); d["r"] = d.ht - d.hat
intact = d.actualht.isna() | (d.actualht == d.ht)
ctl = d[(d.htcd == 1) & intact].copy(); h2 = d[(d.htcd == 2) & (d.actualht < d.ht)].copy()
BINS = [1, 5, 10, 15, 20, 30, 61]; LAB = ["1-4.9", "5-9.9", "10-14.9", "15-19.9", "20-29.9", "30+"]
for x in (ctl, h2, d):
    x["dclass"] = pd.cut(x.dia, BINS, labels=LAB, right=False)
div_name = pd.read_csv("../paper/data/plot_coords.csv", nrows=0)  # placeholder to keep the import cheap
import geopandas as gpd
gd = gpd.read_file("../paper/data/eco_divisions_5070.gpkg")[["division_code", "division_name", "domain_name"]].drop_duplicates("division_code").set_index("division_code")


def sums(x, key, val):
    g = pd.Categorical(x[key], categories=KEYS[key]).codes
    p = pd.factorize(x.plt_cn)[0]; k = len(KEYS[key]); n = np.zeros((p.max() + 1, k)); s = np.zeros_like(n)
    ok = g >= 0; np.add.at(n, (p[ok], g[ok]), 1); np.add.at(s, (p[ok], g[ok]), x[val].values[ok])
    return n, s


def boot(x, key, val):
    n, s = sums(x, key, val); m = s.sum(0) / np.where(n.sum(0) > 0, n.sum(0), np.nan); R = np.empty((B, n.shape[1]))
    for b in range(B):
        w = np.bincount(rng.integers(0, len(n), len(n)), minlength=len(n)).astype(float); R[b] = (w @ s) / np.where(w @ n > 0, w @ n, np.nan)
    return m, R


KEYS = {"division": sorted(d.division.unique()), "statecd": sorted(d.statecd.unique())}


def regional(key):
    out = pd.DataFrame({key: KEYS[key]})
    for val, tag in (("lr", "lr"), ("r", "ft")):
        mc, rc = boot(ctl, key, val); mh, rh = boot(h2, key, val)
        dd = rh - rc
        out[f"ctl_mean_{tag}"] = mc; out[f"htcd2_mean_{tag}"] = mh; out[f"excess_{tag}"] = mh - mc
        out[f"excess_{tag}_lo"] = np.nanpercentile(dd, 2.5, axis=0); out[f"excess_{tag}_hi"] = np.nanpercentile(dd, 97.5, axis=0)
    g = lambda x: x.groupby(key, observed=True)
    out["n_ctl"] = out[key].map(g(ctl).size()).fillna(0).astype(int); out["n_htcd2"] = out[key].map(g(h2).size()).fillna(0).astype(int)
    out["ctl_sd_lr"] = out[key].map(g(ctl).lr.std()); out["htcd2_sd_lr"] = out[key].map(g(h2).lr.std())
    out["ctl_rmse_ft"] = out[key].map(g(ctl).r.apply(lambda v: np.sqrt((v ** 2).mean()))); out["htcd2_rmse_ft"] = out[key].map(g(h2).r.apply(lambda v: np.sqrt((v ** 2).mean())))
    out["excess_pct"] = 100 * (np.exp(out.excess_lr) - 1); out["excess_pct_lo"] = 100 * (np.exp(out.excess_lr_lo) - 1); out["excess_pct_hi"] = 100 * (np.exp(out.excess_lr_hi) - 1)
    out["ctl_bias_pct"] = 100 * (np.exp(out.ctl_mean_lr) - 1); out["htcd2_bias_pct"] = 100 * (np.exp(out.htcd2_mean_lr) - 1)
    out["significant"] = (out.excess_lr_lo > 0) | (out.excess_lr_hi < 0)
    out["share_model_below_actualht"] = out[key].map(g(h2).apply(lambda z: (z.hat < z.actualht).mean()))
    out["mean_break_ft"] = out[key].map(g(h2).apply(lambda z: (z.ht - z.actualht).mean()))
    out["share_speciesdivision_tier"] = out[key].map(g(h2).apply(lambda z: (z.model_tier == "species_division").mean()))
    return out


# --- anchor (earlier measured height) by region
def pairs(x):
    p = x[(x.p_htcd == 1) & (x.p_actualht.isna() | (x.p_actualht == x.p_ht)) & x.p_ht.notna()].copy(); p["dt"] = p.invyr - p.p_invyr
    return p[p.dt.between(1, 12) & (p.p_ht >= 4.5)]


pc_, ph = pairs(ctl), pairs(h2)
gr = (np.log(pc_.ht / pc_.p_ht) / pc_.dt).groupby(pc_.dclass, observed=True).median()
ph["truth"] = ph.p_ht * np.exp(ph.dclass.map(gr).astype(float) * ph.dt)
ph["same"] = ph.ht == ph.p_ht
ph["e_crew"] = np.log(ph.ht / ph.truth); ph["e_mod"] = np.log(ph.hat / ph.truth)
nc = ph[~ph.same]


def anchor(key):
    g = nc.groupby(key, observed=True)
    a = pd.DataFrame({"n_anchor": g.size(), "crew_vs_earlier_pct": 100 * (np.exp(g.e_crew.mean()) - 1), "model_vs_earlier_pct": 100 * (np.exp(g.e_mod.mean()) - 1),
                      "crew_rmse": g.e_crew.apply(lambda v: np.sqrt((v ** 2).mean())), "model_rmse": g.e_mod.apply(lambda v: np.sqrt((v ** 2).mean()))}).reset_index()
    cp = ph.groupby(key, observed=True).same.agg(["mean", "size"]).reset_index().rename(columns={"mean": "copied_share", "size": "n_pairs_all"})
    return a.merge(cp, on=key, how="outer")


for key, fn in (("division", "t8_division"), ("statecd", "t9_state")):
    T = regional(key).merge(anchor(key), on=key, how="left")
    if key == "division":
        T["division_name"] = T.division.map(gd.division_name); T["domain"] = T.division.map(gd.domain_name)
    T.to_csv(f"out/{fn}.csv", index=False)
    print(fn, len(T), "regions;", int(T.significant.sum()), "with significant excess bias")

# --- inventory of the regional models actually used
hm = pd.read_csv("../height_model_results.csv", low_memory=False)
bd = hm[hm.scope == "B_division"]; best = bd.loc[bd.groupby("group_key").rmse.idxmin()].copy()
best["division"] = best.group_key.str.split("|").str[1]
inv = best.groupby("division").agg(n_species_models=("group_key", "size"), n_train_trees=("n_train", "sum"), n_test_trees=("n_test", "sum"),
                                   share_curtis_arney=("model_form", lambda v: (v == "curtis_arney").mean()),
                                   heldout_rmse_ft=("rmse", lambda v: np.sqrt(np.average(v ** 2, weights=best.loc[v.index, "n_test"]))),
                                   heldout_bias_ft=("bias", lambda v: np.average(v, weights=best.loc[v.index, "n_test"]))).reset_index()
inv["division_name"] = inv.division.map(gd.division_name)
inv.to_csv("out/t10_model_inventory.csv", index=False)
# --- division x DBH class excess bias
rows = []
for dv in KEYS["division"]:
    for c in LAB:
        a, b = ctl[(ctl.division == dv) & (ctl.dclass == c)], h2[(h2.division == dv) & (h2.dclass == c)]
        if len(b) >= 100 and len(a) >= 100: rows.append(dict(division=dv, dclass=c, n_htcd2=len(b), n_ctl=len(a), excess_pct=100 * (np.exp(b.lr.mean() - a.lr.mean()) - 1)))
pd.DataFrame(rows).to_csv("out/t11_division_by_dbh.csv", index=False)
# --- residual samples for the box plots (avoid re-loading the 4 M-row table in the figure script)
keep = ["division", "statecd", "dclass", "lr", "r", "invyr", "spcd", "dia", "ht", "hat", "actualht", "htcd"]
smp = pd.concat([ctl.sample(600000, random_state=3)[keep].assign(set="control"), h2[keep].assign(set="htcd2")])
smp.to_pickle("out/resid_samples.pkl")
pd.set_option("display.width", 250, "display.max_columns", 30)
T = pd.read_csv("out/t8_division.csv")
print(T.sort_values("n_htcd2", ascending=False)[["division", "division_name", "n_htcd2", "n_ctl", "ctl_bias_pct", "htcd2_bias_pct", "excess_pct", "excess_pct_lo", "excess_pct_hi", "n_anchor", "crew_vs_earlier_pct", "model_vs_earlier_pct", "copied_share"]].round(2).head(25).to_string())
