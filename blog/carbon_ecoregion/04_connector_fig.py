#!/usr/bin/env python3
"""Carbon-by-ecoregion, step 4: the connector figure for the blog post -- for the 12 highest-carbon-density
divisions (same order as fig2), what share of that carbon rests on a field-measured height vs. a crew estimate
(HTCD 2/3, Part 1 of this series) vs. FIA's own model (HTCD 4, Part 2)."""
import pandas as pd
from plotnine import (ggplot, aes, geom_col, geom_text, labs, scale_fill_manual, scale_y_continuous,
                       coord_cartesian, theme_minimal, theme, element_text, element_blank, element_line, guides, guide_legend)

BLUE, ORANGE, GREY, INK, MUTE, GRID = "#2a78d6", "#eb6834", "#8a8a86", "#0b0b0b", "#52514e", "#e6e5e1"

t1 = pd.read_csv("out/t1_division_summary.csv")
t3 = pd.read_csv("out/t3_carbon_by_htcd_division.csv")
m = t1[t1.included_in_tests].merge(t3[["division", "measured_pct", "crew estimate_pct", "FIA modeled_pct"]], on="division")
m = m.sort_values("mean", ascending=False).head(12)

cat_order = ["Field-measured (HTCD 1)", "Crew estimate (HTCD 2/3, Part 1)", "FIA modeled (HTCD 4, Part 2)"]
long = m.melt(id_vars=["division", "division_name", "mean"],
              value_vars=["measured_pct", "crew estimate_pct", "FIA modeled_pct"],
              var_name="method", value_name="pct")
long["method"] = long.method.map({"measured_pct": cat_order[0], "crew estimate_pct": cat_order[1], "FIA modeled_pct": cat_order[2]})
long["method"] = pd.Categorical(long.method, categories=cat_order, ordered=True)

div_order = m.sort_values("mean", ascending=False).division.tolist()
long["division"] = pd.Categorical(long.division, categories=div_order, ordered=True)

labels = m.set_index("division").loc[div_order]
xlab = {d: f"{d}\n{r:.0f} t/acre" for d, r in labels["mean"].items()}

p = (ggplot(long, aes(x="division", y="pct", fill="method"))
     + geom_col(width=0.72)
     + scale_fill_manual(values={cat_order[0]: GREY, cat_order[1]: ORANGE, cat_order[2]: BLUE}, name="")
     + scale_y_continuous(breaks=[0, 25, 50, 75, 100], expand=(0, 0, 0, 4))
     + coord_cartesian(ylim=(0, 100))
     + labs(title="The highest-carbon divisions lean most on non-measured heights",
            x="", y="Share of this division's live-tree carbon, by the height behind it (%)",
            caption=("The 12 highest-carbon divisions from Fig. 2, in the same rank order (highest first).\n"
                      "Pacific coast / Mediterranean-climate divisions (blue-heavy) carry 23-48% of their carbon on FIA-modeled heights;\n"
                      "Appalachian/eastern divisions in the same top 12 (grey-dominated) are built almost entirely on field measurements."))
     + theme_minimal(base_family="Arial", base_size=11)
     + theme(figure_size=(9, 6),
             plot_title=element_text(weight="bold", size=12, ha="left", margin={"b": 14}),
             axis_text_x=element_text(size=8.5, color=MUTE, linespacing=1.4),
             axis_text_y=element_text(size=8.5, color=MUTE),
             axis_title_y=element_text(size=9.5, color=MUTE),
             panel_grid_major_x=element_blank(),
             panel_grid_minor=element_blank(),
             panel_grid_major_y=element_line(color=GRID, size=0.7),
             legend_position="top",
             legend_direction="horizontal",
             legend_text=element_text(size=9, color=INK),
             plot_caption=element_text(size=8.3, color=MUTE, ha="left", margin={"t": 14}),
             plot_caption_position="plot",
             plot_margin=0.02)
     + guides(fill=guide_legend(nrow=1)))

p = p + aes(x="division")
p.data = p.data  # no-op, keep categorical order

from plotnine import scale_x_discrete
p = p + scale_x_discrete(labels=lambda bks: [xlab[b] for b in bks])

for ext in ("png", "pdf"):
    try:
        p.save(f"figures/fig4_connector_htcd_share.{ext}", dpi=200, verbose=False)
    except OSError:
        p.save(f"figures/fig4_connector_htcd_share_new.{ext}", dpi=200, verbose=False)
print("done")
