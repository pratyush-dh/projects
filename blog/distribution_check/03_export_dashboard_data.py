#!/usr/bin/env python3
"""Distribution check, step 3: export histogram bin data + summary stats as JSON for the interactive dashboard.
Mirrors the exact binning used in 02_analyze.py's fig1-fig4 so the dashboard matches the static figures.
-> out/dashboard_data.json
"""
import json
import numpy as np, pandas as pd
from scipy import stats

d = pd.read_csv("data/tree_measurements.csv", low_memory=False)
print(f"{len(d):,} live trees")

VARS = [
    ("dia", "Diameter at breast height", "inches", "DIA"),
    ("ht", "Total height", "feet", "HT"),
    ("biomass_lbs", "Aboveground + belowground dry biomass", "pounds", "Biomass"),
    ("volcfnet_cuft", "Net merchantable volume", "cubic feet", "Volume"),
]


def hist_series(v, w, bins):
    counts, edges = np.histogram(v, bins=bins, weights=w)
    centers = (edges[:-1] + edges[1:]) / 2
    return {"edges": edges.tolist(), "centers": centers.tolist(), "counts": counts.tolist()}


out = {"n_trees": int(len(d)), "n_plots": int(d.plt_cn.nunique()), "variables": {}}

for col, label, unit, short in VARS:
    v_all = d[col].dropna()
    hi = v_all.quantile(.995)
    v_trim = v_all[v_all <= hi]
    v_pos = v_all[v_all > 0]
    log_bins = np.logspace(np.log10(max(v_pos.min(), 1e-2)), np.log10(v_pos.max()), 61)

    sub = d[[col, "tpa_adj"]].dropna()
    sub = sub[sub.tpa_adj > 0]
    vw, w = sub[col], sub.tpa_adj
    wmed = (lambda vv, ww: np.interp(0.5, (np.cumsum(ww.values[np.argsort(vv.values)]) - 0.5 *
            ww.values[np.argsort(vv.values)]) / ww.sum(), vv.values[np.argsort(vv.values)]))(vw, w)
    wmean = float(np.average(vw, weights=w))
    hi_w = vw.quantile(.995)
    m_trim = vw <= hi_w
    vw_pos = vw[vw > 0]
    log_bins_w = np.logspace(np.log10(vw_pos.min()), np.log10(vw_pos.max()), 61)

    out["variables"][short] = {
        "label": label, "unit": unit,
        "stats": {
            "n": int(len(v_all)), "n_missing": int(d[col].isna().sum()),
            "mean": float(v_all.mean()), "median": float(v_all.median()), "sd": float(v_all.std()),
            "skew": float(stats.skew(v_all)),
            "p5": float(v_all.quantile(.05)), "p95": float(v_all.quantile(.95)),
            "weighted_mean": wmean, "weighted_median": float(wmed),
        },
        "raw_linear": hist_series(v_trim, None, 60),
        "raw_log": hist_series(v_pos, None, log_bins),
        "weighted_linear": hist_series(vw[m_trim], w[m_trim], 60),
        "weighted_log": hist_series(vw_pos, w.loc[vw_pos.index], log_bins_w),
    }
    print(short, "done")

json.dump(out, open("out/dashboard_data.json", "w"), indent=0)
print("wrote out/dashboard_data.json,", len(json.dumps(out)), "bytes")
