# Live-tree carbon density by ecodivision: ANOVA, significance tests, and why the uncertainty is high

Question: does mean carbon density (tons C/acre) differ across Cleland ecodivisions, is that difference
statistically defensible given FIA's sample design and the shape of the data, and why is the within-division
spread (coefficient of variation) so large to begin with?

Run order (from this folder; reads the SQLite export directly, no PostgreSQL needed):
`01_extract.py` -> `02_analyze.py` -> `03_measurement_basis.py` -> `04_connector_fig.py`.

## Scope and data
**Live tree carbon only** (`TREE.CARBON_AG + TREE.CARBON_BG`, FIA's own NSVB-derived aboveground + belowground
values for live trees) — this excludes soil organic carbon, standing/down dead wood, litter, and understory
vegetation carbon, all of which FIA also reports at the condition level (`COND.CARBON_*`) but were out of scope here
since the rest of this project has always worked at the tree level. "Carbon stock" below always means this live-tree
component; a fuller carbon accounting would add the other pools.

**Unit of analysis: one forested plot.** For each state's latest EXPCURR evaluation, every live tree's
`CARBON_AG + CARBON_BG` is weighted by `TPA_UNADJ * ADJ_FACTOR(micr if DIA<5 else subp)` and summed per plot —
the same per-plot weighting convention `paper/01_extract_aux.py` uses for biomass — giving each plot a carbon
density in tons/acre. 313,178 plots have an assigned ecodivision (Alaska, Hawaii and the territories are excluded,
as throughout this project, since Cleland's layer doesn't cover them); 125,123 of those are forested
(`carbon_tons_acre > 0`). Divisions with fewer than 100 forested plots (just one: 262, n=21) are summarized but left
out of the significance tests.

**Plots, not trees, are the sampling unit** — tree-level carbon values were summed to one number per plot before any
test ran, so within-plot tree correlation cannot inflate the significance tests. FIA's base plot grid is an
equal-probability systematic sample, so an unweighted mean across a division's plots is a valid estimate of that
division's mean plot-level density; `EXPNS` (used to scale a *sample* up to a *population total*) is not needed for
a density comparison. As a sensitivity check, `out/t1_division_summary.csv` also reports each division's
`EXPNS`-weighted mean: the two agree within 10.5 percentage points everywhere, usually much closer (see
`weighted_vs_unweighted_pct`) — the biggest gaps are in divisions 242 and M242 (Marine), where plot sampling
intensity varies most by stratum.

## Why the test battery, not just one ANOVA
Carbon density is strongly right-skewed (national median skewness 1.5 across divisions) and far from equal variance
across divisions (SD ranges from about 3.6 to 63 tons/acre) — a textbook violation of classic ANOVA's assumptions,
and with sample sizes from the hundreds to the tens of thousands, a classic Shapiro-Wilk normality test would reject
almost everywhere regardless of practical importance. So instead of reporting one F-test, this runs a
convergence check:

| Test | What it assumes | Result |
|---|---|---|
| Levene's (Brown-Forsythe, median-centered) | — (tests the equal-variance assumption itself) | **Rejected**, p < 1e-300 — variances differ sharply by division |
| Welch's ANOVA (primary omnibus) | Unequal variances allowed | F(34, 9917) = 2075, p < 1e-300, partial η² = 0.219 |
| Kruskal-Wallis (nonparametric, rank-based) | No distributional assumption | H(34) = 29,479, p < 1e-300, ε² = 0.235 |
| Classic (Fisher) ANOVA | Equal variances (violated above) | F(34, 125067) = 1034, p < 1e-300, η² = 0.219 — reported for comparability only |
| Welch's ANOVA on log1p(density) | Robust to the raw scale's skew | F = 1395, p < 1e-300, partial η² = 0.242 |

All five agree: ecodivision explains a large, highly significant share of the variance in carbon density (partial
η² ≈ 0.22, i.e. ecodivision alone accounts for roughly a fifth of all plot-to-plot variation — a large effect by
conventional standards), and the conclusion is identical on the raw and log scales.

**Post-hoc pairwise comparisons** (35 divisions, 595 pairs): Games-Howell (pairs with Welch's ANOVA, safe under
unequal variance/n, built-in family-wise control) and Dunn's test with Holm correction (pairs with Kruskal-Wallis,
rank-based). They agree closely: **540/595 (90.8%)** pairs significant at p < 0.05 under Games-Howell, **530/595
(89.1%)** under Dunn-Holm. The 55 non-significant Games-Howell pairs (`out/pairwise_gameshowell.csv`, `pval >= 0.05`)
are almost all between divisions that are genuinely close in rank, or involve division 261 (n = 172, the smallest
tested group, hence the widest confidence interval in `out/t2_ranked_means_ci.csv`).

## Why the within-division spread (CV) is so high
A coefficient of variation around 0.7-0.9 per division is high for output from a national forest inventory. Two
checks were run on why:
1. **Is it a small-sample artifact?** A modest negative correlation between CV and sample size exists (Pearson
   r = -0.40 on log(n), p = 0.017), but it's loose — division 321 (n=774, a middling sample) has by far the highest
   CV in the dataset (2.10), well above what the trend line predicts. See `fig6_cv_vs_nplots`.
