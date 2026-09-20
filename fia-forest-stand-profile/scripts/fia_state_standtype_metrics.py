"""Pull volume, mortality, and biomass by stand-size class for every US state.

Fills the gap identified against the RDS-2026-0020 static archive (which only
covers 24 northern states and has no biomass-by-stand-size table at all) by
querying the live FIADB-API /fullreport endpoint directly.

All three metrics use the "sound total-stem bark and wood volume" / biomass
family on a Forest land basis so they're on a consistent, comparable footing:
    volume    -> snum 11287 (live trees, >=5" d.b.h./d.r.c.)
    mortality -> snum 11304 (average annual mortality, >=5" d.b.h./d.r.c.)
    biomass   -> snum 10    (aboveground biomass, >=1" d.b.h./d.r.c. -- FIA's
                             standard biomass convention; matches RDS Table 62-64)

Grouped by rselected="Stand-size class" (Large/Medium/Small diameter, Nonstocked).
cselected="Species group" is required by the API but discarded here -- we only
keep the GRP1 (stand-size class) subtotal per state/metric.

Texas and Alaska have no combined "most recent" evaluation at the whole-state
level -- only regional splits, and those splits are NOT the same vintage:
    Texas(East)      current, 2019-2025      Texas(West)      current, 2014-2023
    Alaska Coastal   current, 2015-2022      Alaska Interior  stale, 2014-2019
Summing those into one "current state" number would silently blend mismatched
vintages into one misleading total. Instead each region is emitted as its own
row (state="TX-East", "TX-West", etc.) with its own report_years, so
mismatched vintages stay visible rather than being hidden inside a merged
total.

Confirmed live against /fullreport/parameters/wc (2026-09-19): USDA dropped
the "Texas(West)" label after EVAL_GRP 482013 (2004-2013) and re-published
every evaluation since (up through 482023, 2014-2023, GROWTH_ACCT now "Y")
under the plain state name "Texas" -- not "Texas(West)". An exact-string
match on "Texas(West)" alone silently stops seeing new evaluations the
moment USDA renames the bucket, so TX-West is resolved against BOTH labels
(see SPLIT_STATE_REGIONS / _best_row_for_name below) rather than either one
alone, so a future rename doesn't quietly freeze this again.

Output: fia_all_states_standtype.csv (long format: state, metric, stand_size_class,
estimate, se, se_percent, plot_count, report_years).
"""
from __future__ import annotations

import logging
import time

import pandas as pd
import requests
from bs4 import BeautifulSoup

from client import FIAClient, FullReportQuery, FIADBAPIError

logger = logging.getLogger(__name__)

PARAMETERS_URL = "https://apps.fs.usda.gov/fiadb-api/fullreport/parameters"

# STATECD (FIPS) -> USPS abbreviation, the 50 states only (territories excluded).
STATECD_TO_ABBR = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO",
    "09": "CT", "10": "DE", "12": "FL", "13": "GA", "15": "HI", "16": "ID",
    "17": "IL", "18": "IN", "19": "IA", "20": "KS", "21": "KY", "22": "LA",
    "23": "ME", "24": "MD", "25": "MA", "26": "MI", "27": "MN", "28": "MS",
    "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH", "34": "NJ",
    "35": "NM", "36": "NY", "37": "NC", "38": "ND", "39": "OH", "40": "OK",
    "41": "OR", "42": "PA", "44": "RI", "45": "SC", "46": "SD", "47": "TN",
    "48": "TX", "49": "UT", "50": "VT", "51": "VA", "53": "WA", "54": "WV",
    "55": "WI", "56": "WY",
}

