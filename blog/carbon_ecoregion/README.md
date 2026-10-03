# Live-tree carbon density by ecodivision: design-based estimates, spread, and aggregation checks

Question: does live-tree carbon density (tons C per forested acre) differ across Cleland ecodivisions, how precisely can each
regional estimate be stated under FIA's post-stratified design, and does aggregating states and ecodivisions reproduce the
same national total?

Run order (from this folder; reads the SQLite export directly, no PostgreSQL needed):
`01_extract.py` -> `02_analyze.py` -> `03_measurement_basis.py` -> `04_connector_fig.py` -> `05_design_estimates.py`
-> `06_benchmark_ag_bg.py` -> `07_design_figures.py` -> `08_design_figs.py`.

`02_analyze.py` produces unweighted plot-level descriptives and omnibus/pairwise tests. The design-based estimates
(05, 06, 07, 08) supersede its means, intervals, and spread values for reporting.

## Data and scope
- **Live-tree carbon only**: `TREE.CARBON_AG + TREE.CARBON_BG` (FIA's NSVB-derived values), summed per plot with the
  project's per-plot weighting (`TPA_UNADJ x ADJ_FACTOR`, micr if DIA < 5 else subp) and converted to short tons per acre.
- Each state's latest EXPCURR evaluation (`data/latest_evalid.csv`). 334,046 plots on those evaluations; 128,789 forested
  (carbon > 0).
- Ecodivision assignment by spatial join with the Cleland layer. 313,178 plots fall in a division; 125,123 of them are
  forested. Plots in the Cleland "Water" polygons (2,246; 162 forested) and plots outside the layer (AK, HI, Pacific
  islands, territories; 3,666 forested in total with the water polygons) form a non-division (`NA`) domain, included in
  national totals.
- One division (262, n = 21 forested) is below the 100-plot threshold and is reported descriptively only.

## Design-based estimation (05_design_estimates.py)
Follows `paper/06_design_variance.py` (Bechtold & Patterson 2005; Scott et al. 2005, eq. 4.14):
- Strata h with n_h plots and EXPNS_h acres per plot; A = sum EXPNS_h n_h; W_h = EXPNS_h n_h / A.
- Total = sum_h EXPNS_h sum_j y_j; Var = A^2 [ (1/n) sum_h W_h S_h + (1/n^2) sum_h (1 - W_h) S_h ], S_h the within-stratum
  covariance matrix. Domain estimates use domain indicators with full-stratum n_h.
- Mean per forested acre = total carbon / total forested acres, with delta-method variance.
- Design-weighted spread (wCV) = sd / mean with each plot weighted by EXPNS, over forested plots.
- Aggregation checks: states = divisions + NA (exact); national total recomputed independently by AG and BG
  (06_benchmark_ag_bg.py) matches.

Key outputs:
- `out/d1_state_design.csv`: per state, n plots, forested acres, total, mean, SE, CI, wCV, unweighted CV.
- `out/d2_division_design.csv`: per ecodivision, same quantities (plus division names).
- `out/d3_national.json`: national totals, identity checks, CONUS subtotal, national mean and SE.
- `out/d4_spread_by_level.csv`: wCV by state, division, and national (restricted to division-assigned forested plots).
- `out/d5_national_ag_bg.json`: aboveground and belowground national totals.
- `out/design_evaluation.md`: write-up of the aggregation checks, the comparison with a published aboveground figure,
  and the design-vs-unweighted changes.
- `out/t3_carbon_by_htcd_division.csv` (03): design-weighted share of each division's carbon by height method (HTCD).

## Figures
- `fig1_boxplot_by_division` (02): plot-level violin plots, unweighted (distribution shape).
- `fig3_map_mean_carbon` (08): design-based means by ecodivision.
- `fig4_connector_htcd_share` (04): HTCD shares for the 12 highest design-weighted divisions.
- `fig5_variance_by_division` (08): design-weighted CV by division, ordered by n.
- `fig6_cv_vs_nplots` (08): design-weighted CV vs n (log scale) with OLS trend on log(n).
- `fig8_design_spread_state_vs_division` (07): design-weighted CV, ecodivision vs state (Mann-Whitney).
- PNG and PDF for each.

## Unweighted descriptives and tests (02_analyze.py)
- Omnibus tests (Levene; Welch ANOVA; Kruskal-Wallis; Fisher ANOVA; Welch on log1p): all reject equal means and agree
  on effect size (partial eta^2 about 0.22). See `out/anova_results.json`.
- Pairwise: Games-Howell and Dunn-Holm, 595 pairs; 540 (90.8%) and 530 (89.1%) significant at p < 0.05.
- `out/t1_division_summary.csv`, `out/t2_normality_by_division.csv`, `out/pairwise_*.csv`.
- `figures/fig3_unweighted_map_mean_carbon`, `fig5_unweighted_cv_by_division`, `fig6_unweighted_cv_vs_nplots`,
  `fig7_unweighted_cv_division_vs_state` are written by 02 under those names (regenerate only if needed for comparison).

## Limitations
- Live-tree carbon only. Current evaluations mix inventory years across states.
- Intervals and wCV use plot sampling only; NSVB equation error and height-imputation uncertainty are excluded.
- Ratio variance is a first-order delta approximation; strata with fewer than two plots contribute no within-stratum
  variance.
- The omnibus and pairwise tests use unweighted plot values.
- The published aboveground benchmark (14,312 million metric t) is undated and not like-for-like; the comparison in
  `out/design_evaluation.md` shows +8.6%, which needs a year-matched benchmark to resolve.
- Plot coordinates are fuzzed; division assignment depends on the generalized Cleland polygons.
