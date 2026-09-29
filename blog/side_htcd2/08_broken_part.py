#!/usr/bin/env python3
"""Side project, step 8: the broken-off part itself.

delta_crew  = HT - ACTUALHT           (missing length the crew reconstructed)
delta_model = HT_hat - ACTUALHT       (missing length implied by the HTCD 1-derived regional model)
delta_truth = T - ACTUALHT            (T = the same tree's earlier MEASURED intact height, grown forward; anchor pairs whose HT differs from the earlier HT)
delta_crew - delta_model == HT - HT_hat, so any relation of that difference to the stump height ACTUALHT contains a MECHANICAL part (tall stump
=> tall tree => model under-predicts; and HT >= ACTUALHT truncation).  Benchmarks: the same statistic for intact measured trees ranked on their own
height.  The clean test of crew behaviour is crew error vs the earlier measured height as a function of stump height (no shared noise).
Outputs: out/t12_delta_bins.csv, out/t13_anchor_by_stump.csv, out/t14_anchor_by_relative_stump.csv, out/summary_broken.json, figures/fig12-14
"""
import json
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import colors
from matplotlib.patches import Patch

BLUE, ORANGE, GREY, INK, MUTE, GRID = "#2a78d6", "#eb6834", "#8a8a86", "#0b0b0b", "#52514e", "#e6e5e1"
plt.rcParams.update({"font.family": "Arial", "font.size": 10, "axes.labelsize": 10, "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlelocation": "left",
                     "text.color": INK, "axes.labelcolor": MUTE, "xtick.color": MUTE, "ytick.color": MUTE, "axes.edgecolor": "#b9b8b2", "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.7, "axes.axisbelow": True, "figure.facecolor": "white",
                     "pdf.fonttype": 42, "savefig.dpi": 200, "figure.constrained_layout.use": True, "legend.frameon": False})
HEX = matplotlib.colors.LinearSegmentedColormap.from_list("seq_teal", ["#f4faf7", "#1baf7a", "#0a4d36"])
rng = np.random.default_rng(11); B = 300


def save(fig, n):
    for ext in ("png", "pdf"):
        try: fig.savefig(f"figures/{n}.{ext}", bbox_inches="tight")
        except OSError: fig.savefig(f"figures/{n}_new.{ext}", bbox_inches="tight"); print("locked ->", f"{n}_new.{ext}")
    plt.close(fig)


d = pd.read_pickle("data/analysis_trees.pkl")
BINS = [1, 5, 10, 15, 20, 30, 61]; LAB = ["1-4.9", "5-9.9", "10-14.9", "15-19.9", "20-29.9", "30+"]
d["dclass"] = pd.cut(d.dia, BINS, labels=LAB, right=False)
G3 = lambda x: pd.cut(x.dia, [1, 10, 20, 61], labels=["1-9.9 in", "10-19.9 in", "20+ in"], right=False)
intact = d.actualht.isna() | (d.actualht == d.ht)
ctl = d[(d.htcd == 1) & intact].copy(); h2 = d[(d.htcd == 2) & (d.actualht < d.ht)].copy()
for x in (ctl, h2): x["g3"] = G3(x)
h2["dcrew"] = h2.ht - h2.actualht; h2["dmod"] = h2.hat - h2.actualht; h2["ddiff"] = h2.dcrew - h2.dmod
ctl["ddiff"] = ctl.ht - ctl.hat
S = {"n_htcd2": len(h2), "identity_max_abs_err": float((h2.ddiff - (h2.ht - h2.hat)).abs().max())}


# ---------------------------------------------------------------- anchor pairs
def pairs(x):
    p = x[(x.p_htcd == 1) & (x.p_actualht.isna() | (x.p_actualht == x.p_ht)) & x.p_ht.notna()].copy(); p["dt"] = p.invyr - p.p_invyr
    return p[p.dt.between(1, 12) & (p.p_ht >= 4.5)]


