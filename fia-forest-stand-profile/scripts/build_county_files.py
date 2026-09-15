"""Split the merged, post-East/West-fix county data into one compact JSON
file per state, for lazy client-side loading (fetched only when a viewer
drills into that state, instead of shipping every US county in the main
page payload).

Reads fia_county_data_merged.csv (merge_split_states.py's output), not the
raw fia_county_data.csv -- TX and AK's East/West and Coastal/Interior
overlap has already been resolved there, and each row's report_years
reflects the actual survey vintage that county's estimate came from, which
can now vary within a state. Kept per row (not dropped) for exactly that
reason: unlike every other state, one report_years value can no longer
speak for all of a blended-vintage state's counties.

Output: county_json/<STATE>.json, each a flat list of
{metric, stand_size_class, county_fips, county_name, estimate, se, se_percent, plot_count, report_years}
for that state only.
"""
import json
from pathlib import Path

import pandas as pd

df = pd.read_csv("fia_county_data_merged.csv", dtype={"county_fips": str})
df["county_fips"] = df["county_fips"].str.zfill(5)
df["se_percent"] = df["se_percent"].fillna(0)

out_dir = Path("county_json")
out_dir.mkdir(exist_ok=True)

total_bytes = 0
for state, g in df.groupby("state"):
    records = g[["metric", "stand_size_class", "county_fips", "county_name", "estimate", "se", "se_percent", "plot_count", "report_years"]].to_dict(orient="records")
    path = out_dir / f"{state}.json"
    text = json.dumps(records, separators=(",", ":"))
    path.write_text(text, encoding="utf-8")
    total_bytes += len(text.encode("utf-8"))
    print(f"{state}: {len(records)} rows, {len(text)/1024:.1f} KB, {g['county_fips'].nunique()} counties")

print(f"\ntotal: {total_bytes/1024/1024:.2f} MB across {df['state'].nunique()} files")
