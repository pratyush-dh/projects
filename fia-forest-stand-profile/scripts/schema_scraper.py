"""Scrape FIADB-API parameter tables to build a machine-readable FIADB schema/join map.

Each /fullreport/parameters/<name> page lists valid values for a fullreport
parameter (rselected, cselected, pselected, snum, wc). For the classed
grouping parameters (rselected/cselected/pselected) the page also includes
the literal SQL_SELECT / SQL_JOIN / SQL_GROUPBY fragments used to compute
that grouping -- e.g. "Forest type" resolves to
`LEFT OUTER JOIN FS_FIADB.REF_FOREST_TYPE ... ON (REF_FOREST_TYPE.VALUE = COND.FORTYPCD)`.

Scraping these gives a real (if partial -- only columns exposed as grouping
options) FIADB table/column/join map without needing DataMart access or
guesswork against the EVALIDator UI.

Untested against the live site: no network access in the authoring
environment. Requires `beautifulsoup4` in addition to requests/pandas:
    pip install beautifulsoup4 --break-system-packages
(pandas.read_html uses bs4/lxml under the hood to parse the HTML tables.)
"""

from __future__ import annotations

import io
import json
import logging
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd
import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://apps.fs.usda.gov/fiadb-api/fullreport/parameters"
PARAMETER_NAMES = ["rselected", "cselected", "pselected", "snum", "wc"]

# FS_FIADB.TABLE_NAME references (fully qualified, e.g. in SQL_JOIN).
# Case-insensitive: the site's own SQL fragments aren't consistently cased.
_QUALIFIED_TABLE_RE = re.compile(r"\bFS_FIADB\.([A-Za-z_]+)\b", re.IGNORECASE)
# Short alias.column references (e.g. COND.FORTYPCD, cond.aspect, T.AGENTCD).
# Case-insensitive for the same reason -- rows mix COND.FORTYPCD and
# cond.aspect style references even within the same parameter table.
_ALIAS_COLUMN_RE = re.compile(r"\b([A-Za-z][A-Za-z_]{0,15})\.[A-Za-z_]+\b")

# Known short aliases used throughout the parameter tables -> canonical table.
# Matched case-insensitively; values are the canonical (uppercase) table name.
KNOWN_TABLE_ALIASES = {
    "COND": "COND",
    "C": "COND",
    "TREE": "TREE",
    "T": "TREE",
    "PLOT": "PLOT",
    "P": "PLOT",
    "PLOTGEOM": "PLOTGEOM",
    "PG": "PLOTGEOM",
}


@dataclass
class ParameterEntry:
    parameter: str  # which parameter page this came from
    label_var: str  # human-readable option shown in the EVALIDator UI
    db_var: str | None  # underlying column, e.g. "C.ALSTKCD"
    attribute_list: str | None
    sql_select: str | None
    sql_join: str | None
    sql_groupby: str | None
    referenced_tables: list[str]


def _extract_referenced_tables(*sql_fragments: str | None) -> list[str]:
    """Pull distinct FIADB table names out of SQL fragments."""
    tables: set[str] = set()
    for frag in sql_fragments:
        if not frag:
            continue
        tables.update(m.upper() for m in _QUALIFIED_TABLE_RE.findall(frag))
        for alias in _ALIAS_COLUMN_RE.findall(frag):
            canonical = KNOWN_TABLE_ALIASES.get(alias.upper())
            if canonical:
                tables.add(canonical)
    return sorted(tables)


def fetch_parameter_table(
    parameter: str,
    session: requests.Session,
    timeout: float = 60.0,
) -> pd.DataFrame:
    """Fetch and parse the HTML table at /fullreport/parameters/<parameter>."""
    url = f"{BASE_URL}/{parameter}"
    resp = session.get(url, timeout=timeout)
    resp.raise_for_status()
    tables = pd.read_html(io.StringIO(resp.text))
    if not tables:
        raise ValueError(f"No HTML tables found at {url}")
    # The parameter table is consistently the largest table on the page
    # (there may be small nav/footer tables too).
    return max(tables, key=len)


