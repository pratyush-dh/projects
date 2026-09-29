#!/usr/bin/env python3
"""Side project, step 4: is the anchor result (crew closer to the earlier measured height than the model) an artefact of crews seeing / copying
the previous height?  Repeat the anchor comparison on trees whose current HT differs from the previous recorded HT, by era, and with the
growth adjustment switched off.  -> out/t7_anchor_robustness.csv, out/summary_robust.json"""
import json
import numpy as np, pandas as pd

d = pd.read_pickle("data/analysis_trees.pkl")
d["lr"] = np.log(d.ht / d.hat)
intact = d.actualht.isna() | (d.actualht == d.ht)
BINS = [1, 5, 10, 15, 20, 30, 61]; LAB = ["1-4.9", "5-9.9", "10-14.9", "15-19.9", "20-29.9", "30+"]
d["dclass"] = pd.cut(d.dia, BINS, labels=LAB, right=False)
d["era"] = pd.cut(d.invyr, [0, 2004, 2009, 2014, 2019, 2030], labels=["<=2004", "2005-09", "2010-14", "2015-19", "2020+"])


def pairs(x):
    p = x[(x.p_htcd == 1) & (x.p_actualht.isna() | (x.p_actualht == x.p_ht)) & x.p_ht.notna()].copy()
    p["dt"] = p.invyr - p.p_invyr
    return p[p.dt.between(1, 12) & (p.p_ht >= 4.5)]


ctl = pairs(d[(d.htcd == 1) & intact]); h2 = pairs(d[(d.htcd == 2) & (d.actualht < d.ht)])
ctl["g"] = np.log(ctl.ht / ctl.p_ht) / ctl.dt
gr = ctl.groupby("dclass", observed=True).g.median()
for x in (ctl, h2):
    x["truth"] = x.p_ht * np.exp(x.dclass.map(gr).astype(float) * x.dt)
    x["e_crew"] = np.log(x.ht / x.truth); x["e_mod"] = np.log(x.hat / x.truth)
    x["e_crew0"] = np.log(x.ht / x.p_ht); x["e_mod0"] = np.log(x.hat / x.p_ht)   # no growth adjustment
    x["same"] = x.ht == x.p_ht


def summ(x, tag):
    return dict(subset=tag, n=len(x), crew_bias=x.e_crew.mean(), model_bias=x.e_mod.mean(), crew_rmse=np.sqrt((x.e_crew ** 2).mean()), model_rmse=np.sqrt((x.e_mod ** 2).mean()),
                crew_closer=(x.e_crew.abs() < x.e_mod.abs()).mean(), crew_rmse_nogrowth=np.sqrt((x.e_crew0 ** 2).mean()), model_rmse_nogrowth=np.sqrt((x.e_mod0 ** 2).mean()))


rows = [summ(h2, "HTCD 2, all pairs"), summ(h2[~h2.same], "HTCD 2, HT != previous HT"), summ(h2[h2.same], "HTCD 2, HT == previous HT (copied)"),
        summ(h2[(~h2.same) & (h2.ht % 5 != 0)], "HTCD 2, HT != previous and not a multiple of 5 ft"),
        summ(ctl[~ctl.same], "control HTCD 1 intact (measured now and before), HT != previous")]
for e, g in h2[~h2.same].groupby("era", observed=True): rows.append(summ(g, f"HTCD 2, HT != previous, era {e}"))
for c, g in h2[~h2.same].groupby("dclass", observed=True): rows.append(summ(g, f"HTCD 2, HT != previous, DBH {c}"))
T = pd.DataFrame(rows); T.to_csv("out/t7_anchor_robustness.csv", index=False)
share = h2.groupby("era", observed=True).same.mean().round(3).to_dict()
# QC audit against the non-copied anchor: does a model-limit flag find the crew's large errors?
ctl_all = d[(d.htcd == 1) & intact]
lim = ctl_all.groupby("dclass", observed=True).lr.quantile([0.025, 0.975]).unstack(); lim.columns = ["lo", "hi"]
q = h2[~h2.same].copy(); q["flag"] = (q.lr < q.dclass.map(lim.lo).astype(float)) | (q.lr > q.dclass.map(lim.hi).astype(float))
R = {"copied_share_by_era": share, "copied_share_htcd2": float(h2.same.mean()), "copied_share_control": float(ctl.same.mean())}
for thr in (0.10, 0.20):
    bad = q.e_crew.abs() > thr; fl = q.flag
    R[f"qc_noncopied_err_gt_{thr}"] = dict(prevalence=float(bad.mean()), flag_rate=float(fl.mean()), sensitivity=float((fl & bad).sum() / bad.sum()), specificity=float((~fl & ~bad).sum() / (~bad).sum()),
                                           ppv=float((fl & bad).sum() / fl.sum()))
    # AUC of |lr| as a score for crew error > thr (rank-based)
    from scipy.stats import rankdata
    sc = q.lr.abs().values; y = bad.values; r = rankdata(sc); n1 = y.sum(); n0 = len(y) - n1
    R[f"qc_noncopied_err_gt_{thr}"]["auc_abs_lr"] = float((r[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))
json.dump(R, open("out/summary_robust.json", "w"), indent=1)
pd.set_option("display.width", 250, "display.max_columns", 30)
print(T.round(3).to_string()); print(json.dumps(R, indent=1))
