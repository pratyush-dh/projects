# Figure guide: what each figure shows, how to read it, and what it means

Notation used throughout. **HTCD 1** = height field-measured. **HTCD 2** = broken-top tree whose total height the crew reconstructed. **Regional model** = species × ecodivision Curtis–Arney/Wykoff height–diameter model fitted only on HTCD 1 trees of the 80% training plots. **Control** = intact HTCD 1 trees on the 20% plots the model never saw (the fair yardstick for "how far off is the model on a normal tree"). **ln ratio** = ln(height / model height); −0.03 is about 3% below the model. **ACTUALHT** = height of the standing part, **HT** = total height (standing part + missing piece).

The storyline of the set: (1) what the height columns mean and where they are not measured → (2) how well a model trained on measured trees predicts → (3) how the crews' broken-top heights compare with it, overall and by region → (4) the missing piece and the stump height, with the traps → (5) an independent reference (the tree's earlier measured height) → (6) what it means for volume and biomass.

---

## Blog figures

### Fig 1. Height columns of the FIA tree table (schematic)
**Represents.** Three trees: intact (crew measures HT, HTCD 1); broken top (ACTUALHT measured, missing piece added by measurement or estimate, HTCD 2 or 3); height not taken in the field (model fills HT in, HTCD 4).
**Purpose.** Give readers the vocabulary before any result.
**Read it.** Arrows are the quantity each column holds; the dashed crown is the part that is gone.
**Message.** The single column HT mixes measurements, crew judgements and model output; HTCD is the only way to tell them apart.

### Fig 2. Where heights are not measured (study-area figure)
**Represents.** (a) Number of field-measured live trees per ecodivision available for training (log colour scale, 10⁴ to about 2 × 10⁶). (b) Share of live trees with a model-derived height (HTCD 4), by state. (c) Share with a crew-estimated height (HTCD 2 or 3).
**Purpose.** Show that the two kinds of non-measured heights have different geographies and that measured training data are unevenly spread.
**Read it.** Darker = more. In (a) yellow = plenty of measured trees (Southeast, Lake States), dark blue = few (California, the interior West and Southwest, the central Plains, southern Florida).
**Results.** Modeled heights are essentially confined to Alaska, California, Oregon and Washington (99.4% of HTCD 4 tree records); crew estimates are most frequent in the Northeast. Training data are thinnest in California and the interior West.
**Discussion.** The model-derived heights are concentrated where measured training data are scarce, so any model refitted on measured trees will be least certain exactly where imputation matters most. Alaska and Hawaii have no ecodivision assignment and are outside the modeling.

### Fig 3. The regional models and the data behind them
**Represents.** Four of the largest species × ecodivision groups (Douglas-fir and western hemlock in the Pacific Marine division M242; sweetgum in the Subtropical divisions 231 and 232). Top row: intact measured trees on unseen plots (grey) with the fitted curve (orange). Bottom row: crew-reconstructed HTCD 2 trees (blue) with the same curve. Panel titles give the held-out RMSE of each model.
**Purpose.** Show what "the regional model" is, and how HTCD 2 heights sit relative to it.
**Read it.** The orange curve is the model's expected total height at a given diameter. Points scattered around it are individual trees; the vertical spread is the model's error.
**Results.** Both groups scatter around the same curve. The spread depends on the group: RMSE about 9.4 ft for sweetgum, 15.5 ft for western hemlock and 20.2 ft for Douglas-fir in M242 (very tall trees). Crew heights above about 100 ft form horizontal stripes at multiples of 10 ft (and 5 ft lower down); the measured trees do not.
**Discussion.** The stripes are the visible sign of visual estimation (rounding). The model's uncertainty is large relative to the effects being tested, which sets the noise floor for everything that follows.

### Fig 4. Crew heights vs the model, overall
**Represents.** (Left) Mean height relative to the model prediction (% difference) by diameter class, for intact measured trees (grey) and crew-reconstructed trees (blue, with 95% plot-clustered confidence intervals). (Right) Distribution of ln(height / model height) for the two groups.
**Purpose.** Answer the first question: do crews and the model agree on average, and is the spread different?
**Read it.** Zero = same as the model. Left: distance between blue and grey is the "excess" difference for broken-top trees. Right: horizontal shift = bias, width = scatter.
**Results.** Crew heights are about 3.1% below the model relative to the control (95% interval 3.0–3.3%); the gap is about 1% for saplings and 3–5% for every class above 5 inches (largest for 20–30 inches). The distributions almost overlap: standard deviation of the ln ratio is 0.22 for both.
**Discussion.** The average difference is small compared with the scatter; the disagreement between an individual crew estimate and the model is about as large as the model's own error on ordinary trees. This figure cannot say who is right.

