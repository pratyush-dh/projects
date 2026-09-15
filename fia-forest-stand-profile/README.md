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

**This is a one-time snapshot, not a live feed.** The queries described above
were run once, on 2026-09-14, and their results are baked into `index.html`
and the `county_json/`/`data/` files below — the published page has no way to
call the live FIADB-API itself (a static GitHub Pages site can't run the
Python client), so it can't refresh on its own. Every FIA evaluation on
record gets updated on its own schedule (see "Current inventory" per state in
the app), so figures here will drift from EVALIDator's live numbers as newer
evaluations post. To get a fresher pull, re-run the pipeline below — nothing
about the process is a one-off; every step is a checked-in script.

Light/dark theme toggle top-right; typeface is Source Sans (Google Fonts'
maintained successor to Source Sans Pro), matching the typeface FIADB-API's
own pages ship (`static/css/index.css`). State postal-code labels sit at
each state's centroid on the national map.

**"View / export data"** opens a custom export builder: pick any combination
of states and metrics, at state or county level, and download one combined
CSV — the multi-state, multi-variable pull EVALIDator makes you do one query
at a time and stitch together by hand. **"Download map (SVG)"** opens a
preview of the exact file before saving anything — title, description,
legend, and a source line baked in as real SVG shapes/text (not just the
bare shapes), at whatever pan/zoom the map is currently at, so it reads on
its own dropped into a report or a slide. While zoomed into a county view,
every other state fades to a low-opacity backdrop instead of staying at full
national-map intensity, so the county symbology reads as the actual subject
— on screen and in the export, which just clones that same view.

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
| `index.html` | The app itself, built — do not hand-edit; regenerate it from `src/template.html` via `scripts/build_index.py` |
| `src/template.html` | The actual source: every line of markup, CSS, and JS, with `RAW`/`TOPO` placeholders for whatever the last pull produced |
| `states-topo.json` | The *national* map's own topology (TopoJSON, Albers composite) — baked into `index.html` at build time. Source: [US Census Bureau Cartographic Boundary Files, 2017](https://www.census.gov/geographies/mapping-files/time-series/geo/carto-boundary-file.2017.html) (public domain), redistributed as TopoJSON by [us-atlas](https://github.com/topojson/us-atlas) — see [Data sources & citations](#data-sources--citations) |
| `counties-topo.json` | County boundaries for the zoomed-in view — fetched lazily by the page itself, not touched by the build. Same source as above |
| `county_json/<STATE>.json` | Per-state, per-county FIA estimates — one file per state, fetched only when a viewer drills into it |
| `data/state_by_standtype.csv` | Long-format state-level estimates: state × metric × stand-size class, with SE, SE%, and plot counts. 50 states — Texas and Alaska already merged (see below) |
| `data/county_by_standtype.csv` | Same, at county granularity (2,971 counties), each row carrying its own `report_years` |
| `scripts/client.py` | Thin FIADB-API `/fullreport` client (query builder + response parser) |
| `scripts/schema_scraper.py` | Scrapes the FIADB-API's own parameter reference pages into a machine-readable table/column map |
| `scripts/fia_state_standtype_metrics.py` | Pulls all 7 metrics × all state/region evaluations |
| `scripts/clean_reshape_standtype.py` | Strips FIA's internal label prefixes, drops the null stand-size bucket |
| `scripts/fia_county_pull.py` | Same pull as above, cross-tabbed by county (one query per state returns every county at once) |
| `scripts/merge_split_states.py` | Merges Texas (East/West) and Alaska (Coastal/Interior) into one non-overlapping dataset per state (see below) |
| `scripts/finalize_outputs.py` | Copies the merged output into the canonical `data/*.csv` files above, with explicit column selection |
| `scripts/build_county_files.py` | Splits `data/county_by_standtype.csv` into `county_json/<STATE>.json` |
| `scripts/build_index.py` | Fills `src/template.html`'s placeholders in from `data/state_by_standtype.csv` + `states-topo.json` -> `index.html` |

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
- **Even after merging, growth/removals/mortality still show "No data" for
  most Texas and Alaska counties — this is a real limit of the source data,
  not a leftover merge bug.** Those three metrics require growth-accounting,
  which needs a plot to have been *remeasured* (visited more than once).
  Checking the pre-merge data directly: Texas-West's growth rows cover
  exactly the same 43 counties as Texas-East (at older, lower values) — the
  other 203 counties never had a remeasured plot in either vintage, so
  there's no fallback value to merge in. Volume, biomass, sawlog, and area
  don't need remeasurement and cover nearly the whole state in both. The app
  shows a metric-aware caveat explaining this whenever growth, removals, or
  mortality is selected for TX or AK.
- The county FIPS parser has a fix baked in for a related but separate API
  quirk: for the 7 states whose FIPS code starts with `0` (AL, AK, AZ, AR,
  CA, CO, CT), the site's own display drops the leading zero from the county
  code — silently breaking a naive 5-digit parse. `fia_county_pull.py`
  zero-pads it back.

## Running the data pipeline yourself

