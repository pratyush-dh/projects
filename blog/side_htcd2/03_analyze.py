#!/usr/bin/env python3
"""Side project, step 3: crew-reconstructed height (HTCD 2) vs model height, with the controls the naive design lacks.

Key identity: (HT - ACTUALHT) - (HT_hat - ACTUALHT) = HT - HT_hat, so "missing-length residual" == "total-height residual".
Everything below is therefore expressed as  lr = ln(HT / HT_hat)  (multiplicative, roughly homoscedastic) and in feet.
All intervals are plot-clustered bootstrap (trees in a plot are not independent).
Outputs: out/*.csv, out/summary.json
"""
import json, os
import numpy as np, pandas as pd

os.makedirs("out", exist_ok=True)
rng = np.random.default_rng(2026)
B = 500
d = pd.read_pickle("data/analysis_trees.pkl")
d["lr"] = np.log(d.ht / d.hat)
d["r"] = d.ht - d.hat
intact = d.actualht.isna() | (d.actualht == d.ht)
ctl = d[(d.htcd == 1) & intact].copy()                       # measured, intact, unseen plots
h1dmg = d[(d.htcd == 1) & (d.actualht < d.ht)].copy()        # "measured" but ACTUALHT < HT
h2 = d[(d.htcd == 2) & (d.actualht < d.ht)].copy()           # crew-reconstructed intact height, break > 0
h2eq = d[(d.htcd == 2) & (d.actualht == d.ht)]               # HTCD 2 but nothing missing
h2na = d[(d.htcd == 2) & d.actualht.isna()]
S = {"n": {"ctl_intact_testplots": len(ctl), "htcd1_actual_lt_ht_testplots": len(h1dmg), "htcd2_break": len(h2), "htcd2_actual_eq_ht": len(h2eq),
           "htcd2_actual_missing": len(h2na), "htcd3": int((d.htcd == 3).sum())}}
assert np.allclose((h2.ht - h2.actualht) - (h2.hat - h2.actualht), h2.r)  # the identity
BINS = [1, 5, 10, 15, 20, 30, 61]; LAB = ["1-4.9", "5-9.9", "10-14.9", "15-19.9", "20-29.9", "30+"]
for x in (ctl, h1dmg, h2, h2eq, d):
    x["dclass"] = pd.cut(x.dia, BINS, labels=LAB, right=False)


def plot_sums(x, key, val):
    """dense plot x group matrices of n and sum(val) for a fast cluster bootstrap"""
    g = x[key].cat.codes.values if hasattr(x[key], "cat") else pd.factorize(x[key])[0]
    p = pd.factorize(x.plt_cn)[0]; k = g.max() + 1
    n = np.zeros((p.max() + 1, k)); s = np.zeros_like(n); s2 = np.zeros_like(n)
    ok = g >= 0
    np.add.at(n, (p[ok], g[ok]), 1); np.add.at(s, (p[ok], g[ok]), x[val].values[ok]); np.add.at(s2, (p[ok], g[ok]), x[val].values[ok] ** 2)
    return n, s, s2


def boot_mean(x, key, val, B=B):
    n, s, s2 = plot_sums(x, key, val)
    m = s.sum(0) / n.sum(0); reps = np.empty((B, n.shape[1]))
    for b in range(B):
        w = np.bincount(rng.integers(0, len(n), len(n)), minlength=len(n)).astype(float)
        reps[b] = (w @ s) / (w @ n)
    return m, reps


# ---------------------------------------------------------------- 1. by DBH class: crew-reconstructed vs control
mc, rc = boot_mean(ctl, "dclass", "lr"); mh, rh = boot_mean(h2, "dclass", "lr")
diff = mh - mc; dr = rh - rc
rows = []
for i, c in enumerate(LAB):
    a, b = ctl[ctl.dclass == c], h2[h2.dclass == c]
    rows.append(dict(dbh_class=c, n_control=len(a), n_htcd2=len(b), mean_lr_control=mc[i], mean_lr_htcd2=mh[i], diff_lr=diff[i],
                     diff_lo=np.percentile(dr[:, i], 2.5), diff_hi=np.percentile(dr[:, i], 97.5), diff_pct=100 * (np.exp(diff[i]) - 1),
                     sd_lr_control=a.lr.std(), sd_lr_htcd2=b.lr.std(), mean_ft_control=a.r.mean(), mean_ft_htcd2=b.r.mean(),
                     rmse_ft_control=np.sqrt((a.r ** 2).mean()), rmse_ft_htcd2=np.sqrt((b.r ** 2).mean()),
                     share_model_below_actualht=(b.hat < b.actualht).mean(), mean_break_ft=(b.ht - b.actualht).mean(), mean_break_frac=((b.ht - b.actualht) / b.ht).mean()))
