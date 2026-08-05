import re
from dataclasses import dataclass

from rag_service.models import SourceFilter


@dataclass(frozen=True)
class SecCompany:
    ticker: str
    cik: str
    company_name: str


@dataclass(frozen=True)
class LocalSecFiling:
    ticker: str
    accession_number: str
    form_type: str
    filing_date: str
    report_period: str
    url: str
    text: str


@dataclass(frozen=True)
class SecSection:
    name: str
    text: str


@dataclass(frozen=True)
class IngestedSecDocument:
    source_id: str
    ticker: str
    source_type: SourceFilter
    title: str
    url: str
    section: str
    text: str
    metadata: dict[str, str]


SEC_COMPANIES = {
    "NVDA": SecCompany("NVDA", "0001045810", "NVIDIA Corporation"),
    "MSFT": SecCompany("MSFT", "0000789019", "Microsoft Corporation"),
}


LOCAL_SEC_FILINGS = (
    LocalSecFiling(
        ticker="NVDA",
        accession_number="local-nvda-2026q1-10q",
        form_type="10-Q",
        filing_date="2026-05-28",
        report_period="2026-04-26",
        url="https://example.com/sec/nvda/local-10q",
        text="""
ITEM 2. Management's Discussion and Analysis
Local SEC filing sample says NVDA management discussed data center demand, product transition timing,
inventory purchase commitments, supplier capacity, and capital allocation for AI infrastructure.

ITEM 1A. Risk Factors
Local SEC filing sample says NVDA risk review should monitor customer concentration, manufacturing
capacity, export licensing uncertainty, and rapid shifts in accelerator demand.
""",
    ),
    LocalSecFiling(
        ticker="MSFT",
        accession_number="local-msft-2026-10k",
        form_type="10-K",
        filing_date="2026-07-30",
        report_period="2026-06-30",
        url="https://example.com/sec/msft/local-10k",
        text="""
ITEM 1. Business
Local SEC filing sample says MSFT business discussion focused on cloud infrastructure, AI services,
productivity software, gaming, security products, and LinkedIn.

ITEM 1A. Risk Factors
Local SEC filing sample says MSFT risk review should monitor cybersecurity, cloud capacity spending,
regulation, competition, and availability of advanced AI infrastructure.
""",
    ),
)


SECTION_HEADER_PATTERN = re.compile(r"^ITEM\s+[0-9A-Z]+\.?\s+(.+)$", re.IGNORECASE)


class TickerCikLookup:
    def __init__(self, companies: dict[str, SecCompany] | None = None):
        self._companies = companies or SEC_COMPANIES

    def company_for(self, ticker: str) -> SecCompany | None:
        return self._companies.get(ticker.strip().upper())


class LocalSecFilingIngestor:
    def __init__(
        self,
        filings: tuple[LocalSecFiling, ...] = LOCAL_SEC_FILINGS,
        cik_lookup: TickerCikLookup | None = None,
    ):
        self._filings = filings
        self._cik_lookup = cik_lookup or TickerCikLookup()

    def ingest(self, tickers: list[str], form_types: list[str] | None = None) -> list[IngestedSecDocument]:
        ticker_set = {ticker.strip().upper() for ticker in tickers if ticker.strip()}
        allowed_forms = {form_type.strip().upper() for form_type in form_types or [] if form_type.strip()}
        return [
            document
            for filing in self._filings
            if filing.ticker in ticker_set and (not allowed_forms or filing.form_type.upper() in allowed_forms)
            for document in self._documents_for_filing(filing)
        ]

    def _documents_for_filing(self, filing: LocalSecFiling) -> list[IngestedSecDocument]:
        company = self._cik_lookup.company_for(filing.ticker)
        if company is None:
            return []

        return [
            IngestedSecDocument(
                source_id=source_id_for(filing, section.name),
                ticker=filing.ticker,
                source_type=SourceFilter.SEC,
                title=f"{company.company_name} local {filing.form_type} filing",
                url=f"{filing.url}#{slugify(section.name)}",
                section=section.name,
                text=section.text,
                metadata={
                    "cik": company.cik,
                    "company_name": company.company_name,
                    "accession_number": filing.accession_number,
                    "form_type": filing.form_type,
                    "filing_date": filing.filing_date,
                    "report_period": filing.report_period,
                },
            )
            for section in parse_sections(filing.text)
        ]


def parse_sections(text: str) -> list[SecSection]:
    sections: list[SecSection] = []
    current_name: str | None = None
    current_lines: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        match = SECTION_HEADER_PATTERN.match(line)
        if match:
            if current_name and current_lines:
                sections.append(SecSection(current_name, " ".join(current_lines)))
            current_name = normalize_section_name(match.group(1))
            current_lines = []
            continue

        if current_name:
            current_lines.append(line)

    if current_name and current_lines:
        sections.append(SecSection(current_name, " ".join(current_lines)))
    return sections


def normalize_section_name(value: str) -> str:
    return " ".join(value.replace("&", "and").split())


def source_id_for(filing: LocalSecFiling, section_name: str) -> str:
    return f"sec-{filing.ticker.lower()}-{filing.form_type.lower().replace('-', '')}-{slugify(section_name)}"


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "section"
