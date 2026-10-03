#!/usr/bin/env python3
"""Carbon-by-ecoregion, step 5: design-based (FIA post-stratified) estimates of live-tree carbon per forested acre
by state and by ecodivision, national aggregation two ways, and design-weighted spread (sd/mean).

Estimator follows paper/06_design_variance.py (Bechtold & Patterson 2005, ch. 4; Scott et al. 2005, eq. 4.14):
per estimation unit u, strata h with n_h plots and EXPNS_h acres per plot, A = sum_h EXPNS_h n_h, W_h = EXPNS_h n_h / A:
    total_hat(v)  = sum_h EXPNS_h sum_j v_hj
    Cov(total)    = A^2 [ (1/n) sum_h W_h S_h + (1/n^2) sum_h (1 - W_h) S_h ],  S_h = sample covariance in stratum h
Plot variables v are tons C per acre of plot (y) and a forest indicator (x), each split by ecodivision domain, so
domain totals are domain estimates (domain indicator, full-stratum n_h). Forest-acre ratio R = Y/X with delta-method
variance. Estimation units are independent; states aggregate by summing unit totals and covariances.

Spread: design-weighted sd/mean of plot carbon density over forested plots, weights EXPNS (acres each plot represents).
Outputs: out/d1_state_design.csv, out/d2_division_design.csv, out/d3_national.json, out/d4_spread_by_level.csv
"""
import json
import numpy as np, pandas as pd, geopandas as gpd

MIN_N = 100
pc = pd.read_csv("data/plot_carbon.csv", dtype={"plt_cn": "str", "estn_unit": "str", "stratumcd": "str"}, low_memory=False)
coords = pd.read_csv("../paper/data/plot_coords.csv", dtype={"plt_cn": "str"}, low_memory=False)
names = gpd.read_file("../paper/data/eco_divisions_5070.gpkg")[["division_code", "division_name"]].drop_duplicates("division_code")
st_names = gpd.read_file("../paper/data/states-10m.json", layer="states")[["id", "name"]]
st_names["statecd"] = st_names.id.astype(int)
st_names = pd.concat([st_names[["statecd", "name"]], pd.DataFrame(
    {"statecd": [64, 68, 70], "name": ["Federated States of Micronesia", "Marshall Islands", "Palau"]})])

pc = pc.merge(coords[["plt_cn", "division"]], on="plt_cn", how="left")
pc["division"] = pc.division.fillna("NA").replace({"Water": "NA"})
pc["y"] = pc.carbon_tons_acre
pc["x"] = (pc.carbon_tons_acre > 0).astype(float)
print(f"{len(pc):,} plots, {(pc.x > 0).sum():,} forested, {pc.estn_unit.nunique()} estimation units")

DOMS = sorted(pc.division.unique())
K = 2 * len(DOMS)
dix = {d: i for i, d in enumerate(DOMS)}


def unit_matrix(g):
    """plot x K matrix: columns [y*1(d), x*1(d)] for each domain d."""
    M = np.zeros((len(g), K))
    di = g.division.map(dix).values
    M[np.arange(len(g)), 2 * di] = g.y.values
    M[np.arange(len(g)), 2 * di + 1] = g.x.values
    return M


def unit_totals_cov(g):
    strata = g.groupby("stratumcd")
    n_h = strata.size().values.astype(float)
    E = strata.expns.first().values.astype(float)
    A = float((E * n_h).sum()); n = n_h.sum(); W = E * n_h / A
    M = unit_matrix(g)
    codes = g.stratumcd.values
    T = np.zeros(K); C = np.zeros((K, K))
    for hi, code in enumerate(strata.groups.keys()):
        idx = np.where(codes == code)[0]
        T += E[hi] * M[idx].sum(0)
        if len(idx) >= 2:
            S = np.cov(M[idx].T, ddof=1)
            C += A ** 2 * (W[hi] * S / n + (1 - W[hi]) * S / n ** 2)
    return T, C, len(g), len(n_h), int((n_h < 2).sum())


