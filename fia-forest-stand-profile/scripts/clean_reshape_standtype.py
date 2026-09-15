"""Clean labels and reshape fia_all_states_standtype.csv for charting.

- Strips FIA's internal sort-order prefix (e.g. "`0001 Large diameter" -> "Large diameter").
- Drops the "Not available" stand-size bucket: confirmed zero estimate / zero
  plots in all 52 rows it appears in (it's the COND.STDSZCD IS NULL catch-all).
- Writes a cleaned long-format CSV (same shape, readable labels) and a wide
  one-row-per-state CSV with one column per metric x stand-size class,
  chart-ready for the per-state visualization.
"""
import re

import pandas as pd

SRC = "fia_all_states_standtype.csv"


def clean_label(raw: str) -> str:
    return re.sub(r"^`\d+\s*", "", raw).strip()


def main() -> None:
    df = pd.read_csv(SRC)
    df["stand_size_class"] = df["stand_size_class"].map(clean_label)
    df = df[df["stand_size_class"] != "Not available"].copy()

    df.to_csv("fia_all_states_standtype_clean.csv", index=False)

    wide = df.pivot_table(
        index=["state", "report_years"],
        columns=["metric", "stand_size_class"],
        values="estimate",
    )
    wide.columns = [f"{metric}_{cls.replace(' ', '_')}" for metric, cls in wide.columns]
    wide = wide.reset_index()
    wide.to_csv("fia_all_states_standtype_wide.csv", index=False)

    print("clean long format:", df.shape)
    print("wide format:", wide.shape)
    print(wide.head(8).to_string())


if __name__ == "__main__":
    main()