pc_, ph = pairs(ctl), pairs(d[(d.htcd == 2) & (d.actualht < d.ht)].copy())
gr = (np.log(pc_.ht / pc_.p_ht) / pc_.dt).groupby(pc_.dclass, observed=True).median()
ph["T"] = ph.p_ht * np.exp(ph.dclass.map(gr).astype(float) * ph.dt)
ph = ph[ph.ht != ph.p_ht].copy()                                  # crew value differs from the earlier record
S["anchor_pairs_noncopied"] = len(ph); S["anchor_share_T_below_stump"] = float((ph["T"] < ph.actualht).mean())
ph["dcrew"] = ph.ht - ph.actualht; ph["dmod"] = ph.hat - ph.actualht; ph["dtru"] = ph["T"] - ph.actualht
ph["e_crew"] = ph.ht - ph["T"]; ph["e_mod"] = ph.hat - ph["T"]     # ft (== error of the reconstructed missing length)
ph["s_hat"] = ph.actualht / ph.hat                                 # stump height relative to what the model expects for this DBH
ph["g3"] = G3(ph)
S["anchor_pairs_used_for_errors"] = len(ph)
# NOTE: errors are analysed on ALL such pairs.  Dropping pairs with T <= ACTUALHT (earlier height below today's stump) would select on the earlier
# measurement's own noise and manufacture an apparent under-estimate for tall stumps.  Only the missing-LENGTH scatter needs T > ACTUALHT.
phd = ph[ph["T"] > ph.actualht + 1].copy(); S["anchor_pairs_positive_missing"] = len(phd)


def cluster_mean(x, key, vals):
    codes = pd.Categorical(x[key]).codes; p = pd.factorize(x.plt_cn)[0]; k = codes.max() + 1
    n = np.zeros((p.max() + 1, k)); s = {v: np.zeros_like(n) for v in vals}
    ok = codes >= 0; np.add.at(n, (p[ok], codes[ok]), 1)
    for v in vals: np.add.at(s[v], (p[ok], codes[ok]), x[v].values[ok])
    tot = n.sum(0); out = {v: s[v].sum(0) / tot for v in vals}; R = {v: np.empty((B, k)) for v in vals}
    for b in range(B):
        w = np.bincount(rng.integers(0, len(n), len(n)), minlength=len(n)).astype(float); den = w @ n
        for v in vals: R[v][b] = (w @ s[v]) / den
    return tot, out, {v: (np.percentile(R[v], 2.5, axis=0), np.percentile(R[v], 97.5, axis=0)) for v in vals}


# ---------------------------------------------------------------- Fig 12: the broken part, crew vs model (top) and both vs the earlier measurement (bottom)
# Academic style: sampled points, conditional median with IQR ribbon and 5-95 % bounds, 1:1 line, vector output.
plt.rcParams.update({"axes.grid": False, "axes.spines.top": False, "axes.spines.right": False, "xtick.direction": "out", "ytick.direction": "out"})
PT = "#6f6f6b"


def cond_band(x, y, edges, min_n=40):
    q = pd.cut(x, edges); g = pd.DataFrame({"x": x.values, "y": y.values, "q": q.values}).groupby("q", observed=True)
    keep = g.size() >= min_n
    o = pd.DataFrame({"x": g.x.median(), "p05": g.y.quantile(.05), "p25": g.y.quantile(.25), "med": g.y.median(), "p75": g.y.quantile(.75), "p95": g.y.quantile(.95)})[keep]
    return o


def panel(ax, x, y, colour, xlim, ylim, edges, n_pts=4000, label=None, swap=False):
    idx = np.random.default_rng(5).choice(len(x), min(n_pts, len(x)), replace=False)
    ax.scatter(x.values[idx], y.values[idx], s=3.5, c=PT, alpha=0.28, linewidths=0, zorder=1)
    b = cond_band(x, y, edges)
    ax.fill_between(b.x, b.p25, b.p75, color=colour, alpha=0.22, lw=0, zorder=2)
    ax.plot(b.x, b.p05, color=colour, lw=0.9, ls=(0, (2, 2)), zorder=3); ax.plot(b.x, b.p95, color=colour, lw=0.9, ls=(0, (2, 2)), zorder=3)
    ax.plot(b.x, b.med, color=colour, lw=2.0, zorder=4, label=label)
    ax.plot(xlim, xlim, color=INK, lw=0.9, ls=(0, (5, 3)), zorder=5); ax.axhline(0, color="#9a9994", lw=0.6, zorder=0)
    ax.set_xlim(xlim); ax.set_ylim(ylim)
    return b


