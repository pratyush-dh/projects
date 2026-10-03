#!/usr/bin/env python3
"""Build blog/index.html from post.md: semantic HTML5, relative image paths (no base64), meta/OG tags."""
import re, os, markdown

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
src = open("post.md", encoding="utf-8").read()

# Split H1 title off; the rest becomes the article body.
m = re.match(r"^# (.+?)\n+\*(.+?)\*\n+(.*)$", src, re.S)
title_text, subtitle, body_md = m.group(1), m.group(2), m.group(3)
seo_title = "Carbon Density by Ecoregion: How Much, How Sure | Pratyush Dhungana"

md = markdown.markdown(body_md, extensions=["tables"])

# Figures: <p><img alt="Figure N. Caption..." src="figures/x.png" /></p> -> <figure><img alt=short loading=lazy><figcaption>caption</figcaption></figure>
def fig(mo):
    caption = mo.group(1)
    src_attr = mo.group(2)
    short = re.split(r"(?<=[a-z0-9%)])\. (?=[A-Z(])", caption, maxsplit=1)[0]
    short = re.sub(r'"', "&quot;", short)
    cap_html = re.sub(r'"', "&quot;", caption)
    return f'<figure>\n<img {src_attr} alt="{short}" loading="lazy" decoding="async"/>\n<figcaption>{cap_html}</figcaption>\n</figure>'

md = re.sub(r'<p><img alt="([^"]*)" (src="[^"]+")\s*/></p>', fig, md)
md = md.replace("<table>", '<div class="table-wrap"><table>').replace("</table>", "</table></div>")

CSS = """
:root{color-scheme:light}
body{font:17px/1.65 Georgia,'Times New Roman',serif;color:#1c1c1a;max-width:760px;margin:0 auto;padding:0 20px 60px;background:#fff}
header.site-nav{font:14px Arial,sans-serif;padding:18px 0;border-bottom:1px solid #e6e5e1;margin-bottom:1.2em;display:flex;gap:1.4em;flex-wrap:wrap}
header.site-nav a{color:#52514e;text-decoration:none}
header.site-nav a:hover{color:#2a78d6;text-decoration:underline}
article > h1{font:700 34px/1.2 Arial,sans-serif;margin:0.2em 0 0.1em}
.subtitle{font-style:italic;color:#52514e;margin:0 0 1.4em}
h2{font:700 24px/1.3 Arial,sans-serif;margin-top:2em}
h3{font:700 19px Arial,sans-serif;margin-top:1.6em}
figure{margin:1.6em -60px}
figure img{width:100%;height:auto;display:block}
figcaption{font:14px/1.5 Arial,sans-serif;color:#52514e;margin:.5em 60px 0}
.table-wrap{overflow-x:auto;margin:1em 0}
table{border-collapse:collapse;width:100%;font:15px Arial,sans-serif;min-width:480px}
th,td{border-bottom:1px solid #ddd;padding:6px 8px;text-align:left}
th{background:#f4f4f2}
em{color:#3b3b39}
a{color:#2a78d6}
code{background:#f4f4f2;padding:0.1em 0.3em;border-radius:3px;font-size:0.9em}
footer.site-foot{font:14px/1.6 Arial,sans-serif;color:#52514e;border-top:1px solid #e6e5e1;margin-top:3em;padding-top:1.2em}
footer.site-foot a{color:#2a78d6}
@media(max-width:900px){figure{margin:1.6em 0}figcaption{margin:.5em 0 0}}
"""

DESC = ("Live-tree carbon density varies about 29-fold across US ecoregions, a statistically robust difference -- "
        "and a look at why the within-region uncertainty is unexpectedly high connects back to this series' "
        "earlier posts on FIA tree height data.")
URL = "https://pratyush-dh.github.io/projects/blog/carbon-by-ecoregion/"
IMG = URL + "figures/h03_map_mean_carbon.png"

html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{seo_title}</title>
<meta name="description" content="{DESC}">
<link rel="canonical" href="{URL}">
<meta property="og:type" content="article">
<meta property="og:title" content="{title_text}">
<meta property="og:description" content="{DESC}">
<meta property="og:image" content="{IMG}">
<meta property="og:url" content="{URL}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title_text}">
<meta name="twitter:description" content="{DESC}">
<meta name="twitter:image" content="{IMG}">
<link rel="icon" href="https://pratyush-dh.github.io/assets/img/favicon.png">
<style>{CSS}</style>
</head>
<body>
<header class="site-nav">
<a href="https://pratyush-dh.github.io/">&larr; Portfolio</a>
<a href="https://pratyush-dh.github.io/projects/blog/htcd4/">&larr; Previous post (HTCD 4)</a>
<a href="https://github.com/pratyush-dh/projects/tree/main/blog/carbon_ecoregion">Code &amp; source</a>
</header>
<article>
<h1>{title_text}</h1>
<p class="subtitle">{subtitle}</p>
{md}
</article>
<footer class="site-foot">
<p>Draft analysis, not peer reviewed and not an official FIA product. Corrections and questions are welcome: <a href="https://github.com/pratyush-dh/projects/issues">open an issue</a>. Source: <a href="https://github.com/pratyush-dh/projects/tree/main/blog/carbon_ecoregion">pratyush-dh/projects</a>. Author: <a href="https://pratyush-dh.github.io/">Pratyush Dhungana</a>.</p>
</footer>
</body>
</html>
"""
open("index.html", "w", encoding="utf-8").write(html)
print("wrote index.html,", len(html), "bytes")
