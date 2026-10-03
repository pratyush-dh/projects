# How much carbon is in an acre of forest? It depends enormously on where you are

*Understanding FIA data, part 3: carbon density by ecoregion*

The [first](https://pratyush-dh.github.io/projects/blog/) and [second](https://pratyush-dh.github.io/projects/blog/htcd4/) posts in this series both asked one narrow question: how trustworthy are the tree heights in FIA's database when they weren't actually measured in the field? This post asks something different with the same database — how much live-tree carbon does an acre of forest actually hold, and does that number really differ from one ecoregion to the next, or could the apparent differences just be noise? Answering that honestly turns out to require two separate investigations: whether regional differences in the *average* are real, and why the *spread* within each region is as large as it is. The second investigation leads right back to the first two posts.

## The short version

- Live-tree carbon density (tons C/acre) was compared across 35 Cleland ecodivisions, using 125,123 forested FIA plots.
- The regional differences are real: density ranges 28-fold, from about 2.8 tons/acre in the driest Southwestern divisions to about 77 tons/acre on the central California coast, and it survives a battery of four distribution-robust tests plus two post-hoc procedures (details below).
- But the within-division spread is also large — coefficients of variation (CV) typically around 0.7–0.9 — and that turns out to be partly a side effect of the comparison itself: regrouping the same plots by *state* instead of by ecodivision drops the median CV from 0.84 to 0.69 (p = 0.015). FIA's sample was built to support state and national estimates, not ecoregion-level ones, and ecoregions cut across that design.
- The callback: the divisions with the *highest* carbon density are disproportionately the same Pacific-coast and Mediterranean-climate divisions that Part 2 showed lean hardest on FIA's own modeled (not field-measured) tree heights. The single highest-carbon division in this analysis gets less than half its carbon from a tree with a field-measured height.

## Why ecoregion, and why carbon

FIA computes live-tree carbon (`CARBON_AG` + `CARBON_BG`, aboveground plus belowground) from the same NSVB pipeline this series has been examining all along: species, diameter, height, ecological division, stand origin. The question here is whether that output actually separates cleanly by ecoregion — the kind of thing a land manager, a carbon-offset buyer, or anyone comparing "my forest" to "a typical forest nearby" would want to know — and whether that separation can be defended statistically rather than just eyeballed off a map.

**Scope note up front:** this is **live-tree carbon only**. FIA also reports soil organic carbon, dead wood, litter, and understory vegetation carbon at the condition level, none of which are included here. "Carbon density" below always means the live-tree component.

## Data and methods

Each forested FIA plot gets one number: the sum of every live tree's carbon, weighted by `TPA_UNADJ × ADJ_FACTOR` (the same per-plot weighting convention this series has used throughout), converted to tons per acre. The **plot**, not the tree, is the unit of analysis, so correlation between trees on the same plot can't quietly inflate the sample size the way it would if every one of the underlying 3.5 million trees were treated as independent. 313,178 plots have an assigned ecodivision (Alaska, Hawaii, and the territories are excluded, as throughout this series, since Cleland's layer doesn't cover them); 125,123 of those are forested, and divisions with fewer than 100 forested plots (one division, n = 21) are reported but excluded from the significance tests.

FIA's base plot grid is an equal-probability systematic sample, so a plain average across a division's plots is a valid estimate of that division's mean density without needing the stratum expansion factors (`EXPNS`) — those exist to scale a sample up to a population *total*, which isn't the question here. As a check, each division's `EXPNS`-weighted mean was also computed; it agrees with the unweighted mean within 10.5 percentage points everywhere, usually much closer.

## The data don't fit a textbook ANOVA

Carbon density per plot is heavily right-skewed (most stands are young, with a long tail of older, denser stands) and the spread differs enormously by region — standard deviation ranges from about 3.6 to 63 tons/acre across divisions. A Levene's test confirms the obvious: variances are not equal (p < 10⁻³⁰⁰). So instead of running one ANOVA and calling it done, a small battery of tests was run and checked for agreement:

| Test | What it assumes | Result |
|---|---|---|
| Levene's (Brown–Forsythe) | — (tests equal variance itself) | Rejected: variances differ sharply by division |
| **Welch's ANOVA** (primary) | Unequal variances allowed | F(34, 9917) = 2075, p < 10⁻³⁰⁰, partial η² = 0.219 |
| Kruskal–Wallis (rank-based) | No distributional shape assumed | H(34) = 29,479, p < 10⁻³⁰⁰, ε² = 0.235 |
| Classic (Fisher) ANOVA | Equal variances (violated above) | F(34, 125067) = 1034, p < 10⁻³⁰⁰, η² = 0.219 — for comparison only |
| Welch's ANOVA, log1p scale | Robust to the raw skew | F = 1395, p < 10⁻³⁰⁰, partial η² = 0.242 |

All four agree: ecodivision alone accounts for roughly a fifth of all plot-to-plot variation in carbon density — a large effect by conventional standards — and the conclusion doesn't change whether the raw scale, the log scale, or a test with no normality assumption at all is used.

![Figure 1. Carbon density by ecodivision, ranked by sample size (n, labeled above each violin): violin width shows the distribution, the white line the median. Points beyond the Tukey fences (1.5×IQR) are trimmed for readability.](figures/h01_boxplot_by_division.png)

For *which specific* regions differ from which, two post-hoc procedures were run: Games-Howell (pairs naturally with Welch's ANOVA, safe under unequal variance and unequal sample sizes) and Dunn's test with Holm correction (pairs with Kruskal-Wallis, rank-based, no distributional assumption at all). Across all 595 regional pairs, they agree closely — 90.8% and 89.1% significant respectively at p < 0.05 after correction — and the handful of non-significant pairs are almost all genuinely close neighbors in the ranking, or involve the division with the smallest tested sample (n = 172).

## Why is the within-division spread so high?

A coefficient of variation around 0.7–0.9 is high for output from a national forest inventory that's often described as statistically robust, and that's worth pausing on before trusting any single division's number too precisely.

![Figure 2. Coefficient of variation (sd/mean) of carbon density, one point per ecodivision, ordered left to right by ascending number of forested plots.](figures/h05_variance_by_division.png)

The first thing to check is whether this is simply a small-sample problem — do divisions with fewer plots just have noisier CV estimates? There's a real, if modest, tendency in that direction (Pearson r = -0.40 between CV and log(n), p = 0.017), but it's a loose relationship, not a tight one: division 321, with a middling plot count (774), has by far the highest CV in the dataset (2.10), well above what the trend line would predict.

![Figure 3. The same coefficients of variation plotted directly against the number of forested plots (log scale), with a least-squares trend line (CV regressed on log(n)) and the Pearson correlation annotated. Each point is one ecodivision, labeled by its division code.](figures/h06_cv_vs_nplots.png)

A more fundamental explanation is the sampling design itself. FIA's plot grid is designed and allocated to support **national and state-level** estimates — that's the geography its sampling intensity, stratification, and variance formulas are built around. Ecodivisions are a different geography: climate and physiography boundaries that cut across state and stratum lines, grouping plots by a criterion the sample design never optimized for. Regrouping the identical 125,123 forested plots by state instead of by ecodivision tests that directly:

![Figure 4. Coefficient of variation of carbon density, computed two ways from the same forested-plot pool: once grouped by ecodivision (35 groups) and once grouped by state (48 states with at least 100 forested plots). Box shows the IQR and median; points are individual divisions/states, jittered for visibility.](figures/h07_cv_division_vs_state.png)

Median CV is 0.84 at the ecodivision level versus 0.69 at the state level — a statistically significant difference (Mann-Whitney U, p = 0.015) — and it isn't a sample-size artifact: the two groupings have comparable plot counts per group (median 2,060 plots/division vs. 2,702 plots/state), so the gap can't be explained by ecodivisions simply having smaller samples. The most defensible reading is the one the sampling design itself suggests: state-level aggregation groups plots the way the inventory was built to support, while ecodivision-level aggregation groups them by climate and vegetation zone — a real and meaningful grouping, but one that concentrates more of the underlying plot-to-plot heterogeneity inside each group rather than averaging it away. **The takeaway isn't that ecoregion-level carbon estimates are wrong — it's that their uncertainty is structurally higher than a state-level number with a similar sample size, for reasons baked into the sample design rather than into any particular division's forest.**

## The result: carbon density by ecoregion

With that caveat in hand, mean carbon density ranges from about 2.8 tons/acre in the driest Tropical/Subtropical Steppe division to about 77 tons/acre on the central California coast — a 28-fold spread. The ranked pattern matches what you'd expect from forest-carbon geography: Pacific coast conifer forest and the Appalachians/Northeast carry the most carbon per acre; the semi-arid Southwest and southern Plains carry the least.

**Table 1. Ranked mean carbon density by ecodivision, with 95% confidence intervals**, highest to lowest. The 35 divisions above the line were included in the significance tests; one division (262) fell below the 100-plot threshold and is shown separately below the line.

| Division | Name | n plots | Mean (tons C/acre) | 95% CI |
|---|---|---|---|---|
| 263 | Mediterranean | 434 | 76.8 | 70.9–82.8 |
| M242 | Marine | 9,371 | 64.2 | 63.1–65.4 |
| 242 | Marine | 566 | 51.5 | 48.0–55.1 |
| M221 | Hot Continental | 5,882 | 45.9 | 45.3–46.6 |
| M261 | Mediterranean | 5,403 | 43.0 | 41.8–44.2 |
| 261 | Mediterranean | 172 | 40.9 | 33.2–48.6 |
| 221 | Hot Continental | 6,101 | 37.7 | 37.1–38.4 |
| M211 | Warm Continental | 3,887 | 35.3 | 34.7–35.8 |
| 211 | Warm Continental | 4,132 | 35.0 | 34.3–35.6 |
| 231 | Subtropical | 13,583 | 33.0 | 32.7–33.4 |
| 223 | Hot Continental | 6,441 | 32.1 | 31.6–32.6 |
| M333 | Temperate Desert | 3,645 | 31.1 | 30.3–31.9 |
| M223 | Hot Continental | 561 | 30.4 | 29.1–31.8 |
| 234 | Subtropical | 1,473 | 29.4 | 28.3–30.5 |
| 232 | Subtropical | 14,727 | 28.2 | 27.8–28.5 |
| M231 | Subtropical | 979 | 27.8 | 26.8–28.8 |
| 212 | Warm Continental | 12,445 | 26.1 | 25.8–26.5 |
| 222 | Hot Continental | 4,780 | 25.5 | 24.9–26.1 |
| M332 | Temperate Desert | 6,120 | 23.6 | 23.1–24.1 |
| 251 | Prairie | 2,252 | 22.1 | 21.4–22.8 |
| 411 | Savannah | 138 | 19.8 | 16.7–22.9 |
| M331 | Temperate Desert | 5,997 | 17.5 | 17.1–17.9 |
| 255 | Prairie | 1,316 | 15.5 | 14.8–16.1 |
| M334 | Temperate Desert | 362 | 14.5 | 13.4–15.6 |
| M313 | Tropical/Subtropical Steppe | 2,060 | 12.3 | 11.7–12.9 |
| 332 | Temperate Steppe | 551 | 11.8 | 10.7–12.9 |
| M262 | Mediterranean | 328 | 10.2 | 8.9–11.5 |
| 331 | Temperate Steppe | 1,339 | 9.0 | 8.4–9.5 |
| M341 | Temperate Desert | 2,240 | 8.6 | 8.3–9.0 |
| 342 | Temperate Desert | 1,111 | 8.4 | 7.8–9.0 |
| 313 | Tropical/Subtropical Steppe | 3,172 | 8.4 | 8.0–8.7 |
| 341 | Temperate Desert | 2,060 | 7.1 | 6.8–7.5 |
| 322 | Tropical/Subtropical Desert | 400 | 4.7 | 4.2–5.2 |
| 315 | Tropical/Subtropical Steppe | 300 | 2.8 | 2.4–3.2 |
| 321 | Tropical/Subtropical Steppe | 774 | 2.8 | 2.4–3.2 |
| *262* | *Mediterranean* | *21* | *13.3* | *6.6–20.0 (below the 100-plot test threshold; excluded from significance tests)* |

![Figure 5. The same pattern, mapped. Division boundaries are outlined in dark grey; state lines are the faint grey underneath, for reference only.](figures/h03_map_mean_carbon.png)

Worth flagging, given the previous section: the 95% CIs in Table 1 are plot-level confidence intervals (mean ± 1.96 × SE, from the raw plot-to-plot standard deviation and count) — exactly the quantity shown to be structurally wider at the ecodivision level than at the state level. They're a fair description of sampling uncertainty at this grouping, but a state-level or national rollup of the same underlying plots would carry tighter intervals for reasons that have nothing to do with any division's forest being less knowable.

## Where this series catches up with itself

Here's the part that sent me back to the first two posts. The highest-carbon divisions in this analysis aren't a random draw from the map — several of them are exactly the Pacific-coast and Mediterranean-climate divisions that [Part 2](https://pratyush-dh.github.io/projects/blog/htcd4/) showed carry almost all of the country's FIA-modeled (HTCD 4) heights. So each of the twelve highest-carbon divisions' carbon totals was split by the height method behind them: field-measured (HTCD 1), crew-estimated (HTCD 2/3, [Part 1](https://pratyush-dh.github.io/projects/blog/) of this series), or FIA's own model (HTCD 4, Part 2).

![Figure 6. The twelve highest-carbon divisions from Table 1, in the same rank order, split by the height method behind their carbon: field-measured (HTCD 1), crew-estimated (HTCD 2/3), or FIA-modeled (HTCD 4).](figures/h04_connector_htcd_share.png)

The pattern is not subtle. Division 263 — a Mediterranean-climate division on the California coast, and the single highest-carbon division anywhere in this analysis at 77 tons/acre — gets less than half its carbon (48.6%) from a tree with a field-measured height; another 43.2% rests on FIA's own HTCD 4 model. The Marine division along the Washington and Oregon coast (M242, the single largest division in this dataset at 9,371 plots and the second-highest by carbon density) draws 23% of its carbon from modeled heights, matching Part 2's finding that this exact region holds 99.3% of the nation's HTCD 4 trees. Meanwhile the Appalachian and eastern "Hot/Warm Continental" divisions that round out the top twelve by carbon density — 221, M211, 211 — draw essentially none of theirs from FIA's model (0.00–0.08%); the small remainder beyond field measurement is a crew visual estimate (Part 1), not an HTCD 4 imputation (84.2–92.2% HTCD 1, the rest HTCD 2/3).

To be precise about what this does and doesn't say: Part 2 found that FIA's own modeled heights are close to, not wildly different from, an independently-fit regional model, and the main study behind this whole series found that replacing modeled heights with an independent model moves national totals by well under half a percent. So this isn't evidence that the carbon numbers for the California coast are *wrong*. It's a second, independent reason — on top of the sampling-design argument above — that the plot-level confidence intervals in Table 1 understate the true uncertainty specifically for the divisions with the most carbon: those intervals carry no allowance for height-imputation uncertainty at all. The ecoregion with the most carbon at stake is also the one built most on height estimates rather than measurements, and the one where the grouping itself is least favorable to a tight estimate.

## What I take from this

- The regional differences in mean carbon density are real and statistically well-supported — not a one-test fluke, and not an artifact of skew or unequal variances, since four different tests on two different scales all agree.
- "Statistically significant" and "precisely known" aren't the same thing, for two independent reasons found here: ecodivision-level grouping is structurally noisier than state-level grouping for the same sample design, and the divisions with the most carbon at stake lean hardest on modeled rather than measured tree heights.
- Both of those reasons point the same direction — toward the Pacific coast and Mediterranean-climate divisions. If I were building a carbon-monitoring product on this data, I'd want an uncertainty band on those numbers specifically that's wider than the plot-sampling SE alone would suggest, and I'd rather quantify that than just footnote it.

## Limitations

- **Scope**: live-tree carbon only (`CARBON_AG` + `CARBON_BG`). Soil organic carbon, standing and down dead wood, litter, and understory vegetation carbon are all reported by FIA at the condition level but are not included here.
- **"Current evaluation" isn't one year**: each state's own most recent EXPCURR inventory cycle is used, consistent with the rest of this series, but that mixes inventory years across states rather than reflecting a single fixed national year.
- **The confidence intervals in Table 1 are plot-level, not design-based**: they come from the raw plot-to-plot mean and standard error, not from FIA's full post-stratified variance estimator (used elsewhere in this project for population totals). That choice is appropriate for comparing density across groupings, but it means the intervals shown don't include every source of uncertainty FIA's own published estimates would.
- **The ecodivision-vs-state CV comparison is descriptive, not a formal variance decomposition**: it's a Mann-Whitney comparison of two sets of group-level CVs, not a mixed-effects model partitioning variance into within-state and within-ecodivision components. It's consistent with — and the most parsimonious explanation for — the sampling-design argument made above, but it can't fully rule out that ecoregions are simply more ecologically heterogeneous than states as a matter of geography, independent of how the sample was designed.
- **Map labels and boundaries are generalized**: division codes are placed at each polygon's representative point, and the Cleland division polygons themselves are a coarse, generalized layer; fine-scale variation within a division isn't visible at this resolution.
- This is an independent analysis, not an official FIA product, and not peer reviewed. Corrections welcome.

## Data and code

This post builds on [Part 1](https://pratyush-dh.github.io/projects/blog/) and [Part 2](https://pratyush-dh.github.io/projects/blog/htcd4/) of this series — read those first for the HTCD background and the regional height model referenced above. Scripts, full result tables (every test statistic, all 595 pairwise comparisons, the state-level CV comparison, the division-by-HTCD carbon split) and print-quality figures for this post are in [`carbon_ecoregion`](https://github.com/pratyush-dh/projects/tree/main/blog/carbon_ecoregion). As with the rest of this series, this reads the public FIADB SQLite export directly — no database server needed to reproduce it.
