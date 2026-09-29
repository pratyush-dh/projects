#!/usr/bin/env python3
"""Side project, step 1: live trees with HTCD 1/2/3 and their ACTUALHT straight from the SQLite export (read-only).
-> data/trees_htcd123.csv"""
import sqlite3, csv, os, time
os.makedirs("data", exist_ok=True)
c = sqlite3.connect("file:../SQLite_FIADB_ENTIRE/SQLite_FIADB_ENTIRE.db?mode=ro", uri=True)
q = """SELECT CN, PLT_CN, STATECD, INVYR, SUBP, TREE, SPCD, DIA, HT, ACTUALHT, HTCD, DIAHTCD, TREECLCD, CR, CULL, DAMLOC1, DAMTYP1, TPA_UNADJ, PREV_TRE_CN
       FROM TREE WHERE STATUSCD = 1 AND HTCD IN (1, 2, 3)"""
t0 = time.time(); n = 0
with open("data/trees_htcd123.csv", "w", newline="") as f:
    w = csv.writer(f); cur = c.execute(q); w.writerow([d[0].lower() for d in cur.description])
    while True:
        rows = cur.fetchmany(500000)
        if not rows: break
        w.writerows(rows); n += len(rows); print(n, round(time.time() - t0), "s", flush=True)
print("done", n)
