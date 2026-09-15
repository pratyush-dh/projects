"""Split fia_county_data.csv into one compact JSON file per state/region label,
for lazy client-side loading (fetched only when a viewer drills into that
state, instead of shipping every US county in the main page payload).

Output: county_json/<LABEL>.json, each a flat list of
{metric, stand_size_class, county_fips, county_name, estimate, se, se_percent, plot_count}
for that state only (report_years dropped -- same per state, already shown
elsewhere on the page).
"""
import json
from pathlib import Path

import pandas as pd

df = pd.read_csv("fia_county_data.csv", dtype={"county_fips": str})
df["county_fips"] = df["county_fips"].str.zfill(5)
df["se_percent"] = df["se_percent"].fillna(0)

out_dir = Path("county_json")
out_dir.mkdir(exist_ok=True)

total_bytes = 0
for state, g in df.groupby("state"):
    records = g[["metric", "stand_size_class", "county_fips", "county_name", "estimate", "se", "se_percent", "plot_count"]].to_dict(orient="records")
    path = out_dir / f"{state}.json"
    text = json.dumps(records, separators=(",", ":"))
    path.write_text(text, encoding="utf-8")
    total_bytes += len(text.encode("utf-8"))
    print(f"{state}: {len(records)} rows, {len(text)/1024:.1f} KB, {g['county_fips'].nunique()} counties")

print(f"\ntotal: {total_bytes/1024/1024:.2f} MB across {df['state'].nunique()} files")