T1 = pd.DataFrame(rows); T1.to_csv("out/t1_by_dbh_class.csv", index=False)
allm, allr = boot_mean(pd.concat([ctl.assign(g=0), h2.assign(g=1)]).assign(g=lambda z: z.g.astype("category")), "g", "lr")
S["overall_lr"] = dict(control=float(allm[0]), htcd2=float(allm[1]), diff=float(allm[1] - allm[0]), diff_ci=[float(np.percentile(allr[:, 1] - allr[:, 0], q)) for q in (2.5, 97.5)])

# ---------------------------------------------------------------- 2. severity: rank of ACTUALHT within 2-inch DBH class; control ranked on HT
def pct_in_class(x, col):
    k = np.floor(x.dia / 2).astype(int)
    return x.groupby(k)[col].rank(pct=True)


h2["sev"] = pct_in_class(h2, "actualht"); ctl["sev"] = pct_in_class(ctl, "ht")
for x in (h2, ctl):
    x["sevbin"] = pd.cut(x.sev, np.linspace(0, 1, 11), labels=[f"{i * 10}-{i * 10 + 10}" for i in range(10)], include_lowest=True)
a, ra = boot_mean(ctl, "sevbin", "lr"); b_, rb = boot_mean(h2, "sevbin", "lr")
T2 = pd.DataFrame(dict(percentile_bin=ctl.sevbin.cat.categories, control_mean_lr=a, htcd2_mean_lr=b_,
                       htcd2_lo=np.percentile(rb, 2.5, axis=0), htcd2_hi=np.percentile(rb, 97.5, axis=0),
                       control_lo=np.percentile(ra, 2.5, axis=0), control_hi=np.percentile(ra, 97.5, axis=0),
                       excess_lr=b_ - a, n_htcd2=h2.groupby("sevbin", observed=False).size().values))
T2.to_csv("out/t2_severity_percentile.csv", index=False)
# ratio severities (coupled to HT_crew or HT_hat by construction - reported to show the artefact, not as a finding)
h2["s_hat"] = h2.actualht / h2.hat; h2["s_crew"] = h2.actualht / h2.ht
for c, edges in (("s_hat", [0, .5, .7, .8, .9, 1.0, 1.1, 10]), ("s_crew", [0, .5, .7, .8, .9, .95, 1.0001])):
    h2[c + "_bin"] = pd.cut(h2[c], edges)
    m, r = boot_mean(h2, c + "_bin", "lr")
    pd.DataFrame(dict(bin=h2[c + "_bin"].cat.categories.astype(str), mean_lr=m, lo=np.percentile(r, 2.5, axis=0), hi=np.percentile(r, 97.5, axis=0),
                      n=h2.groupby(c + "_bin", observed=False).size().values)).to_csv(f"out/t3_ratio_{c}.csv", index=False)

# ---------------------------------------------------------------- 3. simulation: an UNBIASED crew still produces a severity trend on ratio axes
sd_model = float(ctl.lr.std()); n = 400000
delta = np.exp(rng.normal(0, sd_model, n)); u = rng.uniform(0.3, 1.0, n)
true_ht = 100 * delta; actual = true_ht * u
sim = {}
for sig_e in (0.0, 0.10):
    crew = true_ht * np.exp(rng.normal(-sig_e ** 2 / 2, sig_e, n))     # unbiased in the mean, noise sig_e
    lr = np.log(crew / 100)
    out = {}
    for nm, s in (("actualht/HT_crew", actual / crew), ("actualht/HT_hat", actual / 100)):
        q = pd.qcut(s, 5, labels=False); out[nm] = [float(lr[q == k].mean()) for k in range(5)]
    q = pd.qcut(actual, 5, labels=False); out["ACTUALHT (rank)"] = [float(lr[q == k].mean()) for k in range(5)]
    sim[f"crew_noise_{sig_e}"] = out