# States with no single combined-state row in /parameters/wc -- only regional
# splits exist, and (confirmed against the live table) the splits are
# different vintages. Reported as separate "STATE-Region" rows, never summed.
#
# Values are either a single STATE label or a tuple of acceptable aliases for
# the same region -- TX-West needs both because USDA renamed that bucket from
# "Texas(West)" to plain "Texas" partway through its evaluation history (see
# module docstring); matching only the old label would silently stop seeing
# every evaluation published after the rename.
SPLIT_STATE_REGIONS = {
    "AK": {"AK-Coastal": "Alaska Coastal", "AK-Interior": "Alaska Interior"},
    "TX": {"TX-East": "Texas(East)", "TX-West": ("Texas(West)", "Texas")},
}

METRICS = {
    "volume": 11287,
    "mortality": 11304,
    "biomass": 10,
    "growth": 11303,      # average annual net growth, sound total-stem, >=5" d.b.h./d.r.c., forest land
    "removals": 11305,    # average annual removals, sound total-stem, >=5" d.b.h./d.r.c., forest land
    "sawlog": 20,         # net sawlog volume of sawtimber trees, board feet (International 1/4-in), forest land
    "area": 2,            # area of forest land, in acres -- denominator for per-forest-acre density views
}

# area (snum=2) is a condition-level attribute -- pairing it with a tree-level
# cselected like "Species group" returns zero rows (confirmed against the live
# API: "SQL Error: Expected to return DataFrame Table Object"). Every other
# metric here is tree-level and uses "Species group" as its (discarded)
# required cselected.
METRIC_CSELECTED = {"area": "Ownership group"}

REQUEST_DELAY = 0.75  # be polite to a small government server


def fetch_parameter_rows(param: str, session: requests.Session) -> list[dict]:
    """Fetch /fullreport/parameters/<param> and parse it with html5lib.

    pandas.read_html (lxml-backed) silently returns an EMPTY table on these
    pages -- the site's HTML mismatches <th scope=row> open tags with a
    closing </td>, which lxml's stricter parser can't reconcile into rows.
    html5lib implements the actual HTML5 parsing algorithm (what a browser
    does) and recovers all rows correctly. Confirmed against the live site:
    lxml sees 0 rows, html5lib sees 96 (rselected/cselected/pselected),
    752 (snum), or 1140 (wc).
    """
    resp = session.get(f"{PARAMETERS_URL}/{param}", timeout=60)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html5lib")
    thead = soup.find("thead")
    tbody = soup.find("tbody")
    if thead is None or tbody is None:
        raise ValueError(f"No table found on parameters/{param} page")
    cols = [th.get_text(strip=True) for th in thead.find_all("th")]
    rows = []
    for tr in tbody.find_all("tr"):
        vals = [c.get_text(strip=True) for c in tr.find_all(["th", "td"])]
        if vals:
            rows.append(dict(zip(cols, vals)))
    return rows


def _best_row_for_name(wc_rows: list[dict], state_name: str | tuple[str, ...]) -> dict | None:
    """Pick the MOST_RECENT='Y' row for state_name, else the newest by EVAL_GRP.

    state_name may be a single STATE label or a tuple of aliases for the same
    region (e.g. TX-West's "Texas(West)"/"Texas" -- see SPLIT_STATE_REGIONS):
    USDA has been known to rename a region's STATE label between evaluations,
    and matching only the old name would silently stop seeing anything newer.
    """
    names = (state_name,) if isinstance(state_name, str) else state_name
    candidates = [r for r in wc_rows if r.get("STATE", "").strip() in names]
    if not candidates:
        return None
    most_recent = [r for r in candidates if r.get("MOST_RECENT") == "Y"]
    if most_recent:
        return most_recent[0]
    return max(candidates, key=lambda r: r.get("EVAL_GRP", ""))


