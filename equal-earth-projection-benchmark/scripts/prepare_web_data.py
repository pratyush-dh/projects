#!/usr/bin/env python3
"""
Builds data/world.json for the interactive web app.

Boundary geometry comes from Natural Earth (for rendering only). Every other
statistic comes from the World Bank Open Data API, one time series per layer:

  - SP.POP.TOTL          total population (-> population density, w/ area)
  - AG.SRF.TOTL.K2       surface area (latest year; population density's denominator)
  - AG.LND.FRST.ZS       forest area, % of land area (source: FAO)
  - EN.GHG.CO2.PC.CE.AR5 CO2 emissions per capita, excl. LULUCF (source: EDGAR/JRC + IEA)
  - SP.URB.TOTL.IN.ZS    urban population, % of total (source: UN World Urbanization Prospects)

World Bank explicitly attributes SP.POP.TOTL to "World Population Prospects,
United Nations (UN), Population Division" -- i.e. this *is* UN population
data, just redistributed through an API that doesn't require a key (the UN
Population Data Portal's own /data/ endpoints now require one). Figures are
official/administrative, not computed from the (simplified) map geometry --
a generalized boundary's own area can differ from the surveyed figure by a
couple of percent.

A separate geometry-derived area (equal-area EPSG:8857) is also stored per
feature, but only as the internal reference for the on-screen "distortion"
readout -- it is never shown to the user as a country's area.

Intended to be re-run periodically (see .github/workflows/update-data.yml)
so the site tracks new World Bank releases automatically.
"""

import datetime
import json
import sys
from pathlib import Path

import geopandas as gpd
import requests

NE_URL = "https://naciscdn.org/naturalearth/110m/cultural/ne_110m_admin_0_countries.zip"
OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "world.json"

WB_BASE = "https://api.worldbank.org/v2"
AREA_INDICATOR = "AG.SRF.TOTL.K2"
SERIES_START_YEAR = 1960

# Map layer id -> World Bank indicator code. Population is handled separately
# (it needs area_km2 to become a density); these three are used as-is.
DIRECT_LAYERS = {
    "forest": "AG.LND.FRST.ZS",
    "co2": "EN.GHG.CO2.PC.CE.AR5",
    "urban": "SP.URB.TOTL.IN.ZS",
}
POP_INDICATOR = "SP.POP.TOTL"

# Natural Earth's ISO_A3_EH is usually a clean ISO 3166-1 alpha-3 code, but a
# few entities still fall back to "-99". Map the ones the World Bank tracks.
ISO_OVERRIDES = {
    "Kosovo": "XKX",
}


def wb_fetch_all(url, params):
    rows = []
    page = 1
    while True:
        r = requests.get(url, params={**params, "page": page}, timeout=30)
        r.raise_for_status()
        meta, page_rows = r.json()
        rows.extend(page_rows or [])
        if page >= meta["pages"]:
            break
        page += 1
    return rows


def wb_real_country_codes():
    rows = wb_fetch_all(f"{WB_BASE}/country", {"format": "json", "per_page": 300})
    return {r["id"] for r in rows if r["region"]["id"] != "NA"}


def wb_series(indicator, valid_codes, end_year):
    """Returns {iso3: [[year, value], ...]} sorted by year ascending, nulls dropped."""
    rows = wb_fetch_all(
        f"{WB_BASE}/country/all/indicator/{indicator}",
        {"format": "json", "per_page": 20000, "date": f"{SERIES_START_YEAR}:{end_year}"},
    )
    series = {}
    for row in rows:
        iso3 = row["countryiso3code"]
        if iso3 not in valid_codes or row["value"] is None:
            continue
        series.setdefault(iso3, []).append([int(row["date"]), row["value"]])
    for points in series.values():
        points.sort(key=lambda p: p[0])
    return series


def resolve_iso3(row):
    if row["NAME"] in ISO_OVERRIDES:
        return ISO_OVERRIDES[row["NAME"]]
    iso = row.get("ISO_A3_EH")
    if iso and iso != "-99":
        return iso
    iso = row.get("ISO_A3")
    if iso and iso != "-99":
        return iso
    return row.get("ADM0_A3")


def latest(series_map, iso3):
    pts = series_map.get(iso3)
    return pts[-1][1] if pts else None


def maybe_int(v):
    return None if v is None or v != v else int(round(v))


def maybe_float(v, nd=1):
    return None if v is None or v != v else round(float(v), nd)


