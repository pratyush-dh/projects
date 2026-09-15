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

Every metric is broken out by **stand-size class** (seedling/sapling →
poletimber → sawtimber, plus nonstocked) — FIA's classification of a stand's
successional stage — so you can see not just how much wood a state holds, but
whether it's locked up in young regenerating stands or old mature ones.

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
| `data/state_by_standtype.csv` | Long-format state-level estimates: state × metric × stand-size class, with SE, SE%, and plot counts |
| `data/county_by_standtype.csv` | Same, at county granularity (2,971 counties) |
| `scripts/client.py` | Thin FIADB-API `/fullreport` client (query builder + response parser) |
| `scripts/schema_scraper.py` | Scrapes the FIADB-API's own parameter reference pages into a machine-readable table/column map |
| `scripts/fia_state_standtype_metrics.py` | Pulls all 7 metrics × all 52 state/region evaluations |
| `scripts/fia_county_pull.py` | Same, cross-tabbed by county (one query per state returns every county at once) |
| `scripts/build_county_files.py`, `scripts/clean_reshape_standtype.py` | Post-processing: label cleanup, county FIPS parsing, per-state file splitting |

## Coverage notes (real data gaps, not bugs)

- **Wyoming and Alaska's Interior unit** have no growth/removals/mortality
  data — every evaluation on file for them is flagged without
  growth-accounting, so the live API itself can't produce those estimates.
  Volume, biomass, sawlog, and area are unaffected.
- **Hawaii** has no sawlog data — its forests are predominantly tropical
  hardwood/woodland species outside the mainland timber-species board-foot
  system.
- **Alaska and Texas** are split into Coastal/Interior and East/West survey
  units respectively, at different vintages (Texas West's newest evaluation
  is 2004–2013 vs. East's 2019–2025) — shown separately rather than summed,
  since blending an 11+ year old survey into a "current" total would be
  misleading.
- The county FIPS parser has a fix baked in for a real API quirk: for the 7
  states whose FIPS code starts with `0` (AL, AK, AZ, AR, CA, CO, CT), the
  site's own display drops the leading zero from the county code — silently
  breaking a naive 5-digit parse. `fia_county_pull.py` zero-pads it back.

## Running the data pipeline yourself

```bash
pip install -r requirements.txt
python scripts/fia_state_standtype_metrics.py   # state-level pull -> fia_all_states_standtype.csv
python scripts/fia_county_pull.py               # county-level pull -> fia_county_data.csv
python scripts/build_county_files.py            # split into county_json/<STATE>.json
```

Both pulls are politely throttled (a small government server, not built for
bulk scraping) and take roughly 10–20 minutes each.

## Stack

Vanilla JS + [D3](https://d3js.org/) + [topojson-client](https://github.com/topojson/topojson-client)
for the map and charts, no build step. Python (`requests`, `pandas`,
`beautifulsoup4`) for the data pipeline.