fig, axs = plt.subplots(2, 3, figsize=(14.5, 9.0))
XL = (0, 80); YL = (-40, 80); EDG = np.arange(0, 84, 6)
for ax, g in zip(axs[0], ["1-9.9 in", "10-19.9 in", "20+ in"]):
    z = h2[h2.g3 == g]
    panel(ax, z.dcrew, z.dmod, BLUE, XL, YL, EDG, label="Median, IQR (band), 5th-95th pct. (dotted)")
    ax.set_xlabel("Missing length imputed by the crew, HT - ACTUALHT (ft)"); ax.set_ylabel("Missing length from the model, HT_hat - ACTUALHT (ft)")
    rho = z[["dcrew", "dmod"]].corr(method="spearman").iloc[0, 1]
    ax.set_title(f"{g}  (n = {len(z):,})", pad=6); ax.text(0.97, 0.05, f"Spearman rho = {rho:.2f}\nmodel < 0 for {100 * (z.dmod < 0).mean():.0f}% of trees", transform=ax.transAxes, ha="right", fontsize=9, color=INK)
    S.setdefault("spearman_crew_vs_model", {})[g] = float(rho)
axs[0, 0].legend(loc="upper left", fontsize=8.5, labelcolor=INK)
lab = [("dtru", "dcrew", BLUE, "Crew-imputed vs earlier measured missing length", "Imputed missing length (ft)"), ("dtru", "dmod", ORANGE, "Model vs earlier measured missing length", "Model missing length (ft)")]
for ax, (xv, yv, colr, ttl, yl) in zip(axs[1][:2], lab):
    panel(ax, phd[xv], phd[yv], colr, XL, YL, EDG, label="Median, IQR (band), 5th-95th percentile (dotted)")
    ax.set_xlabel("Missing length from the earlier measured height (ft)"); ax.set_ylabel(yl); ax.set_title(ttl, pad=6)
axs[1, 0].legend(loc="upper left", fontsize=8, labelcolor=INK)
ax = axs[1, 2]
bc = cond_band(phd.dtru, phd.dcrew, EDG); bm = cond_band(phd.dtru, phd.dmod, EDG)
for b_, colr, nm in ((bc, BLUE, "Crew-imputed"), (bm, ORANGE, "Model")):
    ax.fill_between(b_.x, b_.p25, b_.p75, color=colr, alpha=0.18, lw=0); ax.plot(b_.x, b_.med, "o-", color=colr, lw=2, ms=4, label=nm)
ax.plot(XL, XL, color=INK, lw=0.9, ls=(0, (5, 3)), label="Perfect agreement"); ax.axhline(0, color="#9a9994", lw=0.6); ax.set_xlim(XL); ax.set_ylim(YL)
ax.set_xlabel("Missing length from the earlier measured height (ft)"); ax.set_ylabel("Median (band: 25th-75th percentile) (ft)"); ax.set_title("Both, in bins of the earlier measured length", pad=6); ax.legend(loc="upper left", labelcolor=INK)
S["missing_length_bins"] = bc.reset_index(drop=True).round(2).assign(model_med=bm.med.values).to_dict("records") if len(bc) == len(bm) else []
fig.text(0.0, -0.012, "Top: HTCD 2 trees (4,000 sampled points per panel; statistics use all trees). Bottom: HTCD 2 trees with an earlier measured intact height and HT different from it (n = %s, true missing length > 1 ft). Dashed diagonal: 1:1." % f"{len(phd):,}", fontsize=9, color=MUTE)
save(fig, "fig12_broken_part_crew_vs_model")
plt.rcParams.update({"axes.grid": True})

