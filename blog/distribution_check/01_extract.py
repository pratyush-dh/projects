#!/usr/bin/env python3
"""Distribution check, step 1: per-tree diameter, height, biomass, and volume for live trees (STATUSCD = 1) on
each state's latest EXPCURR evaluation -- the same plot scope used throughout this project. Values are the raw
per-tree FIADB quantities (not expanded to per-acre density): DIA in inches, HT in feet, biomass in pounds
(DRYBIO_AG + DRYBIO_BG), VOLCFNET in cubic feet. Read-only from the SQLite export; no PostgreSQL needed.

Known data quirks handled here, not silently dropped:
  - HT has a small number of HT = 999 sentinel rows (documented project gotcha) -> set to NaN.
  - VOLCFNET can be negative for heavily defective trees (net of a cull/defect deduction) -- this is a real,
    documented FIADB value, kept as-is and flagged in the analysis step, not treated as an error.
-> data/tree_measurements.csv (plt_cn, statecd, spcd, dia, ht, htcd, biomass_lbs, volcfnet_cuft)
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

log("plot-stratum assignment and ADJ factors for those EVALIDs (for a TPA-weighted population view) ...")
psa = pd.read_sql("SELECT PLT_CN, STRATUM_CN, STATECD, EVALID FROM POP_PLOT_STRATUM_ASSGN", c)
psa = psa[psa.EVALID.isin(latest_evalids)].drop_duplicates("PLT_CN")
ps = pd.read_sql("SELECT CN AS STRATUM_CN2, ADJ_FACTOR_SUBP, ADJ_FACTOR_MICR FROM POP_STRATUM", c)
psa = psa.merge(ps, left_on="STRATUM_CN", right_on="STRATUM_CN2", how="left")
plots = set(psa.PLT_CN.tolist())
log(f"  {len(plots):,} plots on the latest evaluations")

log("live trees (STATUSCD = 1), reading in chunks and keeping only plots on the latest evaluations ...")
q = "SELECT PLT_CN, SPCD, DIA, HT, HTCD, DRYBIO_AG, DRYBIO_BG, VOLCFNET, TPA_UNADJ FROM TREE WHERE STATUSCD = 1"
keep = []; n = 0
for ch in pd.read_sql(q, c, chunksize=1_000_000):
    ch = ch[ch.PLT_CN.isin(plots)]
    keep.append(ch); n += len(ch)
    log(f"  scanned chunk, kept {n:,} so far")
tree = pd.concat(keep, ignore_index=True)
log(f"  {len(tree):,} live trees on the plot set")

tree = tree.merge(psa[["PLT_CN", "STATECD", "ADJ_FACTOR_SUBP", "ADJ_FACTOR_MICR"]], on="PLT_CN", how="left")
tree["HT"] = tree.HT.where(tree.HT != 999, np.nan)
tree["biomass_lbs"] = tree.DRYBIO_AG + tree.DRYBIO_BG  # NaN if either is missing
adj = np.where(tree.DIA < 5, tree.ADJ_FACTOR_MICR, tree.ADJ_FACTOR_SUBP)
tree["tpa_adj"] = tree.TPA_UNADJ.fillna(0) * np.nan_to_num(adj)  # trees per acre this sampled tree represents

out = tree.rename(columns={"PLT_CN": "plt_cn", "STATECD": "statecd", "SPCD": "spcd", "DIA": "dia", "HT": "ht",
                           "HTCD": "htcd", "VOLCFNET": "volcfnet_cuft"})[
    ["plt_cn", "statecd", "spcd", "dia", "ht", "htcd", "biomass_lbs", "volcfnet_cuft", "tpa_adj"]]
log(f"  non-null: dia={out.dia.notna().sum():,} ht={out.ht.notna().sum():,} "
    f"biomass={out.biomass_lbs.notna().sum():,} volume={out.volcfnet_cuft.notna().sum():,}")
log(f"  negative volcfnet: {(out.volcfnet_cuft < 0).sum():,}")
out.to_csv("data/tree_measurements.csv", index=False)
log("done")
