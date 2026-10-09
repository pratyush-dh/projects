#!/usr/bin/env python3
"""Distribution check, step 5: a stratified per-tree sample for the interactive dashboard (adjustable bin count,
scatter plot, state/region scoping -- all computed client-side, so raw rows are needed, not precomputed bins).
The full population (3.5M trees) is far too large to ship to a browser; this draws ~80,000 trees, with a floor
per state so small states aren't empty, and keeps the national full-population figures (out/dashboard_data.json)
as the exact reference elsewhere on the page.
-> out/dash_sample.json (short keys: s=statecd, d=dia, h=ht, b=biomass_lbs, v=volcfnet_cuft, w=tpa_adj)
-> out/dash_states.json (statecd, name, region -- US Census 4-region breakdown)
"""
import json
import numpy as np, pandas as pd
import geopandas as gpd

TARGET_N = 80_000
FLOOR_PER_STATE = 250
SEED = 42

d = pd.read_csv("data/tree_measurements.csv", low_memory=False)
print(f"{len(d):,} live trees total, {d.statecd.nunique()} state/territory codes")

frac = TARGET_N / len(d)
rng = np.random.default_rng(SEED)

parts = []
for st, g in d.groupby("statecd"):
    n_take = min(len(g), max(FLOOR_PER_STATE, round(len(g) * frac)))
    idx = rng.choice(g.index.values, size=n_take, replace=False)
    parts.append(g.loc[idx])
sample = pd.concat(parts, ignore_index=True)
print(f"sampled {len(sample):,} trees ({100 * len(sample) / len(d):.1f}% of population)")

out = pd.DataFrame({
    "s": sample.statecd.astype(int),
    "d": sample.dia.round(2),
    "h": sample.ht.round(1),
    "b": sample.biomass_lbs.round(1),
    "v": sample.volcfnet_cuft.round(2),
    "w": sample.tpa_adj.round(4),
})
out = out.dropna(subset=["d", "h", "b"], how="all")  # keep rows with at least one usable measurement
records = json.loads(out.to_json(orient="records"))
json.dump(records, open("out/dash_sample.json", "w"), separators=(",", ":"))
import os
print(f"wrote out/dash_sample.json, {os.path.getsize('out/dash_sample.json') / 1e6:.2f} MB, {len(records):,} rows")

# ---------------------------------------------------------------- state/region lookup
st_names = gpd.read_file("../paper/data/states-10m.json", layer="states")[["id", "name"]]
st_names["statecd"] = st_names.id.astype(int)
st_names = pd.concat([st_names[["statecd", "name"]], pd.DataFrame(
    {"statecd": [64, 68, 70], "name": ["Federated States of Micronesia", "Marshall Islands", "Palau"]})])

REGION = {
    **{s: "Northeast" for s in ["Connecticut", "Maine", "Massachusetts", "New Hampshire", "Rhode Island",
                                 "Vermont", "New Jersey", "New York", "Pennsylvania"]},
    **{s: "Midwest" for s in ["Illinois", "Indiana", "Michigan", "Ohio", "Wisconsin", "Iowa", "Kansas",
                               "Minnesota", "Missouri", "Nebraska", "North Dakota", "South Dakota"]},
    **{s: "South" for s in ["Delaware", "Florida", "Georgia", "Maryland", "North Carolina", "South Carolina",
                             "Virginia", "District of Columbia", "West Virginia", "Alabama", "Kentucky",
                             "Mississippi", "Tennessee", "Arkansas", "Louisiana", "Oklahoma", "Texas"]},
    **{s: "West" for s in ["Arizona", "Colorado", "Idaho", "Montana", "Nevada", "New Mexico", "Utah", "Wyoming",
                            "Alaska", "California", "Hawaii", "Oregon", "Washington"]},
}
st_names["region"] = st_names.name.map(REGION).fillna("Pacific / territories")
states_present = set(sample.statecd.unique())
st_out = st_names[st_names.statecd.isin(states_present)].sort_values("name")
records2 = st_out[["statecd", "name", "region"]].to_dict("records")
json.dump(records2, open("out/dash_states.json", "w"))
print(f"wrote out/dash_states.json, {len(records2)} states/territories")
print(st_out.groupby("region").size())
