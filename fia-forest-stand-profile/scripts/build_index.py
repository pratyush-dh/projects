"""Regenerate index.html from src/template.html + data/state_by_standtype.csv +
counties-topo.json.

The template is the actual app (markup, CSS, all JS logic) with two
placeholders standing in for data that changes every pull:

    const RAW = /*__DATA__*/[];
    const TOPO = /*__TOPO__*/{};

This script fills them in and writes the result to index.html. It is the
last step of the pipeline (after fia_state_standtype_metrics.py ->
clean_reshape_standtype.py -> fia_county_pull.py -> merge_split_states.py ->
finalize_outputs.py -> build_county_files.py), and the only step that
touches the file GitHub Pages actually serves.
"""
import csv
import json
from pathlib import Path

TEMPLATE = Path("src/template.html")
STATE_CSV = Path("data/state_by_standtype.csv")
TOPO_JSON = Path("states-topo.json")  # the national map's own topology -- NOT
# counties-topo.json, which the page fetches lazily and separately, only once
# a viewer actually drills into a state
OUT = Path("index.html")

NUMERIC_FIELDS = {"estimate", "se", "se_percent", "plot_count"}


def load_raw(path: Path) -> list[dict]:
    rows = []
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            for field in NUMERIC_FIELDS:
                # se_percent is blank exactly when estimate and se are both 0
                # (0/0 is undefined) -- 0.0 there, not null, so nothing downstream
                # that expects a number (e.g. `.toFixed()`) can choke on it.
                if row.get(field) not in (None, ""):
                    row[field] = float(row[field]) if field != "plot_count" else int(float(row[field]))
                else:
                    row[field] = 0
            rows.append(row)
    return rows


def main() -> None:
    raw = load_raw(STATE_CSV)
    raw_json = json.dumps(raw, separators=(",", ":"))

    topo_json = TOPO_JSON.read_text(encoding="utf-8").strip()
    json.loads(topo_json)  # fail loudly here, not with a broken page

    html = TEMPLATE.read_text(encoding="utf-8")

    data_marker = "const RAW = /*__DATA__*/[];"
    topo_marker = "const TOPO = /*__TOPO__*/{};"
    if data_marker not in html:
        raise SystemExit(f"template is missing the expected marker: {data_marker!r}")
    if topo_marker not in html:
        raise SystemExit(f"template is missing the expected marker: {topo_marker!r}")

    html = html.replace(data_marker, f"const RAW = {raw_json};", 1)
    html = html.replace(topo_marker, f"const TOPO = {topo_json};", 1)

    OUT.write_text(html, encoding="utf-8", newline="\n")
    print(f"wrote {OUT} ({len(html)/1024:.0f} KB) from {len(raw)} state-level rows")


if __name__ == "__main__":
    main()
