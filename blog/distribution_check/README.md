# Distribution check: diameter, height, biomass, volume (live trees, FIADB)

Question: what do the per-tree distributions of diameter, height, biomass, and volume look like in the current
FIA data, and is the raw tree count a fair picture of the forest or an artifact of how FIA samples trees of
different sizes?

**Live interactive dashboard:** https://claude.ai/artifact/KsQBDMiLRx3vu3P3rgWEiR (adjustable bin count, a two-variable
scatter plot, and region/state scoping, all computed client-side from a stratified sample -- see "The dashboard"
below).

Run order (from this folder; reads the SQLite export directly, no PostgreSQL needed):
`01_extract.py` -> `02_analyze.py` -> `03_export_dashboard_data.py` -> `04_export_flat_dashboard_data.py` -> `05_export_sample.py`.

## Scope and data
Live trees only (`STATUSCD = 1`) on each state's latest EXPCURR evaluation (the same plot scope used throughout
this project). 3,518,601 trees on 334,046 plots (about 27 trees per forested plot, consistent with the carbon
analysis elsewhere in this project).

- **DIA** (inches), **HT** (feet), **biomass** (`DRYBIO_AG + DRYBIO_BG`, pounds), **VOLCFNET** (net merchantable
  volume, cubic feet) -- all raw per-tree FIADB quantities, not expanded to a per-acre density.
- `HT = 999` sentinel rows (a documented project gotcha) are set to missing.
- `VOLCFNET` can be negative for heavily defective trees (a real, documented cull/defect deduction, not an error).
  This extract has none; the analysis script checks for them on every run and would switch the volume panel to a
  symlog axis if a future rerun has any.
- Missingness: DIA/HT/biomass are ~99.85% complete. VOLCFNET is 77.5% complete (missing mostly on very small
  trees and in evaluations that don't model volume for all tree classes).

## Two views, and why both are needed
**Raw tree counts** (`fig1_distributions`, `fig2_log_distributions`) answer "what does the sample look like." They
are not a population-representative picture of the forest on their own: FIA measures small trees (DIA < 5 in) on
a smaller-radius microplot and trees >= 5 in on the full subplot. Because a tree just above the 5-in threshold is
swept in by a much larger sample area than a tree just below it, the raw diameter histogram shows an artificial
dip-then-spike right at 5 in that has nothing to do with the actual forest (visible in `fig1`/`fig2`, and it carries
through into the biomass panel, since biomass tracks diameter closely).

**TPA-weighted distributions** (`fig3_tpa_weighted`, `fig4_tpa_weighted_log`) weight each tree by `tpa_adj`
(`TPA_UNADJ` times the microplot/subplot `ADJ_FACTOR`, the standard per-plot expansion used throughout this
project), which corrects that design effect. This is a shape correction, not a population total -- no acreage
expansion is applied, so the y-axis is "trees per acre, relative" rather than a true per-acre count. Once
weighted, the diameter distribution is a smooth, monotonically declining reverse-J curve, the shape expected of a
natural, uneven-aged forest, with no artifact at 5 in.

## Results
| Variable | Unweighted mean / median | TPA-weighted mean / median |
|---|---|---|
| DIA (in) | 9.0 / 7.4 | 4.3 / 2.7 |
| HT (ft) | 50.5 / 48.0 | 30.1 / 23.0 |
| Biomass (lbs) | 1,044.1 / 279.0 | 256.3 / 21.3 |
| VOLCFNET (cu ft) | 25.1 / 7.0 | 16.8 / 6.7 |

The weighted values are substantially smaller for every variable: small trees vastly outnumber large ones per
acre, even though a randomly *sampled* tree (unweighted) tends to be larger, because large trees are sampled over
a bigger plot area and so are individually more likely to be captured in the TREE table per unit of search effort.
All four raw distributions are heavily right-skewed (skewness 1.3-15.6); biomass and volume are the most skewed,
consistent with the cubic/allometric relationship between diameter and those quantities.

## The dashboard
The static figures below are fixed at 60 bins, national totals, and a 50/50 raw-vs-weighted split. The live
dashboard (linked above) is more flexible: a bin-count slider (8-100) recomputes all four histograms in the
browser, a scatter plot lets you pick any two of the four variables (diameter, height, biomass, volume) against
each other, and a region/state filter (US Census 4-region grouping, or any individual state) rescopes everything
together. That interactivity needs raw per-tree rows in the browser, not precomputed bins, and the full 3.5M-tree
population is too large to ship to a client -- `05_export_sample.py` draws a stratified sample (82,279 trees, a
floor of 250 per state so small states aren't empty) that reproduces the full population's weighted and
unweighted medians exactly (checked against `out/dashboard_data.json` before use). `dashboard_index.html` is the
page's source, written against the Dashboard Artifact type's `dash` API (d3 v7, no other libraries); its data
lives in the artifact's own store, not in this repo, and is built from `out/dash_sample.json` and
`out/dash_states.json`.

## Files
- `out/dash_sample.json` -- the 82,279-tree stratified sample behind the interactive dashboard (short keys:
  s=statecd, d=dia, h=ht, b=biomass_lbs, v=volcfnet_cuft, w=tpa_adj).
- `out/dash_states.json` -- state code, name, and US Census region, for the dashboard's scope filters.
- `out/dash_summary.json`, `out/dash_stats.json`, `out/dashboard_data.json` -- national full-population totals and
  per-variable statistics (exact, not sampled), feeding the dashboard's header KPIs and comparison table.
- `out/summary_stats.csv` -- n, missingness, mean, sd, skew, and percentiles (1st-99th) for each variable, unweighted.
- `out/weighted_summary_stats.csv` -- TPA-weighted vs. unweighted mean/median, from the table above.
- `figures/fig1_distributions`, `fig2_log_distributions` -- raw tree-count histograms, linear (trimmed to p99.5)
  and log x-axis (full range).
- `figures/fig3_tpa_weighted`, `fig4_tpa_weighted_log` -- TPA-weighted histograms, same two views.
- `dashboard_index.html` -- the interactive dashboard's page source.

`data/tree_measurements.csv` (the full 3,518,601-row per-tree extract, ~250 MB) is not included here; regenerate
it with `01_extract.py` against the SQLite export.

## Limitations
This is a per-tree distribution check, not a design-based population estimate (no post-stratified variance, no
acreage expansion -- see `carbon_ecoregion/` elsewhere in this project for that machinery applied to carbon). HT
reflects whatever is in the database today, a mix of field-measured and modeled heights (HTCD 1/2/3/4); this
check does not separate by HTCD -- see the blog series (`blog/post.md`, `blog/htcd4/post.md`) for that question
specifically. VOLCFNET's ~22.5% missingness is not characterized further here (e.g., whether it concentrates in
particular states, species, or small-tree classes).
