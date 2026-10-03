#!/usr/bin/env python3
"""Carbon-by-ecoregion, step 1: per-plot live-tree carbon density (tons C/acre) on each state's latest EXPCURR
evaluation, replicating the exact per-plot weighting convention used throughout this project
(paper/01_extract_aux.py: TPA_UNADJ * ADJ_FACTOR(micr if DIA<5 else subp), summed per plot), but for
CARBON_AG + CARBON_BG (live aboveground + belowground tree carbon, FIA's own NSVB-derived values) instead of
DRYBIO_AG. Read-only from the SQLite export; no PostgreSQL needed.
-> data/plot_carbon.csv (one row per current-evaluation plot: statecd, evalid, plt_cn, carbon_tons_acre, n_trees)
"""
import sqlite3, time
import numpy as np, pandas as pd

DB = "file:../SQLite_FIADB_ENTIRE/SQLite_FIADB_ENTIRE.db?mode=ro"
t0 = time.time()
def log(m): print(f"[{time.time()-t0:6.0f}s] {m}", flush=True)

c = sqlite3.connect(DB, uri=True)

log("latest EXPCURR evaluation per state ...")
pe = pd.read_sql("SELECT CN, EVALID, STATECD, END_INVYR FROM POP_EVAL", c)
pet = pd.read_sql("SELECT EVAL_CN, EVAL_TYP FROM POP_EVAL_TYP WHERE EVAL_TYP = 'EXPCURR'", c)
cur = pe.merge(pet, left_on="CN", right_on="EVAL_CN")
latest = cur.sort_values(["STATECD", "END_INVYR"], ascending=[True, False]).drop_duplicates("STATECD")
latest_evalids = set(latest.EVALID.tolist())
log(f"  {len(latest)} states/territories, {len(latest_evalids)} EVALIDs")
latest[["STATECD", "EVALID", "END_INVYR"]].to_csv("data/latest_evalid.csv", index=False)

log("plot-stratum assignment + stratum weights for those EVALIDs ...")
psa = pd.read_sql("SELECT CN, STRATUM_CN, PLT_CN, STATECD, EVALID, ESTN_UNIT, STRATUMCD FROM POP_PLOT_STRATUM_ASSGN", c)
psa = psa[psa.EVALID.isin(latest_evalids)].copy()
ps = pd.read_sql("SELECT CN AS STRATUM_CN2, EXPNS, P1POINTCNT, P2POINTCNT, ADJ_FACTOR_SUBP, ADJ_FACTOR_MICR FROM POP_STRATUM", c)
psa = psa.merge(ps, left_on="STRATUM_CN", right_on="STRATUM_CN2", how="left")
dup = psa.PLT_CN.duplicated().sum()
log(f"  {len(psa):,} plot-stratum rows; {dup} duplicate PLT_CN (should be 0 -- one stratum per plot per evalid)")
psa = psa.drop_duplicates("PLT_CN")  # safety net; latest-EXPCURR assigns each plot to exactly one stratum
plots = set(psa.PLT_CN.tolist())  # PLT_CN has TEXT affinity in this export (legacy small CNs exist); keep as read, no int cast

log("live trees (STATUSCD=1), reading in chunks and keeping only plots on the latest evaluations ...")
q = "SELECT PLT_CN, DIA, CARBON_AG, CARBON_BG, TPA_UNADJ FROM TREE WHERE STATUSCD = 1"
keep = []; n = 0
for ch in pd.read_sql(q, c, chunksize=1_000_000):
    ch = ch[ch.PLT_CN.isin(plots)]
    keep.append(ch); n += len(ch)
    log(f"  scanned chunk, kept {n:,} so far")
tree = pd.concat(keep, ignore_index=True)
log(f"  {len(tree):,} live trees on the plot set")

pmap = psa.set_index("PLT_CN")[["STATECD", "EVALID", "ESTN_UNIT", "STRATUMCD", "EXPNS", "ADJ_FACTOR_SUBP", "ADJ_FACTOR_MICR"]]
tree = tree.join(pmap, on="PLT_CN")
tree["adj"] = np.where(tree.DIA < 5, tree.ADJ_FACTOR_MICR, tree.ADJ_FACTOR_SUBP)
tree["wa"] = tree.TPA_UNADJ.fillna(0) * tree.adj.fillna(0)
tree["carbon_lbs"] = (tree.CARBON_AG.fillna(0) + tree.CARBON_BG.fillna(0)) * tree.wa

log("summing to per-plot carbon density ...")
per_plot = tree.groupby("PLT_CN").agg(
    statecd=("STATECD", "first"), evalid=("EVALID", "first"), estn_unit=("ESTN_UNIT", "first"),
    stratumcd=("STRATUMCD", "first"), expns=("EXPNS", "first"),
    carbon_lbs_acre=("carbon_lbs", "sum"), n_trees=("PLT_CN", "size")).reset_index()
per_plot = per_plot.rename(columns={"PLT_CN": "plt_cn"})
per_plot["carbon_tons_acre"] = per_plot.carbon_lbs_acre / 2000.0

# include every plot on the latest evaluation, even those with zero live-tree carbon (nonforest / no qualifying trees)
all_plots = psa.rename(columns={"PLT_CN": "plt_cn", "STATECD": "statecd", "EVALID": "evalid",
                                "ESTN_UNIT": "estn_unit", "STRATUMCD": "stratumcd", "EXPNS": "expns"})
out = all_plots[["plt_cn", "statecd", "evalid", "estn_unit", "stratumcd", "expns"]].merge(
    per_plot[["plt_cn", "carbon_tons_acre", "n_trees"]], on="plt_cn", how="left")
out["carbon_tons_acre"] = out.carbon_tons_acre.fillna(0.0); out["n_trees"] = out.n_trees.fillna(0).astype(int)
log(f"  {len(out):,} total plots ({(out.carbon_tons_acre > 0).sum():,} with nonzero live-tree carbon)")
out.to_csv("data/plot_carbon.csv", index=False)
log("done")
