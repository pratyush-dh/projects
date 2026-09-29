#!/usr/bin/env python3
"""HTCD 4 side project, step 3: pull every live HTCD 4 tree's PREVIOUS record (PREV_TRE_CN) straight from the SQLite
export (read-only), to build an independent anchor test: for HTCD 4 trees whose earlier record was itself a genuine
field measurement (HTCD 1), compare FIA's stored HTCD 4 height and our regional-model height against that earlier
measured height, grown forward. side_htcd2/data/trees_htcd123.csv already has every live HTCD 1/2/3 tree (with
PREV_TRE_CN), so it is reused here as the lookup table for the earlier record; only the HTCD 4 side needs a fresh pull.
-> data/htcd4_trees.csv
"""
import sqlite3, csv, os, time
os.makedirs("data", exist_ok=True)
c = sqlite3.connect("file:../SQLite_FIADB_ENTIRE/SQLite_FIADB_ENTIRE.db?mode=ro", uri=True)
q = """SELECT CN, PLT_CN, STATECD, INVYR, SUBP, TREE, SPCD, DIA, HT, ACTUALHT, HTCD, TPA_UNADJ, PREV_TRE_CN
       FROM TREE WHERE STATUSCD = 1 AND HTCD = 4"""
t0 = time.time(); n = 0
with open("data/htcd4_trees.csv", "w", newline="") as f:
    w = csv.writer(f); cur = c.execute(q); w.writerow([d[0].lower() for d in cur.description])
    while True:
        rows = cur.fetchmany(200000)
        if not rows: break
        w.writerows(rows); n += len(rows); print(n, round(time.time() - t0), "s", flush=True)
print("done", n)