### Fig 5. Residual box plots
**Represents.** Residuals (height minus model height) as box plots for control (grey) and HTCD 2 (blue): relative (ln ratio) and in feet by diameter class, and relative for the 12 ecodivisions with most HTCD 2 trees.
**Purpose.** Show the full distribution, not just means, and check that the pattern is a shift and not a change of shape.
**Read it.** Box = 25th–75th percentile, white line = median, whiskers = 5th–95th percentile. A blue box lower than the grey one means crews are below the model.
**Results.** The medians of HTCD 2 sit slightly below the control in every class and division, with similar box widths. Residuals in feet get wider with tree size (a few feet for saplings, tens of feet for the largest trees).
**Discussion.** A relative error model (multiplicative) is appropriate: the same percentage error means a larger number of feet for big trees. The bias is a small downward shift, largest in the eastern and Appalachian divisions.

### Fig 6. Ecodivision maps: model error, model bias, crew bias, excess bias
**Represents.** Four maps by ecodivision. (a) Model RMSE on intact trees in feet (teal, darker = larger). (b) Model bias on intact trees in %: red = measured taller than model (model under-predicts), blue = the reverse. (c) HTCD 2 height relative to the model (%). (d) Excess bias = (c) minus (b); hatching = the 95% interval includes zero. Grey = too few trees.
**Purpose.** Separate the model's own regional bias from what is specific to broken-top trees/crews.
**Read it.** Look at (d) for the crew effect and at (b) for what would otherwise be misread as a crew effect.
**Results.** (a) Errors are largest on the Pacific coast (dark) and smallest in the Southwest. (b) The model under-predicts across the interior West by up to 2–3% and over-predicts in coastal California. (c)–(d) Crews are lower than the model in most of the country, most strongly in the Appalachian, eastern broadleaf and northern mixed-forest divisions (M211, M221, 221, 211: about −4 to −5.4 percentage points) and in a few small interior-West divisions (for example 342, about −11 points but only 307 trees); the significantly positive areas are the Arizona–New Mexico steppe (313, about +4.6 points, about 1,000 trees) and the small division M334. 21 of 37 divisions differ significantly from zero.
**Discussion.** Regional models are not equally good everywhere, so crew–model gaps must be read relative to intact trees of the same region. Hatched areas (much of the Plains and parts of the Intermountain West) show no detectable difference. Regions with few HTCD 2 trees have wide uncertainty.

### Fig 7. The broken piece: crew vs model, and both vs the earlier measurement
**Represents.** Missing length (feet) = HT − ACTUALHT. Top row, by diameter group: crew-imputed missing length (x) vs the missing length the model implies, HT_hat − ACTUALHT (y). Bottom row: both against the missing length implied by the same tree's earlier measured intact height (grown forward). Sampled points; line = median, band = interquartile range, dotted = 5th–95th percentile; dashed = 1:1.
**Purpose.** Show the imputed broken part itself and how it compares with the model and with an independent reference.
**Read it.** On the dashed line the two agree. Lines below it mean the y-quantity is smaller than the x-quantity.
**Results.** Crew and model missing lengths are rank-correlated at 0.66, 0.64 and 0.56 (under 10 in, 10–20 in, over 20 in); the model implies a negative missing length (a tree shorter than its own stump) for 13–15% of trees. Against the earlier measured missing length, crews overstate very short breaks (about 5 ft reported for a true 3 ft) and understate longer ones by roughly 12–19%; the model does the same and is worse for long breaks (about 25% short at a true 67 ft).
**Discussion.** Two facts hide behind this plot: (1) HT − ACTUALHT vs HT_hat − ACTUALHT differ by exactly HT − HT_hat, so "missing length" comparison is the total-height comparison; (2) a diameter-only model is loose for a single tree. The bottom row is the informative part.

