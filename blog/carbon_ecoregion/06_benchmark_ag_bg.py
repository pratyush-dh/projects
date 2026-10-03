#!/usr/bin/env python3
"""Carbon-by-ecoregion, step 6: aboveground vs belowground split of the design-based national live-tree carbon total,
so the national figure can be compared like-for-like with published aboveground live-tree carbon. Same plot set,
weighting and stratum expansions as 01_extract.py / 05_design_estimates.py.
National total = sum over strata of EXPNS_h x sum of plot values (tons C, short tons), all latest evaluations.
-> out/d5_national_ag_bg.json
"""
import sqlite3, json
import numpy as np, pandas as pd

DB = "file:../SQLite_FIADB_ENTIRE/SQLite_FIADB_ENTIRE.db?mode=ro"
c = sqlite3.connect(DB, uri=True)

pe = pd.read_sql("SELECT CN, EVALID, STATECD, END_INVYR FROM POP_EVAL", c)
pet = pd.read_sql("SELECT EVAL_CN, EVAL_TYP FROM POP_EVAL_TYP WHERE EVAL_TYP = 'EXPCURR'", c)
cur = pe.merge(pet, left_on="CN", right_on="EVAL_CN")
latest_evalids = set(cur.sort_values(["STATECD", "END_INVYR"], ascending=[True, False])
                     .drop_duplicates("STATECD").EVALID.tolist())

psa = pd.read_sql("SELECT CN, STRATUM_CN, PLT_CN, STATECD, EVALID FROM POP_PLOT_STRATUM_ASSGN", c)
psa = psa[psa.EVALID.isin(latest_evalids)].drop_duplicates("PLT_CN")
ps = pd.read_sql("SELECT CN AS STRATUM_CN2, EXPNS, ADJ_FACTOR_SUBP, ADJ_FACTOR_MICR FROM POP_STRATUM", c)
psa = psa.merge(ps, left_on="STRATUM_CN", right_on="STRATUM_CN2", how="left")
plots = set(psa.PLT_CN.tolist())

keep = []
for ch in pd.read_sql("SELECT PLT_CN, DIA, CARBON_AG, CARBON_BG, TPA_UNADJ FROM TREE WHERE STATUSCD = 1", c,
                      chunksize=1_000_000):
    keep.append(ch[ch.PLT_CN.isin(plots)])
tree = pd.concat(keep, ignore_index=True)

pmap = psa.set_index("PLT_CN")[["ADJ_FACTOR_SUBP", "ADJ_FACTOR_MICR"]]
tree = tree.join(pmap, on="PLT_CN")
adj = np.where(tree.DIA < 5, tree.ADJ_FACTOR_MICR, tree.ADJ_FACTOR_SUBP)
wa = tree.TPA_UNADJ.fillna(0).values * np.nan_to_num(adj)
tree["ag_lbs"] = tree.CARBON_AG.fillna(0).values * wa
tree["bg_lbs"] = tree.CARBON_BG.fillna(0).values * wa
per = tree.groupby("PLT_CN")[["ag_lbs", "bg_lbs"]].sum() / 2000.0

psa = psa.set_index("PLT_CN").join(per, how="left").fillna({"ag_lbs": 0.0, "bg_lbs": 0.0})
ag_total = float((psa.EXPNS * psa.ag_lbs).sum())
bg_total = float((psa.EXPNS * psa.bg_lbs).sum())
out = dict(
    national_AG_MMT_C=ag_total / 1e6,
    national_BG_MMT_C=bg_total / 1e6,
    national_AG_plus_BG_MMT_C=(ag_total + bg_total) / 1e6,
    bg_share=bg_total / (ag_total + bg_total),
    n_plots=int(len(psa)),
)
json.dump(out, open("out/d5_national_ag_bg.json", "w"), indent=1)
print(json.dumps(out, indent=1))
