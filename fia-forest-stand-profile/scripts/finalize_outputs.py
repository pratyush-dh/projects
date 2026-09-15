"""Copy merge_split_states.py's output into the checked-in data/ files this
repo (and the README) treats as canonical -- explicit column selection so a
column-order change upstream can't silently reshuffle what index.html and
county_json/ get built from.
"""
import pandas as pd

STATE_COLS = ["state", "metric", "stand_size_class", "estimate", "se", "se_percent", "plot_count", "report_years"]
COUNTY_COLS = ["state", "metric", "stand_size_class", "county_fips", "county_name", "estimate", "se", "se_percent", "plot_count", "report_years"]


def main() -> None:
    state_df = pd.read_csv("fia_all_states_standtype_merged.csv")
    state_df[STATE_COLS].to_csv("data/state_by_standtype.csv", index=False)
    print(f"data/state_by_standtype.csv: {len(state_df)} rows, {state_df['state'].nunique()} states")

    county_df = pd.read_csv("fia_county_data_merged.csv", dtype={"county_fips": str})
    county_df["county_fips"] = county_df["county_fips"].str.zfill(5)
    county_df[COUNTY_COLS].to_csv("data/county_by_standtype.csv", index=False)
    print(f"data/county_by_standtype.csv: {len(county_df)} rows, {county_df['county_fips'].nunique()} counties")


if __name__ == "__main__":
    main()