2. **Is it a side effect of comparing at the ecodivision level specifically?** FIA's plot grid is designed and
   allocated to support state and national estimates, not ecodivision-level ones. Regrouping the identical 125,123
   forested plots by state instead of division drops median CV from 0.84 (35 divisions) to 0.69 (48 states with
   >=100 forested plots) — a statistically significant difference (Mann-Whitney U, p = 0.015) that is **not** a
   sample-size artifact (median plots/group: 2,060 for divisions vs. 2,702 for states, comparable). See
   `fig7_cv_division_vs_state`. This is descriptive evidence consistent with — not formal proof of — the
   sampling-design explanation; see Limitations.

## The HTCD connector (`03_measurement_basis.py`, `04_connector_fig.py`)
For the 12 highest-carbon-density divisions, `03_measurement_basis.py` splits each division's total live-tree carbon
by the height-measurement method behind the trees carrying it: field-measured (HTCD 1), crew-estimated (HTCD 2/3,
blog Part 1), or FIA-modeled (HTCD 4, blog Part 2). `04_connector_fig.py` plots the result
(`fig4_connector_htcd_share`). Finding: the Pacific-coast/Mediterranean-climate divisions in the top 12 by carbon
(e.g. 263, M242, M261) draw 23-48% of their carbon from HTCD-4 (modeled) heights, while the Appalachian/eastern
divisions in the same top 12 (e.g. 221, M211, 211) draw essentially none (0.00-0.08%) — built almost entirely on
field measurement and crew estimates instead.

## Results
Carbon density ranges about 28-fold across divisions: from ~2.8 tons/acre (321, Tropical/Subtropical Steppe) to
~76.8 tons/acre (263, Mediterranean) and ~64.2 tons/acre (M242, Marine — the Pacific coast, the largest division by
sample size at n = 9,371 and the one carrying the project's earlier HTCD findings). The ranked pattern matches known
forest-carbon geography closely: Pacific coast conifer forest and the Appalachians/Northeast carry the most carbon
per acre; semi-arid divisions in the Southwest and the southern Plains carry the least. See `figures/fig3_map_mean_carbon`
for the full spatial pattern, `out/t2_ranked_means_ci.csv`/`.md` for the ranked means table with 95% CIs, and
`figures/fig1_boxplot_by_division` for the full distributions (violin plots, Tukey-fence trimmed; heavy right skew
in every division, consistent with stand age structure — most stands are young/mid-successional with a long tail of
older, denser stands).

## Files
- `data/plot_carbon.csv` (not included in this repo; regenerate with `01_extract.py`) — one row per
  current-evaluation plot (313,178 incl. AK/HI/territories before the division filter): statecd, evalid, plt_cn,
  carbon_tons_acre, n_trees.
- `data/latest_evalid.csv` — the latest EXPCURR EVALID per state, used to scope the SQLite extraction.
- `out/t1_division_summary.csv` — n, mean, median, SD, CV, skew, weighted mean, 95% CI, by division (all 36).
- `out/t2_normality_by_division.csv` — Shapiro-Wilk (2,000-row subsample) and skewness, by division.
- `out/t2_ranked_means_ci.csv` / `.md` — ranked means + 95% CI table (the one published in the blog post), highest
  to lowest, 35 included divisions plus the one excluded division (262) noted separately.
- `out/anova_results.json` — every omnibus test statistic, df, p-value and effect size above.
- `out/pairwise_gameshowell.csv`, `out/pairwise_gameshowell_log.csv`, `out/pairwise_dunn_holm.csv` — all 595 pairs.
- `out/t3_carbon_by_htcd_division.csv` — per-division carbon share by HTCD group (the connector to blog Parts 1-2).
- `out/t3_state_cv.csv` — per-state n/mean/sd/CV of carbon density, same forested-plot pool, grouped by state instead
  of ecodivision (the ecodivision-vs-state CV comparison).
- `figures/fig1_boxplot_by_division`, `fig3_map_mean_carbon`, `fig4_connector_htcd_share`,
  `fig5_variance_by_division`, `fig6_cv_vs_nplots`, `fig7_cv_division_vs_state` — PNG + PDF.

## Limitations
Live-tree carbon only (see Scope). "Current evaluation" mixes inventory years across states (each state's own most
recent cycle, consistent with the rest of this project, but not a single fixed year nationally). The 95% CIs in
`out/t2_ranked_means_ci.csv` are plot-level (mean ± 1.96×SE from the raw plot-to-plot SD and n), not FIA's full
post-stratified design-based variance estimator used elsewhere in this project for population totals — appropriate
for comparing density across groupings, but not a complete accounting of every source of uncertainty. The
ecodivision-vs-state CV comparison (`fig7_cv_division_vs_state`) is a descriptive two-sample comparison (Mann-Whitney
on group-level CVs), not a formal mixed-effects variance decomposition; it's consistent with the sampling-design
explanation but can't fully rule out that ecoregions are simply more ecologically heterogeneous than states as a
matter of geography, independent of how the sample was designed. The equal-probability-grid assumption underlying
the unweighted ANOVA is standard but not re-derived here from first principles; the weighted-mean sensitivity check
is a partial, not a full, check of it.