def main():
    current_year = datetime.date.today().year

    print("[*] Loading Natural Earth admin-0 boundaries...")
    world = gpd.read_file(NE_URL).copy()
    world["iso3"] = world.apply(resolve_iso3, axis=1)

    print("[*] Fetching official statistics from the World Bank...")
    valid_codes = wb_real_country_codes()

    pop_series_by_iso = wb_series(POP_INDICATOR, valid_codes, current_year)
    area_series_by_iso = wb_series(AREA_INDICATOR, valid_codes, current_year)
    area_by_iso = {iso: pts[-1][1] for iso, pts in area_series_by_iso.items()}
    global_pop_series = wb_series(POP_INDICATOR, {"WLD"}, current_year).get("WLD", [])

    direct_series_by_layer = {}
    global_series_by_layer = {}
    for layer_id, indicator in DIRECT_LAYERS.items():
        print(f"    - {layer_id} ({indicator})")
        direct_series_by_layer[layer_id] = wb_series(indicator, valid_codes, current_year)
        global_series_by_layer[layer_id] = wb_series(indicator, {"WLD"}, current_year).get("WLD", [])

    print(f"[+] World Bank coverage: {len(area_by_iso)} w/ area, {len(pop_series_by_iso)} w/ population, "
          + ", ".join(f"{len(direct_series_by_layer[l])} w/ {l}" for l in DIRECT_LAYERS))

    # Geometry-derived area (equal-area CRS) -- internal use only, for the
    # distortion readout's baseline. Never surfaced as "a country's area".
    world_eq = world.to_crs(epsg=8857)
    world["geom_area_km2"] = world_eq.geometry.area / 1e6

    world["geometry"] = world.geometry.simplify(0.01, preserve_topology=True)

    area_km2 = world["iso3"].map(lambda c: area_by_iso.get(c))
    population = world["iso3"].map(lambda c: latest(pop_series_by_iso, c))
    pop_density = area_km2.where(area_km2.isna() | (area_km2 == 0), population / area_km2)
    pop_density = pop_density.where(~(area_km2.isna() | population.isna()))

    world["area_km2"] = area_km2
    world["population"] = population
    world["pop_density"] = pop_density
    world["rank_area"] = world["area_km2"].rank(ascending=False, method="min")
    world["rank_pop"] = world["population"].rank(ascending=False, method="min")
    world["rank_density"] = world["pop_density"].rank(ascending=False, method="min")

    layer_counts = {}
    for layer_id in DIRECT_LAYERS:
        series_map = direct_series_by_layer[layer_id]
        current_val = world["iso3"].map(lambda c: latest(series_map, c))
        world[f"{layer_id}_current"] = current_val
        world[f"rank_{layer_id}"] = current_val.rank(ascending=False, method="min")
        layer_counts[layer_id] = int(current_val.notna().sum())

    total_countries = len(world)
    total_rendered_land_area_km2 = float(world["geom_area_km2"].sum())

    features = []
    for _, row in world.iterrows():
        geom = row.geometry.__geo_interface__
        pop_series = pop_series_by_iso.get(row["iso3"], [])
        properties = {
            "name": row["NAME"],
            "iso_a3": row["iso3"],
            "population": maybe_int(row["population"]),
            "area_km2": maybe_float(row["area_km2"]),
            "pop_density": maybe_float(row["pop_density"], 2),
            "rank_pop": maybe_int(row["rank_pop"]),
            "rank_area": maybe_int(row["rank_area"]),
            "rank_density": maybe_int(row["rank_density"]),
            "geom_area_km2": round(float(row["geom_area_km2"]), 1),
            "population_series": [[y, int(v)] for y, v in pop_series],
        }
        for layer_id in DIRECT_LAYERS:
            series = direct_series_by_layer[layer_id].get(row["iso3"], [])
            properties[f"{layer_id}_current"] = maybe_float(row[f"{layer_id}_current"], 2)
            properties[f"rank_{layer_id}"] = maybe_int(row[f"rank_{layer_id}"])
            properties[f"{layer_id}_series"] = [[y, round(v, 3)] for y, v in series]
        features.append({"type": "Feature", "geometry": geom, "properties": properties})

    meta = {
        "total_countries": total_countries,
        "countries_with_area_data": int(world["area_km2"].notna().sum()),
        "countries_with_population_data": int(world["population"].notna().sum()),
        "countries_with_density_data": int(world["pop_density"].notna().sum()),
        "total_rendered_land_area_km2": round(total_rendered_land_area_km2, 1),
        "global_population_series": [[y, int(v)] for y, v in global_pop_series],
        "generated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_boundaries": "Natural Earth 1:110m Cultural Vectors (admin-0 countries)",
        "source_stats": {
            "population": "World Bank Open Data SP.POP.TOTL, sourced from UN World Population Prospects",
            "area": "World Bank Open Data AG.SRF.TOTL.K2",
            "forest": "World Bank Open Data AG.LND.FRST.ZS, sourced from FAO",
            "co2": "World Bank Open Data EN.GHG.CO2.PC.CE.AR5, sourced from EDGAR (JRC/IEA)",
            "urban": "World Bank Open Data SP.URB.TOTL.IN.ZS, sourced from UN World Urbanization Prospects",
        },
    }
    for layer_id in DIRECT_LAYERS:
        meta[f"countries_with_{layer_id}_data"] = layer_counts[layer_id]
        meta[f"global_{layer_id}_series"] = [[y, round(v, 3)] for y, v in global_series_by_layer[layer_id]]

    payload = {"type": "FeatureCollection", "meta": meta, "features": features}

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, separators=(",", ":"))

    size_kb = OUT_PATH.stat().st_size / 1024
    print(f"[+] Wrote {OUT_PATH} ({size_kb:.0f} KB, {total_countries} countries)")


if __name__ == "__main__":
    sys.exit(main())
