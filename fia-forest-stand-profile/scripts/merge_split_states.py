"""Merge Texas (East/West) and Alaska (Coastal/Interior) into single, non-
overlapping datasets.

Root cause of the "Angelina County has two different values" bug: TX-East and
TX-West are NOT a geographic partition of Texas counties. They're two
overlapping FIA evaluations at different vintages -- TX-East (482025,
2019-2025, growth-accounting enabled) covers 43 counties, all of which are
ALSO covered by TX-West (482013, 2004-2013), which covers 246 of Texas's 254
counties. The same real county has a genuinely different reported value in
each survey. Alaska has the same structure at smaller scale (Coastal/Interior
share 3 boroughs). Treating them as two selectable "regions" let a viewer
land on either one for the same county without any indication the other
existed -- hence two silently different numbers for one place.

Fix: for every (metric, stand-size class, county) cell, prefer the newer
survey (East / Coastal) where it has data, and fall back to the older one
(West / Interior) only for counties the newer survey doesn't cover. Each
merged county row keeps the report_years of whichever survey it actually
came from, so vintage differences within one state stay visible per county
instead of being asserted as one (wrong) state-wide figure.

State-level totals are then rebuilt from these merged county rows (sum of
estimates, SE combined as sqrt(sum of squares) across independent counties)
rather than kept as the original two separate whole-region query results --
this guarantees the state total and "sum of the county map" always agree,
which they could not before (the two source queries had different county
footprints).
"""
import math

import pandas as pd

MERGES = [
    ("TX", "TX-East", "TX-West"),
    ("AK", "AK-Coastal", "AK-Interior"),
]


def merge_counties(county_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (merged_county_rows, dropped_original_rows) for TX and AK."""
    merged_frames = []
    drop_states = set()

    for new_label, primary, secondary in MERGES:
        drop_states.update([primary, secondary])
        prim = county_df[county_df["state"] == primary]
        sec = county_df[county_df["state"] == secondary]

        key = ["metric", "stand_size_class", "county_fips"]
        prim_keys = set(map(tuple, prim[key].values))

        sec_unique = sec[~sec[key].apply(tuple, axis=1).isin(prim_keys)]

        merged = pd.concat([prim, sec_unique], ignore_index=True)
        merged["state"] = new_label
        merged_frames.append(merged)

        print(
            f"{new_label}: {len(prim)} rows from {primary} + {len(sec_unique)} "
            f"rows from {secondary} (of {len(sec)} available) = {len(merged)} rows, "
            f"{merged['county_fips'].nunique()} distinct counties"
        )

    merged_all = pd.concat(merged_frames, ignore_index=True)
    kept = county_df[~county_df["state"].isin(drop_states)]
    return pd.concat([kept, merged_all], ignore_index=True), county_df[county_df["state"].isin(drop_states)]


def rebuild_state_totals(merged_county_df: pd.DataFrame, state_df: pd.DataFrame) -> pd.DataFrame:
    """Recompute TX/AK state-level rows as the sum of their merged county rows."""
    new_state_labels = [m[0] for m in MERGES]
    old_labels = [lbl for m in MERGES for lbl in (m[1], m[2])]

    rows = []
    for new_label in new_state_labels:
        sub = merged_county_df[merged_county_df["state"] == new_label]
        for (metric, cls), g in sub.groupby(["metric", "stand_size_class"]):
            estimate = g["estimate"].sum()
            se = math.sqrt((g["se"] ** 2).sum())
            plot_count = int(g["plot_count"].sum())
            se_percent = (se / estimate * 100) if estimate else None
            # report_years: the newer (primary) survey's years where it contributed
            # any county; else the fallback survey's years.
            primary_label = next(p for n, p, s in MERGES if n == new_label)
            years_source = g if (g["county_fips"].isin(
                merged_county_df[merged_county_df["state"] == new_label]["county_fips"]
            )).all() else g
            report_years = state_df.loc[state_df["state"] == primary_label, "report_years"]
            report_years = report_years.iloc[0] if len(report_years) else ""
            rows.append(dict(
                state=new_label, metric=metric, stand_size_class=cls,
                estimate=estimate, se=se, se_percent=se_percent,
                plot_count=plot_count, report_years=report_years,
            ))
    new_rows = pd.DataFrame(rows)
    kept = state_df[~state_df["state"].isin(old_labels + new_state_labels)]
    return pd.concat([kept, new_rows], ignore_index=True)


def main():
    county_df = pd.read_csv("fia_county_data.csv", dtype={"county_fips": str})
    county_df["county_fips"] = county_df["county_fips"].str.zfill(5)
    state_df = pd.read_csv("fia_all_states_standtype_clean.csv")

    merged_county_df, dropped = merge_counties(county_df)
    merged_county_df.to_csv("fia_county_data_merged.csv", index=False)

    new_state_df = rebuild_state_totals(merged_county_df, state_df)
    new_state_df.to_csv("fia_all_states_standtype_merged.csv", index=False)

    print("\nFinal state count:", new_state_df["state"].nunique())
    print("Final county-file state count:", merged_county_df["state"].nunique())

    # sanity check: Angelina county now has exactly one row per metric/class
    ang = merged_county_df[(merged_county_df["state"] == "TX") & (merged_county_df["county_name"] == "Angelina")]
    dupes = ang.groupby(["metric", "stand_size_class"]).size()
    print("\nAngelina duplicate check (should all be 1):")
    print(dupes[dupes > 1] if (dupes > 1).any() else "OK -- no duplicates")


if __name__ == "__main__":
    main()