def parse_parameter_entries(parameter: str, df: pd.DataFrame) -> list[ParameterEntry]:
    """Convert a raw parameter DataFrame into structured ParameterEntry records.

    Column sets differ by parameter: snum/wc tables carry ATTRIBUTE_NBR/EVALID
    style columns rather than SQL_SELECT/SQL_JOIN/SQL_GROUPBY. Missing columns
    are filled with None rather than raising, since not every parameter page
    has SQL fragments to offer.
    """
    entries: list[ParameterEntry] = []
    cols = {c.upper(): c for c in df.columns}

    def get(row: pd.Series, name: str) -> str | None:
        col = cols.get(name)
        if col is None:
            return None
        val = row[col]
        return None if pd.isna(val) else str(val)

    for _, row in df.iterrows():
        label_var = (
            get(row, "LABEL_VAR")
            or get(row, "ATTRIBUTE_DESCR")
            or get(row, "EVALID")
        )
        if not label_var:
            continue
        sql_select = get(row, "SQL_SELECT")
        sql_join = get(row, "SQL_JOIN")
        sql_groupby = get(row, "SQL_GROUPBY")
        entries.append(
            ParameterEntry(
                parameter=parameter,
                label_var=label_var,
                db_var=get(row, "DB_VAR"),
                attribute_list=get(row, "ATTRIBUTE_LIST"),
                sql_select=sql_select,
                sql_join=sql_join,
                sql_groupby=sql_groupby,
                referenced_tables=_extract_referenced_tables(
                    sql_select, sql_join, sql_groupby
                ),
            )
        )
    return entries


def build_schema(
    parameters: list[str] = PARAMETER_NAMES,
    request_delay: float = 1.0,
) -> dict[str, list[dict]]:
    """Fetch all parameter tables and return {parameter: [entry_dict, ...]}.

    request_delay throttles requests between parameter pages -- this is a
    small public government server not designed for bulk scraping; be polite.
    """
    session = requests.Session()
    session.headers["User-Agent"] = (
        "fia-schema-scraper/0.1 (research use -- replace with your contact info)"
    )

    schema: dict[str, list[dict]] = {}
    for i, parameter in enumerate(parameters):
        logger.info("Fetching parameter table: %s", parameter)
        df = fetch_parameter_table(parameter, session)
        entries = parse_parameter_entries(parameter, df)
        schema[parameter] = [asdict(e) for e in entries]
        logger.info("  -> %d entries", len(entries))
        if i < len(parameters) - 1:
            time.sleep(request_delay)
    return schema


def summarize_join_graph(schema: dict[str, list[dict]]) -> dict[str, list[str]]:
    """Build {table: [tables it co-occurs with via a shared SQL fragment]}.

    This is a coarse co-occurrence graph, not a precise foreign-key graph --
    two tables appearing in the same SQL_JOIN doesn't always mean a direct
    FK relationship. Use it as a starting map for docs/fiadb_schema.md, then
    verify individual joins against the FIADB user guide before relying on them.
    """
    graph: dict[str, set[str]] = {}
    for entries in schema.values():
        for entry in entries:
            tables = entry["referenced_tables"]
            for t in tables:
                graph.setdefault(t, set()).update(x for x in tables if x != t)
    return {k: sorted(v) for k, v in graph.items()}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    schema = build_schema()
    schema_path = Path("fiadb_schema.json")
    schema_path.write_text(json.dumps(schema, indent=2))
    logger.info("Wrote %s (%d parameters)", schema_path, len(schema))

    graph = summarize_join_graph(schema)
    graph_path = Path("fiadb_join_graph.json")
    graph_path.write_text(json.dumps(graph, indent=2))
    logger.info("Wrote %s (%d tables)", graph_path, len(graph))
