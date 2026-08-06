import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

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
    file_path: str


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


SECTION_HEADER_PATTERN = re.compile(r"^ITEM\s+[0-9A-Z]+\.?\s+(.+)$", re.IGNORECASE)
SEC_DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "sec"


class TickerCikLookup:
    def __init__(self, companies: dict[str, SecCompany] | None = None):
        self._companies = companies or SEC_COMPANIES

    def company_for(self, ticker: str) -> SecCompany | None:
        return self._companies.get(ticker.strip().upper())


class LocalSecFilingIngestor:
    def __init__(
        self,
        filings: tuple[LocalSecFiling, ...] | None = None,
        cik_lookup: TickerCikLookup | None = None,
        data_root: Path = SEC_DATA_ROOT,
        manifest_path: Path | None = None,
    ):
        self._data_root = data_root
        self._filings = filings if filings is not None else load_local_sec_filings(manifest_path or data_root / "manifest.json")
        self._cik_lookup = cik_lookup or TickerCikLookup()

    def ingest(
        self,
        tickers: list[str],
        ciks: list[str] | None = None,
        form_types: list[str] | None = None,
        accession_numbers: list[str] | None = None,
        filed_after: str | None = None,
        filed_before: str | None = None,
    ) -> list[IngestedSecDocument]:
        ticker_set = {ticker.strip().upper() for ticker in tickers if ticker.strip()}
        cik_set = {cik.strip().lstrip("0") for cik in ciks or [] if cik.strip()}
        allowed_forms = {form_type.strip().upper() for form_type in form_types or [] if form_type.strip()}
        allowed_accessions = {
            accession_number.strip()
            for accession_number in accession_numbers or []
            if accession_number.strip()
        }
        after = date.fromisoformat(filed_after) if filed_after else None
        before = date.fromisoformat(filed_before) if filed_before else None
        return [
            document
            for filing in self._filings
            if self._matches_filing(
                filing,
                ticker_set,
                cik_set,
                allowed_forms,
                allowed_accessions,
                after,
                before,
            )
            for document in self._documents_for_filing(filing)
        ]

    def _matches_filing(
        self,
        filing: LocalSecFiling,
        ticker_set: set[str],
        cik_set: set[str],
        allowed_forms: set[str],
        allowed_accessions: set[str],
        after: date | None,
        before: date | None,
    ) -> bool:
        company = self._cik_lookup.company_for(filing.ticker)
        if company is None:
            return False
        if ticker_set and filing.ticker not in ticker_set:
            return False
        if cik_set and company.cik.lstrip("0") not in cik_set:
            return False
        if allowed_forms and filing.form_type.upper() not in allowed_forms:
            return False
        if allowed_accessions and filing.accession_number not in allowed_accessions:
            return False
        filing_date = date.fromisoformat(filing.filing_date)
        if after and filing_date < after:
            return False
        if before and filing_date > before:
            return False
        return True

    def _documents_for_filing(self, filing: LocalSecFiling) -> list[IngestedSecDocument]:
        company = self._cik_lookup.company_for(filing.ticker)
        if company is None:
            return []

        filing_text = self._read_filing_text(filing)
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
                    "source_path": filing.file_path,
                },
            )
            for section in parse_sections(filing_text)
        ]

    def _read_filing_text(self, filing: LocalSecFiling) -> str:
        path = self._data_root / filing.file_path
        try:
            return path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"Local SEC filing file not found: {path}") from exc


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


def load_local_sec_filings(manifest_path: Path) -> tuple[LocalSecFiling, ...]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    filings = manifest.get("filings", [])
    return tuple(local_sec_filing_from_manifest(item) for item in filings)


def local_sec_filing_from_manifest(item: dict[str, str]) -> LocalSecFiling:
    return LocalSecFiling(
        ticker=item["ticker"].strip().upper(),
        accession_number=item["accession_number"],
        form_type=item["form_type"].strip().upper(),
        filing_date=item["filing_date"],
        report_period=item["report_period"],
        url=item["url"],
        file_path=item["file_path"],
    )


def normalize_section_name(value: str) -> str:
    return " ".join(value.replace("&", "and").split())


def source_id_for(filing: LocalSecFiling, section_name: str) -> str:
    return f"sec-{filing.ticker.lower()}-{filing.form_type.lower().replace('-', '')}-{slugify(section_name)}"


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "section"