# ---------------------------------------------------------------- Fig 13: how the discrepancy depends on the stump height (with the mechanical benchmark) and the anchor test
def decile_curve(x, val, rank_col):
    k = np.floor(x.dia / 2).astype(int); x = x.assign(sev=x.groupby(k)[rank_col].rank(pct=True)); x["bin"] = pd.cut(x.sev, np.linspace(0, 1, 11), labels=False, include_lowest=True)
    x["mid"] = x.groupby("bin")[rank_col].transform("median"); x["midpct"] = 10 * x["bin"] + 5
    return x


fig, axs = plt.subplots(2, 3, figsize=(14.5, 8.6))
rows = []
for ax, g in zip(axs[0], ["1-9.9 in", "10-19.9 in", "20+ in"]):
    zc = decile_curve(ctl[ctl.g3 == g], "ddiff", "ht"); zh = decile_curve(h2[h2.g3 == g], "ddiff", "actualht")
    for z, col, lab in ((zc, GREY, "Intact measured trees (ranked on their own height)"), (zh, BLUE, "HTCD 2 (ranked on stump height ACTUALHT)")):
        tot, m, ci = cluster_mean(z, "bin", ["ddiff", "mid", "midpct"])
        ax.fill_between(m["midpct"], ci["ddiff"][0], ci["ddiff"][1], color=col, alpha=0.18, lw=0); ax.plot(m["midpct"], m["ddiff"], "o-", color=col, lw=1.8, ms=5, label=lab)
        for i in range(len(tot)): rows.append(dict(dbh_group=g, set="control" if col == GREY else "htcd2", decile=i + 1, n=int(tot[i]), stump_or_height_ft=m["mid"][i], mean_ddiff_ft=m["ddiff"][i], lo=ci["ddiff"][0][i], hi=ci["ddiff"][1][i]))
    ax.axhline(0, color=INK, lw=0.8); ax.set_title(g, pad=6); ax.set_xlabel("Percentile rank within 2-inch diameter class"); ax.set_ylabel("Crew minus model missing length (ft)")
axs[0, 0].legend(loc="upper left", fontsize=8.5, labelcolor=INK)
pd.DataFrame(rows).to_csv("out/t12_delta_bins.csv", index=False)
# anchor: crew error and model error vs earlier measured height as a function of stump height
rows = []
for ax, g in zip(axs[1], ["1-9.9 in", "10-19.9 in", "20+ in"]):
    z = decile_curve(ph[ph.g3 == g], "e_crew", "actualht")
    tot, m, ci = cluster_mean(z, "bin", ["e_crew", "e_mod", "mid"])
    for v, col, lab in (("e_crew", BLUE, "Crew-imputed height"), ("e_mod", ORANGE, "Model height")):
        ax.fill_between(m["mid"], ci[v][0], ci[v][1], color=col, alpha=0.18, lw=0); ax.plot(m["mid"], m[v], "o-", color=col, lw=1.8, ms=5, label=lab)
    for i in range(len(tot)): rows.append(dict(dbh_group=g, decile=i + 1, n=int(tot[i]), stump_ft=m["mid"][i], crew_error_ft=m["e_crew"][i], crew_lo=ci["e_crew"][0][i], crew_hi=ci["e_crew"][1][i], model_error_ft=m["e_mod"][i], model_lo=ci["e_mod"][0][i], model_hi=ci["e_mod"][1][i]))
    ax.axhline(0, color=INK, lw=0.8); ax.set_title(g + "  (vs earlier measured height)", pad=6); ax.set_xlabel("Stump height, ACTUALHT (ft)"); ax.set_ylabel("Error of the reconstructed total height (ft)\n(= error of the missing length)")
axs[1, 0].legend(loc="lower left", fontsize=9, labelcolor=INK)
pd.DataFrame(rows).to_csv("out/t13_anchor_by_stump.csv", index=False)
fig.text(0.0, -0.015, "Top: rank = stump height (HTCD 2) or total height (intact control). The difference is partly mechanical (tall stump = tall tree), so read HTCD 2 against the grey benchmark, not against zero. Bottom: error against the tree's own earlier measured height (bands: 95% plot-clustered CI); positive = overestimate.", fontsize=9, color=MUTE)
save(fig, "fig13_stump_height_relationship")

