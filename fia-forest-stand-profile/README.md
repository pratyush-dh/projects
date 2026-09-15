# Forest Stand Profile

**[Live demo](https://pratyush-dh.github.io/projects/fia-forest-stand-profile/)**

An interactive US forest inventory explorer built on live queries against the
USDA Forest Service's **FIADB-API** (`/fullreport`) — the same estimation
engine behind their official EVALIDator tool. It turns that data into a
zoomable choropleth map plus per-state and per-county breakdowns of:

- **Live volume** — net sound total-stem volume, live trees ≥5 in d.b.h./d.r.c.
- **Aboveground biomass** — live trees ≥1 in d.b.h./d.r.c.
- **Net annual growth**, **annual removals**, **annual mortality** — the
  growth/removals/mortality (GRM) trio, so you can see at a glance which
  states are being cut faster than they regrow, or losing more to mortality
  than growth replaces
- **Sawlog volume** — merchantable sawtimber stock, board feet
- **Forest land area** — used as the denominator for the per-acre density views
- **Latest inventory year** — the landing view: each state (and county) shaded
  by how recent its FIA evaluation is, darker green = more recently surveyed,
  matching FIA's own DataMart convention

Every metric is broken out by **stand-size class** (seedling/sapling →
poletimber → sawtimber, plus nonstocked) — FIA's classification of a stand's
successional stage — so you can see not just how much wood a state holds, but
whether it's locked up in young regenerating stands or old mature ones.

Light/dark theme toggle top-right; typeface is Source Sans (Google Fonts'
maintained successor to Source Sans Pro), matching the typeface FIADB-API's
own pages ship (`static/css/index.css`). State postal-code labels sit at
each state's centroid on the national map.

**"View / export data"** opens a custom export builder: pick any combination
of states and metrics, at state or county level, and download one combined
CSV — the multi-state, multi-variable pull EVALIDator makes you do one query
at a time and stitch together by hand. **"Download map (SVG)"** exports the
map as a self-contained, annotated file — title, description, legend, and a
source line baked in as real SVG shapes/text (not just the bare shapes), at
whatever pan/zoom the map is currently at, so it reads on its own dropped
into a report or a slide.

## Why this exists

FIA is the authoritative, plot-based inventory of American forests, but it's
genuinely hard to use directly: the API requires knowing an obscure query
vocabulary (`rselected`/`cselected`/`snum`/`wc`/evaluation groups), and USDA's
own published state bulletins are static, fixed-format PDFs/spreadsheets with
no cross-state map, no per-acre density view, and no biomass-by-stand-size
breakdown at all. This project runs the same kind of query EVALIDator supports
— across every state (and every county within it) at once — and puts the
result on one map.

## What's in this folder

| Path | Contents |
|---|---|
| `index.html` | The app itself — self-contained, all state-level data inlined, county-level data and boundaries lazy-loaded from the files below |
| `counties-topo.json` | US county boundaries (TopoJSON, Albers composite projection), from [us-atlas](https://github.com/topojson/us-atlas) (public domain, US Census TIGER derivative) |
| `county_json/<STATE>.json` | Per-state, per-county FIA estimates — one file per state/region, fetched only when a viewer drills into it |
| `data/state_by_standtype.csv` | Long-format state-level estimates: state × metric × stand-size class, with SE, SE%, and plot counts. 50 states — Texas and Alaska already merged (see below) |
| `data/county_by_standtype.csv` | Same, at county granularity (2,971 counties), each row carrying its own `report_years` |
| `scripts/client.py` | Thin FIADB-API `/fullreport` client (query builder + response parser) |
| `scripts/schema_scraper.py` | Scrapes the FIADB-API's own parameter reference pages into a machine-readable table/column map |
| `scripts/fia_state_standtype_metrics.py` | Pulls all 7 metrics × all state/region evaluations |
| `scripts/fia_county_pull.py` | Same, cross-tabbed by county (one query per state returns every county at once) |
| `scripts/merge_split_states.py` | Merges Texas (East/West) and Alaska (Coastal/Interior) into one non-overlapping dataset per state (see below) |
| `scripts/build_county_files.py`, `scripts/clean_reshape_standtype.py` | Post-processing: label cleanup, county FIPS parsing, per-state file splitting |

## Coverage notes (real data gaps, not bugs)

- **Wyoming** has no growth/removals/mortality data — every evaluation on file
  for it is flagged without growth-accounting, so the live API itself can't
  produce those estimates. Volume, biomass, sawlog, and area are unaffected.
- **Hawaii** has no sawlog data — its forests are predominantly tropical
  hardwood/woodland species outside the mainland timber-species board-foot
  system.
- **Small or heavily urbanized counties** (Virginia's 38 independent cities
  plus Arlington County are the biggest cluster) show as "no data" on the
  county map: FIA's systematic plot grid (~1 plot per 6,000 acres) places
  zero plots in some of them. Real absence of sampled forest, not a pull gap
  — the hover tooltip says so explicitly.
- **Texas and Alaska's regional survey split is a real gotcha, fixed by
  merging, not by picking a side.** Texas's FIA evaluations are named "East"
  (482025, 2019–2025, growth-accounting enabled, 43 counties) and "West"
  (482013, 2004–2013, 246 counties) — but these are **not** a geographic
  partition: all 43 East counties are *also* covered by West, at a different,
  much older vintage. Treating them as two toggle-able "units" (an earlier
  version of this project did) let the same real county carry two silently
  different values depending on which was selected — e.g. Angelina County
  showed one forest-area figure under "East" and a different one under
  "West". `merge_split_states.py` fixes this at the source: for every
  (metric, stand-size class, county) cell, it keeps the newer survey's value
  wherever the newer survey covers that county, and falls back to the older
  survey only for counties the newer one doesn't reach. State totals are then
  *rebuilt from the merged county data* (summed, SE combined as
  `sqrt(sum of squares)`) rather than kept as either original whole-region
  query result, so the state figure and the county map always agree. Alaska
  (Coastal/Interior) has the same structure at smaller scale (3 boroughs
  overlap) and gets the same fix. Because vintages now blend by county within
  one state, each county row keeps its own `report_years` rather than
  asserting one figure for the whole state — the app surfaces this via a
  caveat banner and per-county hover text whenever TX or AK is selected.
- The county FIPS parser has a fix baked in for a related but separate API
  quirk: for the 7 states whose FIPS code starts with `0` (AL, AK, AZ, AR,
  CA, CO, CT), the site's own display drops the leading zero from the county
  code — silently breaking a naive 5-digit parse. `fia_county_pull.py`
  zero-pads it back.

## Running the data pipeline yourself

```bash
pip install -r requirements.txt
python scripts/fia_state_standtype_metrics.py   # state-level pull -> fia_all_states_standtype.csv
python scripts/fia_county_pull.py               # county-level pull -> fia_county_data.csv
python scripts/merge_split_states.py            # merge TX East/West + AK Coastal/Interior
python scripts/build_county_files.py            # split into county_json/<STATE>.json
```

Both pulls are politely throttled (a small government server, not built for
bulk scraping) and take roughly 10–20 minutes each.

## Stack

Vanilla JS + [D3](https://d3js.org/) + [topojson-client](https://github.com/topojson/topojson-client)
for the map and charts, no build step. Python (`requests`, `pandas`,
`beautifulsoup4`) for the data pipeline.
