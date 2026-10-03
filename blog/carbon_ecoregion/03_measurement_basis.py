#!/usr/bin/env python3
"""Carbon-by-ecoregion, step 3: design-weighted share of each division's live-tree carbon that rests on a field-measured height
(HTCD 1) vs. a crew reconstruction (HTCD 2/3) or FIA's own model (HTCD 4) -- the connector to the first two posts
in this series. Reuses the same plot set and per-tree weighting as 01_extract.py, adding HTCD.
-> out/t3_carbon_by_htcd_division.csv
"""
import time
import numpy as np, pandas as pd, geopandas as gpd

t0 = time.time()
def log(m): print(f"[{time.time()-t0:6.0f}s] {m}", flush=True)

psa = pd.read_csv("data/latest_evalid.csv")
latest_evalids = set(psa.EVALID.tolist())

import sqlite3
c = sqlite3.connect("file:../SQLite_FIADB_ENTIRE/SQLite_FIADB_ENTIRE.db?mode=ro", uri=True)
ppsa = pd.read_sql("SELECT CN, STRATUM_CN, PLT_CN, STATECD, EVALID FROM POP_PLOT_STRATUM_ASSGN WHERE EVALID IN (%s)" %
                   ",".join(map(str, latest_evalids)), c)
ps = pd.read_sql("SELECT CN AS STRATUM_CN2, EXPNS, ADJ_FACTOR_SUBP, ADJ_FACTOR_MICR FROM POP_STRATUM", c)
ppsa = ppsa.merge(ps, left_on="STRATUM_CN", right_on="STRATUM_CN2", how="left").drop_duplicates("PLT_CN")
pmap = ppsa.set_index("PLT_CN")[["ADJ_FACTOR_SUBP", "ADJ_FACTOR_MICR", "EXPNS"]]
plots = set(ppsa.PLT_CN.tolist())
log(f"{len(plots):,} plots on the latest evaluations")

log("live trees with HTCD ...")
q = "SELECT PLT_CN, DIA, HTCD, CARBON_AG, CARBON_BG, TPA_UNADJ FROM TREE WHERE STATUSCD = 1"
keep = []
for ch in pd.read_sql(q, c, chunksize=1_000_000):
    ch = ch[ch.PLT_CN.isin(plots)]; keep.append(ch)
tree = pd.concat(keep, ignore_index=True)
log(f"{len(tree):,} live trees")

tree = tree.join(pmap, on="PLT_CN")
tree["adj"] = np.where(tree.DIA < 5, tree.ADJ_FACTOR_MICR, tree.ADJ_FACTOR_SUBP)
tree["wa"] = tree.TPA_UNADJ.fillna(0) * tree.adj.fillna(0)
tree["carbon_w"] = (tree.CARBON_AG.fillna(0) + tree.CARBON_BG.fillna(0)) * tree.wa * tree.EXPNS
tree["measured"] = np.where(tree.HTCD == 1, "measured (HTCD 1)", np.where(tree.HTCD.isin([2, 3]), "crew estimate (HTCD 2/3)",
                                                                          np.where(tree.HTCD == 4, "FIA modeled (HTCD 4)", "missing/other")))

coords = pd.read_csv("../paper/data/plot_coords.csv", dtype={"plt_cn": "str"}, low_memory=False)
tree["PLT_CN"] = tree.PLT_CN.astype(str)
tree = tree.merge(coords[["plt_cn", "division"]], left_on="PLT_CN", right_on="plt_cn", how="left")
tree = tree[tree.division.notna() & (tree.division != "Water")]

piv = tree.pivot_table(index="division", columns="measured", values="carbon_w", aggfunc="sum", fill_value=0)
piv["total"] = piv.sum(axis=1)
for col in ["measured (HTCD 1)", "crew estimate (HTCD 2/3)", "FIA modeled (HTCD 4)", "missing/other"]:
    if col not in piv.columns: piv[col] = 0.0
    piv[col.split(" (")[0] + "_pct"] = 100 * piv[col] / piv.total
piv = piv.reset_index().sort_values("FIA modeled_pct", ascending=False)

names = gpd.read_file("../paper/data/eco_divisions_5070.gpkg")[["division_code", "division_name"]].drop_duplicates("division_code")
piv = piv.merge(names, left_on="division", right_on="division_code", how="left").drop(columns="division_code")
piv.to_csv("out/t3_carbon_by_htcd_division.csv", index=False)
pd.set_option("display.width", 200)
print(piv[["division", "division_name", "measured_pct", "crew estimate_pct", "FIA modeled_pct"]].round(2).to_string())
log("done")