S["simulation"] = dict(model_sd_lr=sd_model, **sim)
json.dump(sim, open("out/sim_coupling.json", "w"), indent=1)

# ---------------------------------------------------------------- 4. anchor test: earlier MEASURED height of the same tree
def pairs(x):
    p = x[(x.p_htcd == 1) & (x.p_actualht.isna() | (x.p_actualht == x.p_ht)) & x.p_ht.notna()].copy()
    p["dt"] = p.invyr - p.p_invyr
    return p[p.dt.between(1, 12) & (p.p_ht >= 4.5)]


pc_, ph = pairs(ctl), pairs(h2)
pc_["g"] = np.log(pc_.ht / pc_.p_ht) / pc_.dt                     # ln growth per year of intact measured trees
gr = pc_.groupby("dclass", observed=True).g.median()             # median, robust to measurement noise
for x in (pc_, ph):
    x["truth"] = x.p_ht * np.exp(x.dclass.map(gr).astype(float) * x.dt)   # earlier measured height grown forward
    x["e_crew"] = np.log(x.ht / x.truth); x["e_mod"] = np.log(x.hat / x.truth)
    x["e_crew_ft"] = x.ht - x.truth; x["e_mod_ft"] = x.hat - x.truth
S["pairs"] = dict(n_htcd2=len(ph), n_control=len(pc_), median_dt=float(ph.dt.median()), growth_ln_per_yr=gr.round(4).to_dict(),
                  crew_equals_prev_share_htcd2=float((ph.ht == ph.p_ht).mean()), control_equals_prev_share=float((pc_.ht == pc_.p_ht).mean()),
                  crew_ge_prev_share_htcd2=float((ph.ht >= ph.p_ht).mean()))
rows = []
for c in LAB:
    a_, b2 = pc_[pc_.dclass == c], ph[ph.dclass == c]
    if len(b2) < 30: continue
    rows.append(dict(dbh_class=c, n_htcd2=len(b2), crew_bias_lr=b2.e_crew.mean(), model_bias_lr=b2.e_mod.mean(), crew_rmse_lr=np.sqrt((b2.e_crew ** 2).mean()), model_rmse_lr=np.sqrt((b2.e_mod ** 2).mean()),
                     crew_rmse_ft=np.sqrt((b2.e_crew_ft ** 2).mean()), model_rmse_ft=np.sqrt((b2.e_mod_ft ** 2).mean()), crew_closer_share=(b2.e_crew.abs() < b2.e_mod.abs()).mean(),
                     n_control=len(a_), control_bias_lr=a_.e_crew.mean(), control_rmse_lr=np.sqrt((a_.e_crew ** 2).mean()), control_model_rmse_lr=np.sqrt((a_.e_mod ** 2).mean())))
T4 = pd.DataFrame(rows); T4.to_csv("out/t4_anchor_by_dbh.csv", index=False)
# overall with cluster bootstrap of the paired squared-error difference (crew - model)
ph["dse"] = ph.e_crew ** 2 - ph.e_mod ** 2; ph["one"] = 0; ph["one"] = ph["one"].astype("category")
m, r = boot_mean(ph.assign(one=pd.Categorical(np.zeros(len(ph), int))), "one", "dse")
S["pairs"]["paired_sqerr_diff_crew_minus_model"] = dict(mean=float(m[0]), ci=[float(np.percentile(r[:, 0], q)) for q in (2.5, 97.5)])
for nm, col in (("crew", "e_crew"), ("model", "e_mod")):
    ph["t"] = ph[col]; mm, rr = boot_mean(ph.assign(one=pd.Categorical(np.zeros(len(ph), int))), "one", "t")
    S["pairs"][nm + "_bias_lr"] = dict(mean=float(mm[0]), ci=[float(np.percentile(rr[:, 0], q)) for q in (2.5, 97.5)], rmse=float(np.sqrt((ph[col] ** 2).mean())))