def get_state_wc_codes(session: requests.Session) -> dict[str, dict]:
    """Return {label: {"eval_grp", "report_years"}} for the current inventory.

    `label` is a 2-letter state abbreviation for ordinary states. For AK/TX
    (see SPLIT_STATE_REGIONS) each region becomes its own label ("AK-Coastal",
    "TX-West", ...) since their regional splits are different survey vintages
    and must not be silently merged into one "current state" number.
    """
    wc_rows = fetch_parameter_rows("wc", session)

    result: dict[str, dict] = {}
    for statecd, abbr in STATECD_TO_ABBR.items():
        if abbr in SPLIT_STATE_REGIONS:
            for label, state_name in SPLIT_STATE_REGIONS[abbr].items():
                row = _best_row_for_name(wc_rows, state_name)
                if row:
                    result[label] = {
                        "eval_grp": row["EVAL_GRP"].strip(),
                        "report_years": row.get("REPORT_YEAR_NM", "").strip(),
                    }
            continue
        candidates = [r for r in wc_rows if r.get("STATECD") == str(int(statecd))]
        row = next((r for r in candidates if r.get("MOST_RECENT") == "Y"), None)
        if row:
            result[abbr] = {
                "eval_grp": row["EVAL_GRP"].strip(),
                "report_years": row.get("REPORT_YEAR_NM", "").strip(),
            }
    return result


def query_standsize_metric(
    client: FIAClient, wc_code: str, snum: int, cselected: str = "Species group"
) -> pd.DataFrame:
    """Run one /fullreport query and return the GRP1 (stand-size class) subtotal."""
    query = FullReportQuery(
        snum=snum,
        wc=wc_code,
        rselected="Stand-size class",
        cselected=cselected,
    )
    result = client.fullreport(query)
    grp1 = result.subtotals.get("GRP1")
    if grp1 is None or grp1.empty:
        return pd.DataFrame(columns=["GRP1", "ESTIMATE", "SE", "PLOT_COUNT"])
    return grp1[["GRP1", "ESTIMATE", "SE", "PLOT_COUNT"]].rename(
        columns={"GRP1": "stand_size_class"}
    )


def build_all_states(out_path: str = "fia_all_states_standtype.csv") -> pd.DataFrame:
    # Build the client first so it constructs its own retry/backoff-hardened
    # session (3 retries, exponential backoff, on both connect errors and
    # 5xx) -- passing in a plain requests.Session() here instead would skip
    # that entirely, leaving every call (including the metadata GET below)
    # with a single attempt against a server that does occasionally time out.
    client = FIAClient()
    client.session.headers["User-Agent"] = "fia-standtype-metrics/0.1 (research use)"
    session = client.session

    logger.info("Resolving current-inventory wc codes for all states...")
    state_wc = get_state_wc_codes(session)
    logger.info("Resolved %d state/region labels", len(state_wc))

    rows: list[dict] = []
    total_calls = len(state_wc) * len(METRICS)
    call_num = 0

    for label, info in sorted(state_wc.items()):
        wc_code, report_years = info["eval_grp"], info["report_years"]
        for metric_name, snum in METRICS.items():
            call_num += 1
            logger.info(
                "[%d/%d] %s / %s (wc=%s)", call_num, total_calls, label, metric_name, wc_code
            )
            try:
                frame = query_standsize_metric(
                    client, wc_code, snum, METRIC_CSELECTED.get(metric_name, "Species group")
                )
            except FIADBAPIError as exc:
                logger.warning("  FAILED %s/%s wc=%s: %s", label, metric_name, wc_code, exc)
                time.sleep(REQUEST_DELAY)
                continue
            time.sleep(REQUEST_DELAY)

            for _, r in frame.iterrows():
                estimate = float(r["ESTIMATE"])
                se = float(r["SE"])
                rows.append(
                    dict(
                        state=label,
                        metric=metric_name,
                        stand_size_class=r["stand_size_class"],
                        estimate=estimate,
                        se=se,
                        se_percent=(se / estimate * 100) if estimate else None,
                        plot_count=int(r["PLOT_COUNT"]),
                        report_years=report_years,
                    )
                )

    df = pd.DataFrame(rows)
    df.to_csv(out_path, index=False)
    logger.info("Wrote %s (%d rows, %d state/region labels)", out_path, len(df), df["state"].nunique())
    return df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    build_all_states()