def ratio_se(T, C, iy, ix):
    """ratio R = sum(T[iy]) / sum(T[ix]) and its delta-method SE from the covariance matrix C."""
    Yn = T[iy].sum(); Xd = T[ix].sum()
    g = np.zeros(K); g[iy] = 1.0 / Xd; g[ix] = -Yn / Xd ** 2
    return Yn / Xd, np.sqrt(max(g @ C @ g, 0))


def dom_idx(d):
    i = dix[d]; return [2 * i], [2 * i + 1]


def all_idx():
    return [2 * i for i in range(len(DOMS))], [2 * i + 1 for i in range(len(DOMS))]


# --------------------------------------------------------------- estimate per state (sum over its units)
st_T, st_C, st_n, st_nstr, st_small = {}, {}, {}, {}, {}
for st, gs in pc.groupby("statecd"):
    T = np.zeros(K); C = np.zeros((K, K)); n = nstr = small = 0
    for _, gu in gs.groupby("estn_unit"):
        t, c, n_, h_, s_ = unit_totals_cov(gu)
        T += t; C += c; n += n_; nstr += h_; small += s_
    st_T[st], st_C[st], st_n[st], st_nstr[st], st_small[st] = T, C, n, nstr, small

# --------------------------------------------------------------- weighted spread (design weights = EXPNS)
def weighted_cv(v, w):
    mu = np.average(v, weights=w)
    var = np.average((v - mu) ** 2, weights=w)
    return mu, np.sqrt(var), np.sqrt(var) / mu

fp = pc[pc.x > 0]
rows = []
iy_all, ix_all = all_idx()
for st, gs in pc.groupby("statecd"):
    T, C = st_T[st], st_C[st]
    Yt, Xt = T[iy_all].sum(), T[ix_all].sum()
    R, se = ratio_se(T, C, iy_all, ix_all)
    f = fp[fp.statecd == st]
    mu_w, sd_w, cv_w = weighted_cv(f.y.values, f.expns.values)
    mu_u, sd_u, cv_u = f.y.mean(), f.y.std(), f.y.std() / f.y.mean()
    rows.append(dict(statecd=st, n_plots=st_n[st], n_forest=len(f), n_strata=st_nstr[st], n_strata_lt2=st_small[st],
                     forest_acres_M=Xt / 1e6, total_MMT_C=Yt / 1e6, mean_tC_per_acre=R, se_mean=se,
                     ci_lo=R - 1.96 * se, ci_hi=R + 1.96 * se, wmean=mu_w, wsd=sd_w, wcv=cv_w,
                     unweighted_mean=mu_u, unweighted_cv=cv_u))
d1 = pd.DataFrame(rows).merge(st_names, on="statecd", how="left")
d1.to_csv("out/d1_state_design.csv", index=False)

# --------------------------------------------------------------- ecodivision domain estimates (summed over states)
Tn = sum(st_T.values());
Cn = np.zeros((K, K))
for st in st_C: Cn += st_C[st]          # states independent: block-diagonal sum
drows = []
for d in DOMS:
    if d == "NA":
        continue
    iy, ix = dom_idx(d)
    Yd, Xd = Tn[iy][0], Tn[ix][0]
    R, se = ratio_se(Tn, Cn, iy, ix)
    f = fp[fp.division == d]
    mu_w, sd_w, cv_w = weighted_cv(f.y.values, f.expns.values)
    drows.append(dict(division=d, n_forest=len(f), n_plots_all=int((pc.division == d).sum()),
                      forest_acres_M=Xd / 1e6, total_MMT_C=Yd / 1e6, mean_tC_per_acre=R, se_mean=se,
                      ci_lo=R - 1.96 * se, ci_hi=R + 1.96 * se, wmean=mu_w, wsd=sd_w, wcv=cv_w,
                      unweighted_mean=f.y.mean(), unweighted_cv=f.y.std() / f.y.mean()))
