#!/usr/bin/env python3
"""Distribution check, step 4: flatten out/dashboard_data.json into row-based tables for the Dashboard artifact
(one summary row, one stats row per variable, one histogram row per variable x view x bin).
-> out/dash_summary.json, out/dash_stats.json, out/dash_histograms.json
"""
import json
import pandas as pd

raw = json.load(open("out/dashboard_data.json"))

summary = [{"n_trees": raw["n_trees"], "n_plots": raw["n_plots"]}]
json.dump(summary, open("out/dash_summary.json", "w"))

stats_rows = []
for short, v in raw["variables"].items():
    s = v["stats"]
    stats_rows.append({
        "variable": short, "label": v["label"], "unit": v["unit"],
        "n": s["n"], "n_missing": s["n_missing"],
        "mean": round(s["mean"], 2), "median": round(s["median"], 2), "sd": round(s["sd"], 2),
        "skew": round(s["skew"], 2), "p5": round(s["p5"], 2), "p95": round(s["p95"], 2),
        "weighted_mean": round(s["weighted_mean"], 2), "weighted_median": round(s["weighted_median"], 2),
    })
json.dump(stats_rows, open("out/dash_stats.json", "w"))

hist_rows = []
for short, v in raw["variables"].items():
    for view_key, view_name in [("raw_linear", "raw_linear"), ("raw_log", "raw_log"),
                                ("weighted_linear", "weighted_linear"), ("weighted_log", "weighted_log")]:
        h = v[view_key]
        for lo, hi, c, cnt in zip(h["edges"][:-1], h["edges"][1:], h["centers"], h["counts"]):
            hist_rows.append({"variable": short, "view": view_name, "bin_lo": round(lo, 4),
                              "bin_hi": round(hi, 4), "bin_center": round(c, 4), "count": round(cnt, 3)})
json.dump(hist_rows, open("out/dash_histograms.json", "w"))

print(f"summary: {len(summary)} row | stats: {len(stats_rows)} rows | histograms: {len(hist_rows)} rows")
print("stats sample:", stats_rows[0])
