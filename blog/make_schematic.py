#!/usr/bin/env python3
"""Schematic of HT, ACTUALHT and the height method codes (HTCD 1-4) for the blog post."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Rectangle

INK, MUTE, TEAL, BLUE, ORANGE, GREY = "#0b0b0b", "#52514e", "#1baf7a", "#2a78d6", "#eb6834", "#8a8a86"
plt.rcParams.update({"font.family": "Arial", "font.size": 11, "text.color": INK, "figure.facecolor": "white"})
fig, ax = plt.subplots(figsize=(13, 5.6)); ax.set_xlim(0, 13.6); ax.set_ylim(-1.6, 7.4); ax.axis("off")


def tree(x, top, colour, dashed_to=None):
    ax.add_patch(Rectangle((x - 0.09, 0), 0.18, top, color="#6b5a45", lw=0, zorder=2))
    ax.add_patch(Polygon([(x - 0.75, top * 0.42), (x + 0.75, top * 0.42), (x, top)], closed=True, color=colour, alpha=0.9, lw=0, zorder=1))
    if dashed_to:
        ax.plot([x, x], [top, dashed_to], color=GREY, lw=2, ls=(0, (3, 2)), zorder=3)
        base = top + (dashed_to - top) * 0.05
        ax.add_patch(Polygon([(x - 0.5, base), (x + 0.5, base), (x, dashed_to)], closed=True, fill=False, ec=GREY, ls=(0, (3, 2)), lw=1.2, zorder=1))


def dim(x, y0, y1, label, colour, side=1):
    ax.annotate("", xy=(x, y1), xytext=(x, y0), arrowprops=dict(arrowstyle="<->", color=colour, lw=1.6))
    ax.text(x + 0.12 * side, (y0 + y1) / 2, label, color=INK, va="center", ha="left" if side > 0 else "right", fontsize=10.5)


ax.plot([0.2, 13.4], [0, 0], color="#6b5a45", lw=2)
tree(1.4, 5.2, TEAL); dim(2.4, 0, 5.2, "HT = ACTUALHT\nmeasured\n(HTCD 1)", TEAL)
tree(6.0, 3.4, TEAL, dashed_to=5.6)
dim(4.9, 0, 3.4, "ACTUALHT\nmeasured", TEAL, side=-1)
dim(7.0, 3.4, 5.6, "missing piece\nestimated by the crew\n(HTCD 2 or 3)", BLUE)
tree(10.6, 4.6, GREY); dim(11.55, 0, 4.6, "HT from a model\nusing DBH\n(HTCD 4)", ORANGE)
for x, t, s in ((1.4, "1  Intact tree", "crew measures the whole tree"), (6.0, "2  Broken top", "HT is total length: standing part + missing piece"), (10.6, "3  Height not taken in the field", "an imputation model fills HT in")):
    ax.text(x, -0.75, t, ha="center", fontweight="bold"); ax.text(x, -1.25, s, ha="center", color=MUTE, fontsize=10)
ax.text(0.2, 7.15, "What the height columns of the FIA TREE table can mean", fontsize=13, fontweight="bold", va="top")
fig.savefig("figures/f01_height_codes_schematic.png", dpi=200, bbox_inches="tight"); print("ok")