# ---------------------------------------------------------------- Fig 14: tall stump relative to what the model expects (A / HT_hat)
edges = [0, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.3, 10]; ph["sbin"] = pd.cut(ph.s_hat, edges)
ph["e_crew_pct"] = 100 * (ph.ht / ph["T"] - 1); ph["e_mod_pct"] = 100 * (ph.hat / ph["T"] - 1); ph["sb"] = pd.Categorical(ph.sbin).codes
tot, m, ci = cluster_mean(ph, "sb", ["e_crew", "e_mod", "e_crew_pct", "e_mod_pct", "dtru", "dcrew"])
T14 = pd.DataFrame({"s_hat_bin": [str(c) for c in pd.Categorical(ph.sbin).categories], "n": tot.astype(int), "crew_error_ft": m["e_crew"], "crew_lo": ci["e_crew"][0], "crew_hi": ci["e_crew"][1],
                    "model_error_ft": m["e_mod"], "crew_error_pct": m["e_crew_pct"], "model_error_pct": m["e_mod_pct"], "mean_true_missing_ft": m["dtru"], "mean_crew_missing_ft": m["dcrew"]})
T14.to_csv("out/t14_anchor_by_relative_stump.csv", index=False)
fig, axs = plt.subplots(1, 3, figsize=(15.5, 4.8))
x = np.arange(len(T14)); lab = ["<0.5", "0.5-0.6", "0.6-0.7", "0.7-0.8", "0.8-0.9", "0.9-1.0", "1.0-1.1", "1.1-1.3", ">1.3"]
a = axs[0]; a.axhline(0, color=INK, lw=0.8)
a.errorbar(x, T14.crew_error_ft, yerr=[T14.crew_error_ft - T14.crew_lo, T14.crew_hi - T14.crew_error_ft], fmt="o-", color=BLUE, lw=1.8, ms=6, capsize=3, label="Crew-imputed")
a.plot(x, T14.model_error_ft, "o-", color=ORANGE, lw=1.8, ms=6, label="Model (shares HT_hat with the x-axis: partly mechanical)")
a.set_xticks(x, lab); a.set_xlabel("Stump height relative to the model's expected tree height (ACTUALHT / HT_hat)"); a.set_ylabel("Error vs earlier measured height (ft)"); a.set_title("Do crews misjudge tall stumps?", pad=6); a.legend(loc="lower left", fontsize=8.5, labelcolor=INK)
b = axs[1]; b.bar(x, T14.n, color=GREY, width=0.7); b.set_xticks(x, lab); b.set_xlabel("ACTUALHT / HT_hat"); b.set_ylabel("Trees (anchor pairs)"); b.set_title("How many trees per bin", pad=6)
c = axs[2]; c.bar(x - 0.2, T14.mean_true_missing_ft, 0.4, color=GREY, label="Earlier measured (true) missing length"); c.bar(x + 0.2, T14.mean_crew_missing_ft, 0.4, color=BLUE, label="Crew-imputed missing length")
c.set_xticks(x, lab); c.set_xlabel("ACTUALHT / HT_hat"); c.set_ylabel("Mean missing length (ft)"); c.set_title("Missing length shrinks as the stump gets tall", pad=6); c.legend(loc="upper right", fontsize=9, labelcolor=INK)
save(fig, "fig14_relative_stump_height")
S["anchor_by_relative_stump"] = T14.round(2).to_dict("records")
json.dump(S, open("out/summary_broken.json", "w"), indent=1, default=float)
pd.set_option("display.width", 250, "display.max_columns", 30)
print(json.dumps({k: S[k] for k in S if k not in ("anchor_by_relative_stump", "missing_length_bins")}, indent=1, default=float)); print(T14.round(2).to_string())
print(pd.DataFrame(S["missing_length_bins"]).to_string())
print(pd.read_csv("out/t13_anchor_by_stump.csv").round(2).to_string())
