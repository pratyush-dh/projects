#!/usr/bin/env python3
"""Side project, step 2: attach ecodivision, genus, the model-predicted intact height HT_hat and - where it exists - the tree's
PREVIOUS measured height (PREV_TRE_CN) to the extracted trees.

Model = the production regional height model of the main study (species x ecodivision Curtis-Arney/Wykoff, fallback species -> genus -> all),
fitted ONLY on HTCD = 1 trees of the 80 % TRAINING plots.  Therefore:
  * HTCD 2 / 3 trees were never in the training data (any plot);
  * the HTCD 1 control set is restricted to the 20 % TEST plots, which the models never saw.
-> data/analysis_trees.pkl
"""
import sys, time
import numpy as np, pandas as pd
sys.path.insert(0, "..")
from recompute_volume_biomass import load_best_coeffs, assign_models, predict_new_height

t0 = time.time()
DT = {"cn": "Int64", "prev_tre_cn": "Int64", "plt_cn": "int64"}
plots = np.load("../paper/data/npy/plots.npy"); test = set(plots[np.load("../paper/data/npy/is_test_plot.npy")].tolist())
pc = pd.read_csv("../paper/data/plot_coords.csv", usecols=["plt_cn", "division"], dtype={"plt_cn": "int64", "division": "str"}).drop_duplicates("plt_cn").set_index("plt_cn").division
genus = pd.read_csv("../paper/data/ref_species.csv").drop_duplicates("spcd").set_index("spcd").genus

keep, need = [], []
for ch in pd.read_csv("data/trees_htcd123.csv", chunksize=1_000_000, low_memory=False, dtype=DT):
    ch["test_plot"] = ch.plt_cn.isin(test)
    ch = ch[(ch.htcd != 1) | ch.test_plot]  # HTCD 1 only as an out-of-sample control
    keep.append(ch); need.append(ch.prev_tre_cn.dropna().astype("int64"))
d = pd.concat(keep, ignore_index=True); need = set(pd.concat(need).tolist())
print("kept", len(d), "need prev for", len(need), round(time.time() - t0), "s", flush=True)

# previous record of the same tree (only when it was itself a live HTCD 1/2/3 tally tree)
prev = []
for ch in pd.read_csv("data/trees_htcd123.csv", chunksize=1_000_000, low_memory=False, dtype=DT,
                      usecols=["cn", "invyr", "dia", "ht", "actualht", "htcd"]):
    prev.append(ch[ch.cn.isin(need)])
prev = pd.concat(prev).rename(columns=lambda c: "p_" + c if c != "cn" else "prev_tre_cn").drop_duplicates("prev_tre_cn")
d = d.merge(prev, on="prev_tre_cn", how="left")
n0 = d.htcd.value_counts().to_dict()
d["division"] = d.plt_cn.map(pc)
d["genus"] = d.spcd.map(genus)
d = d[d.division.notna() & d.dia.between(1, 60) & d.ht.between(4.5, 250)].copy()  # same screens as the training data
print("after screens", d.htcd.value_counts().to_dict(), "from", n0, "| with previous record:", int(d.p_ht.notna().sum()), flush=True)
coeffs = load_best_coeffs("../height_model_results.csv")
d = assign_models(d, coeffs)
d["hat"] = predict_new_height(d)
d = d.drop(columns=["b0", "b1", "b2"])
d.to_pickle("data/analysis_trees.pkl")
print(d.model_tier.value_counts().to_dict(), round(time.time() - t0), "s")