# by severity within the paired subset (percentile of ACTUALHT)
ph["sevbin"] = pd.cut(ph.sev, [0, .25, .5, .75, 1.0], include_lowest=True)
T5 = ph.groupby("sevbin", observed=True).agg(n=("e_crew", "size"), crew_bias=("e_crew", "mean"), model_bias=("e_mod", "mean"),
                                                 crew_rmse=("e_crew", lambda v: np.sqrt((v ** 2).mean())), model_rmse=("e_mod", lambda v: np.sqrt((v ** 2).mean()))).reset_index()
T5["sevbin"] = T5.sevbin.astype(str); T5.to_csv("out/t5_anchor_by_severity.csv", index=False)

# ---------------------------------------------------------------- 5. QC-audit use: flag by control limits, score against the anchor
lim = ctl.groupby("dclass", observed=True).lr.quantile([0.025, 0.975]).unstack(); lim.columns = ["lo", "hi"]
for x in (h2, ph, ctl):
    x["flag"] = (x.lr < x.dclass.map(lim.lo).astype(float)) | (x.lr > x.dclass.map(lim.hi).astype(float))
S["qc"] = dict(control_flag_rate=float(ctl.flag.mean()), htcd2_flag_rate=float(h2.flag.mean()),
               htcd2_flag_high=float((h2.lr > h2.dclass.map(lim.hi).astype(float)).mean()), htcd2_flag_low=float((h2.lr < h2.dclass.map(lim.lo).astype(float)).mean()))
for thr in (0.10, 0.20):
    bad = ph.e_crew.abs() > thr; fl = ph.flag
    S["qc"][f"anchor_err_gt_{thr}"] = dict(prevalence=float(bad.mean()), sensitivity=float((fl & bad).sum() / max(bad.sum(), 1)), specificity=float((~fl & ~bad).sum() / max((~bad).sum(), 1)),
                                           ppv=float((fl & bad).sum() / max(fl.sum(), 1)))

# ---------------------------------------------------------------- 6. context: where/when, heaping, tiers
west = d.statecd.isin([2, 6, 41, 53])
d["era"] = pd.cut(d.invyr, [0, 2004, 2009, 2014, 2019, 2030], labels=["<=2004", "2005-09", "2010-14", "2015-19", "2020+"])
ctx = []
for nm, key in (("region", np.where(west, "AK/CA/OR/WA", "other states")), ("era", d.era.astype(str).values), ("state", d.statecd.values), ("tier", d.model_tier.values)):
    z = d.assign(k=key)
    for k, g in z.groupby("k"):
        a_, b2 = g[(g.htcd == 1) & (g.actualht.isna() | (g.actualht == g.ht))], g[(g.htcd == 2) & (g.actualht < g.ht)]
        if len(b2) >= 200: ctx.append(dict(by=nm, group=k, n_htcd2=len(b2), n_ctl=len(a_), htcd2_mean_lr=b2.lr.mean(), ctl_mean_lr=a_.lr.mean() if len(a_) else np.nan,
                                           htcd2_sd_lr=b2.lr.std(), ctl_sd_lr=a_.lr.std() if len(a_) else np.nan))
pd.DataFrame(ctx).to_csv("out/t6_context.csv", index=False)
for nm, x in (("htcd2", h2), ("control", ctl)):
    S.setdefault("heaping", {})[nm] = dict(mult5=float((x.ht % 5 == 0).mean()), mult10=float((x.ht % 10 == 0).mean()))
S["htcd1_actual_lt_ht_share_of_htcd1_testplots"] = float(len(h1dmg) / (len(ctl) + len(h1dmg)))
json.dump(S, open("out/summary.json", "w"), indent=1, default=float)
pd.set_option("display.width", 250, "display.max_columns", 30)
print(json.dumps({k: S[k] for k in ("n", "overall_lr", "pairs", "qc", "heaping")}, indent=1, default=float)); print(T1.round(3).to_string()); print(T2.round(3).to_string()); print(T4.round(3).to_string()); print(T5.round(3).to_string())
