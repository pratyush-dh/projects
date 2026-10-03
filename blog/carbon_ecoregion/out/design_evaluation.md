# FIA design-based evaluation of live-tree carbon density (latest EXPCURR evaluation per state)

Estimator: FIA post-stratified ratio estimator (Bechtold & Patterson 2005; Scott et al. 2005, eq. 4.14), with plot values
per acre of plot, strata and EXPNS from POP_STRATUM, and ratio variance by delta method. Domains are ecodivisions
(Cleland) and states. Plots without an ecodivision (Alaska, Hawaii, Pacific islands, territories, and plots inside the
"Water" polygons) form an "NA" domain. Units: tons C (short tons) and tons C per forested acre.

## 1. Aggregation identities (internal consistency)

| Quantity | Value |
|---|---|
| States summed (58 units, all latest evaluations) | 20,445.78 M tons C |
| Ecodivisions summed + NA domain | 20,445.78 M tons C (difference 4e-6) |
| Ecodivisions only (excluding NA) | 19,752.29 M tons C |
| NA domain (AK, HI, Pacific islands, territories, Water-polygon plots) | 693.49 M tons C |
| Independent aboveground + belowground recomputation | 20,445.78 M tons C (matches exactly) |
| National forested acres | 706.71 M acres |
| National mean density | 28.93 tons C / forested acre (SE 0.061, 95% CI 28.81-29.05) |
| National total standard error | 43.78 M tons C (0.21% of total) |
| Conterminous US only (48 units) | 19,822.45 M tons C; 689.73 M acres; 28.74 tons C/acre |

The state and ecodivision totals agree exactly because every plot belongs to exactly one stratum, one state, and at most one
ecodivision. The national total is therefore the same whether it is built from states or from ecodivisions.

## 2. Comparison with published national aboveground live-tree carbon

| Quantity | This analysis | Published reference | Note |
|---|---|---|---|
| Aboveground live-tree carbon, all units | 17,133.8 M short tons = 15,543.5 M metric t | 14,312 M metric t (Forest Service report, year and NSVB version not identified) | +8.6%. The reference predates or differs in tree-carbon method and evaluation years; not verified as like-for-like. |
| Belowground live-tree carbon, all units | 3,312.0 M short tons | not retrieved | belowground is 16.2% of AG+BG |

No year-matched official EVALIDator national carbon total for this set of evaluations was retrievable, so the comparison above
is the closest available reference, not a validated benchmark.

## 3. Design-based ecodivision estimates (mean, SE, 95% CI, spread)