### Fig 8. A severity trend appears even when the crew is perfect
**Represents.** Mean ln(crew height / model height) against the percentile rank of stump height within its 2-inch diameter class. Grey: intact trees ranked on their own height. Blue: HTCD 2 ranked on stump height. Orange diamonds: a simulation in which the crew is perfectly accurate but the model has the same error.
**Purpose.** Demonstrate that the tempting "crews behave differently for tall stumps" plot is uninformative on its own.
**Read it.** If all three curves rise together, the rise is produced by the model, not by crew behavior.
**Results.** All three rise from about −0.14 at the lowest ranks to about +0.2 at the highest; HTCD 2 lies about 0.05 below the control across ranks (the small excess seen in Fig 4).
**Discussion.** A tall stump belongs to a tall tree, and a model that only sees diameter under-predicts tall trees; the ratio and rank axes share the model error with the y-axis. Any trend against stump height needs a benchmark or an independent reference (Fig 9).

### Fig 9. Stump height: benchmark (top) and test against the earlier measurement (bottom)
**Represents.** Three columns = diameter groups. Top: crew-minus-model missing length (ft) by stump-height rank, with intact trees as the benchmark (grey). Bottom: error of the crew's total height (blue) and of the model's total height (orange) against the tree's own earlier measured height, by stump height (ft); positive = overestimate; band = 95% plot-clustered interval. Only trees whose HT differs from the earlier recorded HT.
**Purpose.** Answer "do crews over- or underestimate when they see a tall stump?".
**Read it.** The bottom row is the test: a flat line at zero = no relation with stump height. Top row: HTCD 2 below grey = crews lower than the model beyond what any tree would show.
**Results.** Crew error is flat: about −1 ft (trees under 10 in), about 0 (10–20 in), +3 to +5 ft (over 20 in), at every stump height. Model error falls from +3, +7 and +20–25 ft for the shortest stumps to −15, −18 and −27 ft for the tallest.
**Discussion.** The dependence on stump height belongs to the model. Crews do not detectably over- or under-estimate as a function of stump height. Caveat: crews may see the earlier recorded height, so flat lines are an upper bound on their independent accuracy. Also note the selection trap: restricting to pairs with earlier height above the stump produces a spurious under-estimate for tall stumps.

### Fig 10. Stump height relative to what the model expects
**Represents.** (Left) Error against the earlier measured height (ft) by ACTUALHT / model height (< 0.5 to > 1.3); crew (blue, with 95% interval), model (orange). (Middle) trees per bin. (Right) Mean missing length: earlier measured (grey) vs crew-imputed (blue).
**Purpose.** Repeat the tall-stump test on a scale that already accounts for diameter: a ratio above 1 = the stump is already taller than the model expects for that diameter.
**Read it.** Left: flat blue line = crews unaffected. Right: bars of the same height = crews reproduce the missing length.
**Results.** Crew error stays between −0.7 and −0.2 ft in every bin; model error goes from +5 ft to −24 ft. Mean missing length falls from about 27 ft (short stumps) to about 5 ft (tall), and the crew value is 0.4–0.7 ft below the measured one in every bin (27.1 vs 27.7 ft; 4.8 vs 5.4 ft).
**Discussion.** The model line shares HT_hat with the x-axis, so its slope is partly mechanical (flagged in the legend); the crew line does not, which is why it can be interpreted. Middle panel: fewest trees at the extremes, so those points are less stable.

### Fig 11. Against the earlier measurement, and copied values
**Represents.** (Left) Typical error (RMSE, %) against the tree's own earlier measured height by diameter class: crew (blue), model (orange), and the error of a fresh field measurement of an intact tree vs its own earlier measurement (dashed, about 17%). (Right) Share of HTCD 2 trees whose current HT is identical to the earlier recorded HT, by inventory period (grey line = 8% for measured trees).
**Purpose.** Provide an independent reference for "who is closer" and expose a limitation of that reference.
**Read it.** Left: shorter bar = closer to the earlier measurement. Right: taller bar = more copied values.
**Results.** Crew RMSE is about 19% against 26% for the model; crew is closer than the model for about two of three trees, in every class and era. But 37% of HTCD 2 trees with an earlier record have an identical height (against 8% for measured trees), rising from 20% before 2005 to 53% since 2020; 44% of HTCD 2 heights are multiples of 5 ft (23% for measured trees).
**Discussion.** Crews are consistent with the past, and much more than the model. But since the crew may see the previous value, this is not proof of independent accuracy. The identical cases were excluded from the left panel; adjusted-but-anchored values remain.

---

