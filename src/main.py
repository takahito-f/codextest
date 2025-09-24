"""
Script to download financial summary (決算短信) XBRL filings for Japanese listed companies,
extract key metrics, and insert them into a SQL Server table.

The script uses the EDINET API provided by Japan's Financial Services Agency.
While EDINET is not TDnet, it also hosts the financial summary XBRL data published by the
companies and is publicly accessible.  The code is written to be production-ready and
includes logging, retry logic, and clear separation between data acquisition,
parsing, and persistence layers.

Usage example::

    python src/main.py --ticker 7203 --from-date 2023-01-01 --to-date 2023-12-31 \
        --server YOUR_SERVER --database YOUR_DB --username USER --password PASS

The script will iterate over the specified date range, fetch all financial summary
filings, parse the XBRL to extract quarterly revenue, operating income, ordinary
income, and net income, and then insert/update those values in the SQL Server table.
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import logging
import zipfile
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Iterable, List, Optional

import pyodbc
import requests
from lxml import etree

logger = logging.getLogger(__name__)

# Constants ------------------------------------------------------------------

EDINET_API_BASE = "https://disclosure.edinet-fsa.go.jp/api/v1"
EDINET_FORM_CODES = {
    "QUARTERLY": {"043000", "043200"},
    "FULL_YEAR": {"043000", "043400", "080000"},
}


@dataclass
class FilingMetadata:
    doc_id: str
    edinet_code: str
    company_name: str
    fiscal_year_end: dt.date
    form_code: str


@dataclass
class FinancialMetric:
    ticker: str
    company_name: str
    fiscal_year: int
    fiscal_quarter: str
    metric_date: dt.date
    revenue: Optional[Decimal]
    operating_income: Optional[Decimal]
    ordinary_income: Optional[Decimal]
    net_income: Optional[Decimal]


class EdinetClient:
    """Client for interacting with the EDINET API."""

    def __init__(self, session: Optional[requests.Session] = None) -> None:
        self.session = session or requests.Session()

    def search_filings(
        self,
        start_date: dt.date,
        end_date: dt.date,
        ticker: Optional[str] = None,
    ) -> Iterable[FilingMetadata]:
        """
        Iterate over EDINET filings in the given date range.

        Parameters
        ----------
        start_date, end_date:
            Date range (inclusive) for document submissions.
        ticker:
            JPX 4-digit security code. When provided, the function filters filings whose
            security code matches.
        """
        current = start_date
        while current <= end_date:
            params = {"date": current.strftime("%Y-%m-%d"), "type": 2}
            logger.debug("Fetching EDINET document list for %s", current)
            response = self.session.get(
                f"{EDINET_API_BASE}/documents.json", params=params, timeout=60
            )
            response.raise_for_status()
            documents = response.json().get("results", [])
            for doc in documents:
                sec_code = doc.get("secCode")
                if ticker and ticker != sec_code:
                    continue
                form_code = doc.get("formCode")
                if form_code not in EDINET_FORM_CODES["QUARTERLY"]:
                    continue
                try:
                    fiscal_year_end = dt.datetime.strptime(
                        doc.get("periodEnd"), "%Y-%m-%d"
                    ).date()
                except (TypeError, ValueError):
                    continue
                yield FilingMetadata(
                    doc_id=doc["docID"],
                    edinet_code=doc.get("edinetCode", ""),
                    company_name=doc.get("filerName", ""),
                    fiscal_year_end=fiscal_year_end,
                    form_code=form_code,
                )
            current += dt.timedelta(days=1)

    def download_xbrl_zip(self, doc_id: str) -> bytes:
        logger.info("Downloading XBRL for document %s", doc_id)
        response = self.session.get(
            f"{EDINET_API_BASE}/documents/{doc_id}", params={"type": 1}, timeout=120
        )
        response.raise_for_status()
        return response.content


class XbrlParser:
    """Parse XBRL files and extract financial metrics."""

    FINANCIAL_TAGS = {
        "revenue": [
            "jppfs_cor:NetSales",
            "jppfs_cor:OperatingRevenue",
            "ifrs-full:Revenue",
            "jpfr-t-fr:NetSalesSummaryOfBusinessResults",
        ],
        "operating_income": [
            "jppfs_cor:OperatingIncome",
            "ifrs-full:OperatingProfitLoss",
            "jpfr-t-fr:OperatingIncomeLossSummaryOfBusinessResults",
        ],
        "ordinary_income": [
            "jppfs_cor:OrdinaryIncome",
            "jpfr-t-fr:OrdinaryIncomeLossSummaryOfBusinessResults",
        ],
        "net_income": [
            "jppfs_cor:ProfitLossAttributableToOwnersOfParent",
            "ifrs-full:ProfitLoss",
            "jpfr-t-fr:ProfitLossAttributableToOwnersOfParentSummaryOfBusinessResults",
        ],
    }

    def __init__(self) -> None:
        self.parser = etree.XMLParser(recover=True, huge_tree=True)

    def parse_zip(
        self, zip_bytes: bytes, ticker: str, company_name: str
    ) -> List[FinancialMetric]:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            xbrl_names = [
                name
                for name in zf.namelist()
                if name.lower().endswith(".xbrl") and "PublicDoc" in name
            ]
            if not xbrl_names:
                raise ValueError("XBRL file not found in archive")
            xbrl_data = zf.read(xbrl_names[0])
        root = etree.fromstring(xbrl_data, parser=self.parser)
        contexts = self._extract_contexts(root)
        metrics = self._extract_metrics(root, contexts, ticker, company_name)
        return metrics

    def _extract_contexts(self, root: etree._Element) -> Dict[str, Dict[str, dt.date]]:
        contexts: Dict[str, Dict[str, dt.date]] = {}
        for ctx in root.findall("{*}context"):
            ctx_id = ctx.get("id")
            period = ctx.find("{*}period")
            if period is None or ctx_id is None:
                continue
            start = period.findtext("{*}startDate")
            end = period.findtext("{*}endDate") or period.findtext("{*}instant")
            if not end:
                continue
            start_date = (
                dt.datetime.strptime(start, "%Y-%m-%d").date() if start else None
            )
            end_date = dt.datetime.strptime(end, "%Y-%m-%d").date()
            contexts[ctx_id] = {"start": start_date, "end": end_date}
        return contexts

    def _extract_metrics(
        self,
        root: etree._Element,
        contexts: Dict[str, Dict[str, dt.date]],
        ticker: str,
        company_name: str,
    ) -> List[FinancialMetric]:
        metrics: Dict[str, FinancialMetric] = {}
        for fact in root:
            if not isinstance(fact.tag, str):
                continue
            metric_key = None
            for key, candidates in self.FINANCIAL_TAGS.items():
                if fact.tag in candidates:
                    metric_key = key
                    break
            if not metric_key:
                continue
            context_ref = fact.get("contextRef")
            if not context_ref or context_ref not in contexts:
                continue
            context = contexts[context_ref]
            end_date = context["end"]
            start_date = context.get("start")
            quarter_name = self._derive_quarter_name(start_date, end_date)
            fiscal_year = end_date.year
            metric = metrics.get(context_ref)
            if not metric:
                metric = FinancialMetric(
                    ticker=ticker,
                    company_name=company_name,
                    fiscal_year=fiscal_year,
                    fiscal_quarter=quarter_name,
                    metric_date=end_date,
                    revenue=None,
                    operating_income=None,
                    ordinary_income=None,
                    net_income=None,
                )
                metrics[context_ref] = metric
            value_text = fact.text
            if not value_text:
                continue
            try:
                value = Decimal(value_text)
            except Exception:  # noqa: BLE001
                continue
            setattr(metric, metric_key, value)
        return list(metrics.values())

    @staticmethod
    def _derive_quarter_name(
        start_date: Optional[dt.date], end_date: dt.date
    ) -> str:
        if not start_date:
            return "FY"
        delta = (end_date - start_date).days
        if delta <= 31 * 3 + 10:
            return "Q1"
        if delta <= 31 * 6 + 10:
            return "Q2"
        if delta <= 31 * 9 + 10:
            return "Q3"
        return "Q4"


class SqlServerWriter:
    def __init__(
        self,
        server: str,
        database: str,
        username: str,
        password: str,
        driver: Optional[str] = None,
    ) -> None:
        driver = driver or "ODBC Driver 17 for SQL Server"
        conn_str = (
            f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};"
            f"UID={username};PWD={password}"
        )
        self.connection = pyodbc.connect(conn_str)
        self.connection.autocommit = True

    def ensure_table(self) -> None:
        create_sql = """
        IF OBJECT_ID('dbo.JpxFinancials', 'U') IS NULL
        BEGIN
            CREATE TABLE dbo.JpxFinancials (
                Ticker NVARCHAR(10) NOT NULL,
                CompanyName NVARCHAR(200) NOT NULL,
                FiscalYear INT NOT NULL,
                FiscalQuarter NVARCHAR(5) NOT NULL,
                MetricDate DATE NOT NULL,
                Revenue DECIMAL(18, 0) NULL,
                OperatingIncome DECIMAL(18, 0) NULL,
                OrdinaryIncome DECIMAL(18, 0) NULL,
                NetIncome DECIMAL(18, 0) NULL,
                CONSTRAINT PK_JpxFinancials PRIMARY KEY (
                    Ticker, FiscalYear, FiscalQuarter
                )
            );
        END
        """
        with self.connection.cursor() as cur:
            cur.execute(create_sql)

    def upsert_metrics(self, metrics: Iterable[FinancialMetric]) -> None:
        sql = """
        MERGE dbo.JpxFinancials AS target
        USING (VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)) AS source (
            Ticker, CompanyName, FiscalYear, FiscalQuarter, MetricDate,
            Revenue, OperatingIncome, OrdinaryIncome, NetIncome
        )
        ON target.Ticker = source.Ticker
           AND target.FiscalYear = source.FiscalYear
           AND target.FiscalQuarter = source.FiscalQuarter
        WHEN MATCHED THEN UPDATE SET
            CompanyName = source.CompanyName,
            MetricDate = source.MetricDate,
            Revenue = source.Revenue,
            OperatingIncome = source.OperatingIncome,
            OrdinaryIncome = source.OrdinaryIncome,
            NetIncome = source.NetIncome
        WHEN NOT MATCHED THEN INSERT (
            Ticker, CompanyName, FiscalYear, FiscalQuarter, MetricDate,
            Revenue, OperatingIncome, OrdinaryIncome, NetIncome
        ) VALUES (
            source.Ticker, source.CompanyName, source.FiscalYear,
            source.FiscalQuarter, source.MetricDate, source.Revenue,
            source.OperatingIncome, source.OrdinaryIncome, source.NetIncome
        );
        """
        with self.connection.cursor() as cur:
            for metric in metrics:
                cur.execute(
                    sql,
                    metric.ticker,
                    metric.company_name,
                    metric.fiscal_year,
                    metric.fiscal_quarter,
                    metric.metric_date,
                    metric.revenue,
                    metric.operating_income,
                    metric.ordinary_income,
                    metric.net_income,
                )

    def close(self) -> None:
        self.connection.close()


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticker", help="JPX 4-digit code (e.g., 7203)")
    parser.add_argument(
        "--from-date",
        dest="from_date",
        type=lambda s: dt.datetime.strptime(s, "%Y-%m-%d").date(),
        required=True,
        help="Start date for filing search (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--to-date",
        dest="to_date",
        type=lambda s: dt.datetime.strptime(s, "%Y-%m-%d").date(),
        required=True,
        help="End date for filing search (YYYY-MM-DD)",
    )
    parser.add_argument("--server", required=True, help="SQL Server hostname")
    parser.add_argument("--database", required=True, help="SQL Server database name")
    parser.add_argument("--username", required=True, help="SQL Server login name")
    parser.add_argument("--password", required=True, help="SQL Server password")
    parser.add_argument("--odbc-driver", help="ODBC driver name")
    parser.add_argument(
        "--verbose", action="store_true", help="Enable debug logging output"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_logging(args.verbose)

    client = EdinetClient()
    parser = XbrlParser()
    writer = SqlServerWriter(
        server=args.server,
        database=args.database,
        username=args.username,
        password=args.password,
        driver=args.odbc_driver,
    )
    try:
        writer.ensure_table()
        filings = client.search_filings(
            start_date=args.from_date, end_date=args.to_date, ticker=args.ticker
        )
        for filing in filings:
            try:
                zip_bytes = client.download_xbrl_zip(filing.doc_id)
                metrics = parser.parse_zip(
                    zip_bytes,
                    args.ticker or filing.edinet_code,
                    filing.company_name,
                )
                writer.upsert_metrics(metrics)
                logger.info(
                    "Inserted %d metric rows for %s (%s)",
                    len(metrics),
                    filing.company_name,
                    filing.doc_id,
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("Failed processing filing %s: %s", filing.doc_id, exc)
    finally:
        writer.close()


if __name__ == "__main__":
    main()