| Division | Name | n forested plots | Forest acres (M) | Total (M tons C) | Mean (t C/acre) | SE | 95% CI | wCV |
|---|---|---|---|---|---|---|---|---|
| 263 | Mediterranean | 434 | 2.93 | 220.9 | 75.44 | 2.81 | 69.9-81.0 | 0.82 |
| M242 | Marine | 9,371 | 30.41 | 1,775.1 | 58.37 | 0.51 | 57.4-59.4 | 0.90 |
| 242 | Marine | 566 | 3.40 | 157.0 | 46.13 | 1.54 | 43.1-49.2 | 0.84 |
| M221 | Hot Continental | 5,882 | 32.55 | 1,416.7 | 43.53 | 0.31 | 42.9-44.1 | 0.55 |
| 261 | Mediterranean | 172 | 1.19 | 48.6 | 40.82 | 3.75 | 33.5-48.2 | 1.27 |
| M261 | Mediterranean | 5,403 | 29.70 | 1,159.9 | 39.05 | 0.50 | 38.1-40.0 | 1.08 |
| 221 | Hot Continental | 6,101 | 40.50 | 1,532.9 | 37.85 | 0.30 | 37.3-38.4 | 0.64 |
| M211 | Warm Continental | 3,887 | 22.25 | 775.9 | 34.88 | 0.28 | 34.3-35.4 | 0.54 |
| 211 | Warm Continental | 4,132 | 26.46 | 918.0 | 34.70 | 0.30 | 34.1-35.3 | 0.61 |
| 231 | Subtropical | 13,583 | 80.86 | 2,622.2 | 32.43 | 0.18 | 32.1-32.8 | 0.67 |
| 223 | Hot Continental | 6,441 | 39.15 | 1,224.9 | 31.29 | 0.23 | 30.8-31.7 | 0.64 |
| M223 | Hot Continental | 561 | 3.42 | 103.8 | 30.36 | 0.63 | 29.1-31.6 | 0.52 |
| M333 | Temperate Desert | 3,645 | 19.97 | 599.8 | 30.03 | 0.38 | 29.3-30.8 | 0.82 |
| 234 | Subtropical | 1,473 | 9.18 | 269.1 | 29.32 | 0.54 | 28.3-30.4 | 0.75 |
| M231 | Subtropical | 979 | 6.00 | 166.3 | 27.70 | 0.46 | 26.8-28.6 | 0.58 |
| 232 | Subtropical | 14,727 | 85.55 | 2,360.6 | 27.59 | 0.17 | 27.3-27.9 | 0.76 |
| 222 | Hot Continental | 4,780 | 22.82 | 626.5 | 27.45 | 0.33 | 26.8-28.1 | 0.82 |
| 212 | Warm Continental | 12,445 | 46.35 | 1,207.6 | 26.05 | 0.16 | 25.7-26.4 | 0.70 |
| 251 | Prairie | 2,252 | 14.74 | 336.1 | 22.79 | 0.34 | 22.1-23.5 | 0.78 |
| M332 | Temperate Desert | 6,120 | 28.47 | 622.7 | 21.88 | 0.25 | 21.4-22.4 | 0.91 |
| 411 | Savannah | 138 | 1.27 | 25.0 | 19.66 | 1.32 | 17.1-22.3 | 0.94 |
| M331 | Temperate Desert | 5,997 | 37.79 | 653.5 | 17.29 | 0.17 | 17.0-17.6 | 0.87 |
| 255 | Prairie | 1,316 | 8.43 | 131.2 | 15.57 | 0.31 | 15.0-16.2 | 0.78 |
| M334 | Temperate Desert | 362 | 2.02 | 29.5 | 14.61 | 0.50 | 13.6-15.6 | 0.74 |
| 262 | Mediterranean | 21 | 0.14 | 1.9 | 13.01 | 3.10 | 6.9-19.1 | 1.13 |
| 332 | Temperate Steppe | 551 | 3.63 | 43.7 | 12.02 | 0.50 | 11.0-13.0 | 1.08 |
| M313 | Tropical/Subtropical Steppe | 2,060 | 13.37 | 155.3 | 11.62 | 0.24 | 11.1-12.1 | 1.12 |
| M262 | Mediterranean | 328 | 2.20 | 22.4 | 10.22 | 0.63 | 9.0-11.5 | 1.15 |
| 331 | Temperate Steppe | 1,339 | 9.57 | 84.0 | 8.77 | 0.25 | 8.3-9.3 | 1.15 |
| M341 | Temperate Desert | 2,240 | 13.69 | 118.4 | 8.65 | 0.16 | 8.3-9.0 | 0.94 |
| 342 | Temperate Desert | 1,111 | 6.46 | 54.0 | 8.36 | 0.30 | 7.8-9.0 | 1.28 |
| 313 | Tropical/Subtropical Steppe | 3,172 | 20.08 | 165.1 | 8.22 | 0.15 | 7.9-8.5 | 1.15 |
| 341 | Temperate Desert | 2,060 | 12.61 | 91.5 | 7.26 | 0.18 | 6.9-7.6 | 1.18 |
| 322 | Tropical/Subtropical Desert | 400 | 2.79 | 12.7 | 4.55 | 0.22 | 4.1-5.0 | 1.09 |
| 315 | Tropical/Subtropical Steppe | 300 | 2.56 | 6.9 | 2.70 | 0.17 | 2.4-3.0 | 1.22 |
| 321 | Tropical/Subtropical Steppe | 774 | 5.00 | 12.8 | 2.56 | 0.17 | 2.2-2.9 | 2.06 |

Ecodivision totals (excluding NA) sum to 19,752.3 M tons C over 687.5 M forested acres, matching Section 1.

## 4. Design weighting versus the earlier unweighted means

The published post (Table 2) reports unweighted plot means. Design weighting moves several division means by up to 10.5%, the bound stated in the
earlier README. The largest changes are:

- M242 Marine: 64.2 (unweighted) to 58.4 (design-weighted), -9.1%.
- 263 Mediterranean: 76.8 to 75.4, -1.8%.
- 242 Marine: 51.5 to 46.1, -10.5%.
- 261 Mediterranean: 40.9 to 40.8, -0.2%.

The design-weighted means are the defensible per-acre estimates for the regional comparison, since they account for
differing sampling intensity across strata. The published Table 2 should be revised before it is cited as a design
estimate.

## 5. Spread (wCV) by level, design-weighted

Restricted to forested plots with an assigned ecodivision (same universe as the published analysis), divisions and states
with at least 100 forested plots:

| Level | n units | Median wCV | Median unweighted CV |
|---|---|---|---|
| Ecodivision | 35 | 0.836 | 0.841 |
| State | 48 | 0.702 | 0.693 |
| National (all such plots) | 1 | 0.930 | 0.960 |

Mann-Whitney test, ecodivision vs. state design-weighted wCV: p = 0.013 (unweighted: p = 0.015). The conclusion that
ecodivision-level spread exceeds state-level spread is unchanged by design weighting.

## 6. Limitations of this evaluation

- The external benchmark is an undated published aboveground figure, not a year-matched EVALIDator total. The 8.6%
  difference cannot be attributed to a specific cause from the available information.
- The ratio variance is a delta-method approximation. Strata with fewer than two plots contribute no within-stratum variance,
  so variances are slightly understated for those units.
- The national SE covers sampling error only, not the NSVB model error or the height-imputation uncertainty discussed in
  Parts 1 and 2.
- National aggregation treats estimation units as independent across states, following the project's convention in
  paper/06_design_variance.py.