## Additional figures (in `side_htcd2/figures`, not in the blog draft)

### Fig 5 (side project): Bias by ecodivision
**Represents.** Left: mean height relative to the model in each ecodivision (n ≥ 500 HTCD 2 trees) for intact trees (grey) and HTCD 2 (blue), joined by a line. Right: the difference (excess bias, %) with 95% interval and sample size; blue = significantly lower than the model, red = significantly higher, grey = no detectable difference.
**Purpose.** The numerical version of the maps.
**Results.** Most divisions are blue (−2 to −5%); Marine M242 (n = 31,173) −3.0%; M211, M221 and 221 the largest among the well-sampled ones (−4 to −5.4); 342 is lower still (−11) but has only 307 trees; the only well-sampled red one is 313 (+4.6). Left panel shows that in the interior-West divisions the model itself is off for intact trees, so the raw crew gap there would be misleading.

### Fig 9 (side project): Excess bias by ecodivision and diameter class (heatmap)
**Represents.** Cell = excess bias (percentage points) of HTCD 2 over control for a division × diameter class; blue = crews lower, red = higher; blank = fewer than 100 trees in a group.
**Results.** The eastern divisions (211, 212, 221, 222, 223, M211, M221, 231, 232) go from about 0 to −5 for saplings to −6 to −12 at 20–30 in. The steppe and prairie divisions (313, 251, 255) are positive for saplings (+5 to +7) and near zero above.
**Discussion.** The overall 3% is an average of very different behavior by size; large broken trees in the East are where crews are lowest relative to the model.

### Fig 7 (side project): State maps
**Represents.** (a) Excess bias by state (hatched = not significant); (b) HTCD 2 trees per state (log); (c) share of HTCD 2 heights identical to the earlier recorded height; (d) crew height vs earlier measured height (%; states with ≥ 200 pairs).
**Results.** Arizona is the clearest positive state (+5.6 points), followed by Kansas (+3.3) and Illinois (+2.3); the lowest are Vermont (−8.6), Florida (−7.4), Virginia and New Hampshire (both about −6.8), and Connecticut and Massachusetts (about −6.4). Copied heights are most common in Arizona (89% of HTCD 2 trees with an earlier record; 568 pairs), Wyoming, New Mexico, Kentucky, Utah and Montana (all above 65%, some with small samples) and least common in Illinois, Mississippi, West Virginia and Maine (about 8–14%). In (d) crews are within a few percent of the earlier measured height in almost every state with enough pairs.
**Discussion.** States where copying is common are where the earlier-measurement comparison is least independent.

### Fig 8 (side project): Ecodivision maps against the earlier measurement
**Represents.** (a) Crew height vs earlier measured height (%), (b) model height vs earlier measured (%), (c) ratio of model error to crew error (RMSE ratio, teal; above 1 = crew closer).
**Results.** The model is off by more than 5% in the same regions where it was biased in Fig 6 (interior West), while crews are within a few percent nearly everywhere; the RMSE ratio is above 1 wherever there are enough pairs, highest (up to about 2) in the Pacific, Rocky Mountain, Southwest and Texas divisions.
**Discussion.** Even there the reference is the earlier recorded height (see Fig 11 caveat).

### Fig 11 (side project): Inventory of the regional models
**Represents.** Per ecodivision: number of training trees (log scale) and number of species models (left); pooled held-out RMSE (right).
**Results.** Southeastern divisions (231, 232) have the most training data (over 10⁶ trees, 105–109 species models); Pacific divisions have the largest RMSE (about 15–16 ft in M242, 263 and 242), the Southwest the smallest (about 4–6 ft).
**Discussion.** RMSE in feet depends on the size of trees in a region (tall Pacific trees), so it is not a like-for-like quality ranking.

---

## Manuscript-level results behind the volume and biomass section (table, not figure)
National aboveground biomass change after replacing all non-measured heights: −0.117% with regional models (95% CI −0.143 to −0.090), −0.226% with national per-species models, +0.114% after retransformation-bias correction; replacing only model heights (HTCD 4) −0.127%, only crew estimates (HTCD 2–3) +0.010%. On trees with known measured heights (held-out check), diameter-only models understate biomass by 1.0–2.8% and volume by 1.5–3.9%, and the bias grows with inventory year (heights measured after 2020 are on average 2.3 ft above the prediction, versus 0.1 ft before 2000).