d2 = pd.DataFrame(drows).merge(names, left_on="division", right_on="division_code", how="left").drop(columns="division_code")
d2.to_csv("out/d2_division_design.csv", index=False)

# --------------------------------------------------------------- national: aggregate states and divisions, check identities
Y_states = sum(st_T[s][iy_all].sum() for s in st_T)
Y_divs = sum(Tn[dom_idx(d)[0]][0] for d in DOMS if d != "NA")
Y_na = Tn[dom_idx("NA")[0]][0]
X_states = sum(st_T[s][ix_all].sum() for s in st_T)
nat_R, nat_se = ratio_se(Tn, Cn, iy_all, ix_all)
div_idx = [2 * dix[d] for d in DOMS if d != "NA"]
div_idx_x = [2 * dix[d] + 1 for d in DOMS if d != "NA"]
Yd_sum = Tn[div_idx].sum(); Xd_sum = Tn[div_idx_x].sum()
a = np.zeros(K); a[div_idx] = 1.0
var_Yd_sum = a @ Cn @ a
CONUS = [s for s in st_T if s not in (2, 15) and s <= 56]
conus_Y = sum(st_T[s][iy_all].sum() for s in CONUS); conus_X = sum(st_T[s][ix_all].sum() for s in CONUS)
nat = dict(
    conus_states=len(CONUS), conus_total_MMT_C=float(conus_Y / 1e6), conus_forest_acres_M=float(conus_X / 1e6),
    conus_mean_tC_per_forest_acre=float(conus_Y / conus_X),
    n_states=len(st_T), n_plots_all=int(pc.shape[0]), n_forest_all=int((pc.x > 0).sum()),
    national_total_MMT_C_all_states=float(Y_states / 1e6),
    national_total_MMT_C_sum_divisions_plus_NA=float((Y_divs + Y_na) / 1e6),
    national_total_MMT_C_sum_divisions_only=float(Y_divs / 1e6),
    national_total_MMT_C_NA_domain=float(Y_na / 1e6),
    national_forest_acres_M=float(X_states / 1e6),
    national_mean_tC_per_forest_acre=float(nat_R), national_mean_se=float(nat_se),
    national_mean_ci_lo=float(nat_R - 1.96 * nat_se), national_mean_ci_hi=float(nat_R + 1.96 * nat_se),
    national_total_se_MMT=float(np.sqrt(np.array([1.0 if i in iy_all else 0.0 for i in range(K)]) @ Cn @
                                        np.array([1.0 if i in iy_all else 0.0 for i in range(K)])) / 1e6),
    divisions_only_total_se_MMT=float(np.sqrt(var_Yd_sum) / 1e6),
    state_sum_check_diff=float(Y_states - (Y_divs + Y_na)),
)
json.dump(nat, open("out/d3_national.json", "w"), indent=1)
print(json.dumps(nat, indent=1))

# --------------------------------------------------------------- spread at each level, design-weighted
lv = []
fpd = fp[fp.division != "NA"]
for name, grp, w_col in [
    ("state", fpd.groupby("statecd"), "expns"),
    ("division", fpd.groupby("division"), "expns"),
]:
    for key, g in grp:
        if len(g) < MIN_N:
            continue
        mu, sd, cv = weighted_cv(g.y.values, g[w_col].values)
        lv.append(dict(level=name, key=key, n_forest=len(g), wcv=cv, unweighted_cv=g.y.std() / g.y.mean()))
mu_all, sd_all, cv_all = weighted_cv(fpd.y.values, fpd.expns.values)
lv.append(dict(level="national", key="all", n_forest=len(fpd), wcv=cv_all, unweighted_cv=fpd.y.std() / fpd.y.mean()))
pd.DataFrame(lv).to_csv("out/d4_spread_by_level.csv", index=False)
print(pd.DataFrame(lv).groupby("level")[["wcv", "unweighted_cv"]].median().round(3).to_string())
