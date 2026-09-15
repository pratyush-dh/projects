"""FIADB-API client for the USDA Forest Service EVALIDator estimation endpoint.

Wraps the public /fullreport endpoint (https://apps.fs.usda.gov/fiadb-api/fullreport).

SCOPE NOTE
----------
/fullreport is an ESTIMATION endpoint. It returns grouped population estimates
(with sampling errors), never row-level TREE/COND/PLOT records. Every
rselected/cselected/pselected grouping option collapses to a GROUP BY on
classed/binned values (confirmed by inspecting the SQL_GROUPBY column at
/fullreport/parameters/rselected) -- there is no parameter combination that
returns raw records through this API. For row-level FIA data, use DataMart's
static file releases (when accessible) instead.

Untested against the live endpoint: no network access in the authoring
environment. Verify against a known-good query (e.g. the "Land Use - Major"
example in the official docs, snum=79 wc=102020) before relying on this.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Literal

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

FULLREPORT_URL = "https://apps.fs.usda.gov/fiadb-api/fullreport"

OutputFormat = Literal["NJSON", "JSON", "NHTML", "HTML", "NXML", "XML"]
ForestDef = Literal["FIADEF", "RPADEF"]
TemporalBasis = Literal[
    "CURRENT",
    "PREVIOUS",
    "CURRENT IF AVAILABLE ELSE PREVIOUS",
    "PREVIOUS IF AVAILABLE ELSE CURRENT",
    "ACCOUNTING",
]


@dataclass
class FullReportQuery:
    """Parameters for a single /fullreport request.

    wc, snum, rselected, and cselected are required by the API. Valid values
    for wc/snum/rselected/cselected/pselected come from
    /fullreport/parameters/<name>.
    """

    wc: int | str
    snum: int | str
    rselected: str
    cselected: str
    pselected: str | None = None
    strFilter: str | None = None
    sdenom: int | str | None = None
    rtime: TemporalBasis | None = None
    ctime: TemporalBasis | None = None
    ptime: TemporalBasis | None = None
    estOnly: Literal["Y"] | None = None
    FIAorRPA: ForestDef = "FIADEF"
    outputFormat: OutputFormat = "NJSON"

    def to_params(self) -> dict[str, Any]:
        """Build the request parameter dict, dropping unset optional fields."""
        params = {
            "wc": self.wc,
            "snum": self.snum,
            "rselected": self.rselected,
            "cselected": self.cselected,
            "pselected": self.pselected,
            "strFilter": self.strFilter,
            "sdenom": self.sdenom,
            "rtime": self.rtime,
            "ctime": self.ctime,
            "ptime": self.ptime,
            "estOnly": self.estOnly,
            "FIAorRPA": self.FIAorRPA,
            "outputFormat": self.outputFormat,
        }
        return {k: v for k, v in params.items() if v is not None}


@dataclass
class FullReportResult:
    """Parsed response from /fullreport.

    `sql` is the exact Oracle SQL the API ran to produce the estimate --
    useful for provenance logging and for reverse-mapping FIADB table/column
    names (this is what the schema scraper also mines, at a different point
    in the API).
    """

    estimates: pd.DataFrame
    subtotals: dict[str, pd.DataFrame] = field(default_factory=dict)
    totals: pd.DataFrame | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def sql(self) -> str | None:
        return self.metadata.get("sql")


class FIADBAPIError(RuntimeError):
    """Raised on transport failure, HTTP error, or a malformed/empty response."""


class FIAClient:
    """Thin, resilient client for the FIADB-API /fullreport endpoint.

    Parameters
    ----------
    timeout:
        Per-request timeout in seconds.
    max_retries:
        Retries for connection errors and 5xx responses, with exponential
        backoff. 4xx responses (bad parameters) are never retried -- they
        indicate a query error, not a transient failure.
    session:
        Inject a pre-configured requests.Session (e.g. for testing, or to
        set a custom User-Agent identifying your use case to the FS).
    """

    def __init__(
        self,
        timeout: float = 60.0,
        max_retries: int = 3,
        session: requests.Session | None = None,
    ) -> None:
        self.timeout = timeout
        self.session = session or self._build_session(max_retries)

    @staticmethod
    def _build_session(max_retries: int) -> requests.Session:
        session = requests.Session()
        retry = Retry(
            total=max_retries,
            backoff_factor=1.5,
            status_forcelist=(500, 502, 503, 504),
            allowed_methods=("GET", "POST"),
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def fullreport(self, query: FullReportQuery) -> FullReportResult:
        """Submit a query to /fullreport and return parsed NJSON results.

        Uses POST (form-encoded) rather than GET to avoid URL length limits
        when strFilter contains long SQL expressions.
        """
        params = query.to_params()
        if params.get("outputFormat") not in ("NJSON", None):
            logger.warning(
                "outputFormat=%s requested; fullreport() only parses NJSON. "
                "Use .raw() to get the response unparsed for other formats.",
                params.get("outputFormat"),
            )

        try:
            resp = self.session.post(FULLREPORT_URL, data=params, timeout=self.timeout)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise FIADBAPIError(f"Request to {FULLREPORT_URL} failed: {exc}") from exc

        try:
            data = resp.json()
        except ValueError as exc:
            raise FIADBAPIError(
                f"Non-JSON response from fullreport "
                f"(first 200 chars): {resp.text[:200]!r}"
            ) from exc

        if "estimates" not in data:
            raise FIADBAPIError(
                "No 'estimates' key in response; the API likely rejected the "
                f"query parameters. Response keys: {list(data.keys())}"
            )

        estimates = pd.DataFrame(data["estimates"])

        subtotals: dict[str, pd.DataFrame] = {}
        if data.get("subtotals"):
            for key, rows in data["subtotals"].items():
                subtotals[key] = pd.DataFrame(rows)

        # `totals` is a single flat dict of scalars (one row), unlike
        # `estimates`/`subtotals` which are lists of row-dicts -- pandas
        # can't build a DataFrame from a dict of scalars without wrapping
        # it in a list first.
        totals = pd.DataFrame([data["totals"]]) if data.get("totals") else None

        return FullReportResult(
            estimates=estimates,
            subtotals=subtotals,
            totals=totals,
            metadata=data.get("metadata", {}),
        )

    def raw(self, query: FullReportQuery) -> requests.Response:
        """Submit a query and return the raw Response (for non-NJSON formats)."""
        params = query.to_params()
        try:
            resp = self.session.post(FULLREPORT_URL, data=params, timeout=self.timeout)
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            raise FIADBAPIError(f"Request to {FULLREPORT_URL} failed: {exc}") from exc


if __name__ == "__main__":
    # Smoke test using the example from the official docs: land use by
    # major category, Delaware 2020 inventory (wc=102020).
    logging.basicConfig(level=logging.INFO)
    client = FIAClient()
    query = FullReportQuery(
        snum=79,
        wc=102020,
        rselected="Land Use - Major",
        cselected="Land use",
    )
    result = client.fullreport(query)
    print(result.estimates.head())
    print("SQL used:", result.sql)