```bash
pip install -r requirements.txt
python scripts/fia_state_standtype_metrics.py   # state-level pull -> fia_all_states_standtype.csv
python scripts/clean_reshape_standtype.py       # label cleanup -> fia_all_states_standtype_clean.csv
python scripts/fia_county_pull.py               # county-level pull -> fia_county_data.csv
python scripts/merge_split_states.py            # merge TX East/West + AK Coastal/Interior
python scripts/finalize_outputs.py              # -> data/state_by_standtype.csv, data/county_by_standtype.csv
python scripts/build_county_files.py            # -> county_json/<STATE>.json
python scripts/build_index.py                   # data/state_by_standtype.csv + src/template.html -> index.html
```

Both pulls are politely throttled (a small government server, not built for
bulk scraping) and take roughly 10–20 minutes each. `src/template.html` is
the actual app — markup, CSS, every line of JS — with two placeholders
(`RAW`, `TOPO`) standing in for whatever the last pull produced;
`build_index.py` is the only step that touches `index.html`, the file
GitHub Pages actually serves. `states-topo.json` (the *national* map's
topology) is a one-time, no-need-to-re-pull asset from
[us-atlas](https://github.com/topojson/us-atlas) — separate from
`counties-topo.json`, which is fetched lazily by the page itself and isn't
touched by this pipeline at all.

A GitHub Actions workflow (`.github/workflows/monthly-refresh.yml`) runs
this whole sequence on the 1st of each month and opens a pull request if
anything changed — see below.

## Keeping this current

FIA's evaluations post on their own schedule, not continuously — this
isn't a live feed to poll every minute, it's a periodic survey to re-harvest
on a cadence that matches how the source actually updates. A monthly
GitHub Actions job (`.github/workflows/monthly-refresh.yml`) re-runs the
full pipeline above and opens a pull request with whatever changed —
nothing merges automatically, so a bad pull (a USDA-side API or format
change, say) gets caught before it goes live rather than after. Trigger it
by hand from the Actions tab (`workflow_dispatch`) any time, or just wait
for the 1st of the month.

The Claude Artifact version of this project (linked from the portfolio
entry) is a separate, one-time copy — this workflow only updates GitHub
Pages, since Actions has no way to publish to an Artifact.

## Stack

Vanilla JS + [D3](https://d3js.org/) + [topojson-client](https://github.com/topojson/topojson-client)
for the map and charts, no build step. Python (`requests`, `pandas`,
`beautifulsoup4`) for the data pipeline.

## License

The code in this folder ([LICENSE](LICENSE)) is MIT — use it, fork it, learn
from it. The FIA estimates themselves are produced by a US federal agency and
aren't copyrightable in the US to begin with (17 U.S.C. § 105); `states-topo.json`
and `counties-topo.json` are public-domain US Census Bureau data, redistributed
by [us-atlas](https://github.com/topojson/us-atlas) — see the citations below.

## Data sources & citations

Nothing here is original data — this project queries and reshapes work
produced by others, so it's credited properly rather than folded quietly
into "the map" or "the data":

- **Forest inventory estimates.** U.S. Department of Agriculture, Forest
  Service, Forest Inventory and Analysis (FIA) Program. Retrieved via the
  live FIADB-API `/fullreport` endpoint
  ([research.fs.usda.gov/products/dataandtools/evalidator-and-fiadb-api](https://research.fs.usda.gov/products/dataandtools/evalidator-and-fiadb-api)).
  This project queries the same underlying estimation engine as USDA's own
  **EVALIDator** web tool, but is not affiliated with or endorsed by USDA or
  the Forest Service. Recommended EVALIDator citation:
  > Miles, P.D. Forest Inventory EVALIDator web-application. St. Paul, MN:
  > U.S. Department of Agriculture, Forest Service, Northern Research
  > Station. [research.fs.usda.gov/understory/evalidator-user-guide](https://research.fs.usda.gov/understory/evalidator-user-guide)
- **State and county boundaries.** U.S. Census Bureau, Cartographic
  Boundary Files, 2017 (public domain) — a generalized, small-scale-mapping
  derivative of the Bureau's MAF/TIGER geographic database, not the raw
  TIGER/Line Shapefiles themselves. Recommended citation, per the [Census
  Bureau's own citation guidance](https://www.census.gov/about/policies/citation.html):
  > U.S. Census Bureau, "cb_2017_us_state_20m" / "cb_2017_us_county_20m",
  > Cartographic Boundary Files, 2017,
  > [census.gov/geographies/mapping-files/time-series/geo/carto-boundary-file.2017.html](https://www.census.gov/geographies/mapping-files/time-series/geo/carto-boundary-file.2017.html).

  This project uses [us-atlas](https://github.com/topojson/us-atlas)'s
  TopoJSON redistribution of those files (`states-topo.json`,
  `counties-topo.json`) rather than processing the shapefiles directly —
  credited as the immediate source of those two files above, alongside the
  Census Bureau as the original data owner.
- **Land area denominators.** U.S. Census Bureau state land-area reference
  figures (`STATE_LAND_ACRES` in `src/template.html`), used only for the
  "per acre of whole state" view — a coarse denominator, not FIA data.
