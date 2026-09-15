"""Pull volume/biomass/growth/removals/mortality/sawlog/area by county x stand-size
class for every state, for the county drill-down view.

One query per state per metric returns EVERY county in that state at once
(cselected="County code and name" cross-tabs against rselected="Stand-size
class") -- so this is the same ~52-state-sized call budget as the state-level
pull, not one call per county. Confirmed against the live API for Delaware.

County labels come back as "`10001 10001 DE Kent" -- the middle token is the
5-digit county FIPS (state FIPS + county FIPS), which matches the `id` field
used by us-atlas county topojson features, so no separate FIPS lookup is
needed.
"""
from __future__ import annotations

import logging
import re
import time

import pandas as pd
import requests

from client import FIAClient, FIADBAPIError
from fia_state_standtype_metrics import get_state_wc_codes, query_standsize_metric, METRICS, METRIC_CSELECTED

REQUEST_DELAY = 0.75
COUNTY_LABEL_RE = re.compile(r"^(\d{4,5})\s+([A-Z]{2})\s+(.+)$")


def query_county_metric(client: FIAClient, wc_code: str, snum: int) -> pd.DataFrame:
    from client import FullReportQuery

    query = FullReportQuery(
        snum=snum, wc=wc_code, rselected="Stand-size class", cselected="County code and name"
    )
    result = client.fullreport(query)
    est = result.estimates
    if est.empty:
        return pd.DataFrame(columns=["stand_size_class", "county_fips", "county_name", "estimate", "se", "se_percent", "plot_count"])

    def parse_county(raw: str):
        cleaned = re.sub(r"^`\d+\s*", "", raw).strip()
        m = COUNTY_LABEL_RE.match(cleaned)
        # States whose FIPS code starts with 0 (01,02,04,05,06,08,09) have the
        # leading zero stripped from the site's own numeric county code (e.g.
        # Alabama's Autauga shows as "1001", not "01001") -- zero-pad back to
        # the standard 5-digit county FIPS used by county boundary topojson.
        return (m.group(1).zfill(5), m.group(3)) if m else (None, cleaned)

    def parse_class(raw: str) -> str:
        return re.sub(r"^`\d+\s*", "", raw).strip()

    out = pd.DataFrame({
        "stand_size_class": est["GRP1"].map(parse_class),
        "county_fips": est["GRP2"].map(lambda v: parse_county(v)[0]),
        "county_name": est["GRP2"].map(lambda v: parse_county(v)[1]),
        "estimate": est["ESTIMATE"].astype(float),
        "se": est["SE"].astype(float),
        "se_percent": est["SE_PERCENT"].astype(float),
        "plot_count": est["PLOT_COUNT"].astype(int),
    })
    return out


def build_county_data(out_path: str = "fia_county_data.csv") -> pd.DataFrame:
    session = requests.Session()
    session.headers["User-Agent"] = "fia-county-pull/0.1 (research use)"
    client = FIAClient(session=session)

    logging.info("Resolving current-inventory wc codes for all states...")
    state_wc = get_state_wc_codes(session)
    logging.info("Resolved %d state/region labels", len(state_wc))

    rows = []
    total_calls = len(state_wc) * len(METRICS)
    call_num = 0

    for label, info in sorted(state_wc.items()):
        wc_code, report_years = info["eval_grp"], info["report_years"]
        for metric_name, snum in METRICS.items():
            call_num += 1
            logging.info("[%d/%d] %s / %s (wc=%s)", call_num, total_calls, label, metric_name, wc_code)
            try:
                frame = query_county_metric(client, wc_code, snum)
            except FIADBAPIError as exc:
                logging.warning("  FAILED %s/%s: %s", label, metric_name, exc)
                time.sleep(REQUEST_DELAY)
                continue
            time.sleep(REQUEST_DELAY)

            for _, r in frame.iterrows():
                if not r["county_fips"]:
                    continue
                rows.append(dict(
                    state=label, metric=metric_name, stand_size_class=r["stand_size_class"],
                    county_fips=r["county_fips"], county_name=r["county_name"],
                    estimate=r["estimate"], se=r["se"], se_percent=r["se_percent"],
                    plot_count=r["plot_count"], report_years=report_years,
                ))

    df = pd.DataFrame(rows)
    df.to_csv(out_path, index=False)
    logging.info("Wrote %s (%d rows, %d states, %d counties)", out_path, len(df),
                 df["state"].nunique(), df["county_fips"].nunique())
    return df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    build_county_data()
