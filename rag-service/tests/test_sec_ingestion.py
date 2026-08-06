from rag_service.models import SourceFilter
from rag_service.sec_ingestion import (
    SEC_DATA_ROOT,
    LocalSecFilingIngestor,
    TickerCikLookup,
    load_local_sec_filings,
    parse_sections,
)


def test_ticker_cik_lookup_normalizes_ticker():
    company = TickerCikLookup().company_for(" nvda ")

    assert company is not None
    assert company.cik == "0001045810"
    assert company.company_name == "NVIDIA Corporation"


def test_parse_sections_extracts_item_sections():
    sections = parse_sections(
        """
ITEM 1. Business
Business text.

ITEM 1A. Risk Factors
Risk text.
"""
    )

    assert [section.name for section in sections] == ["Business", "Risk Factors"]
    assert sections[1].text == "Risk text."


def test_load_local_sec_filings_reads_manifest():
    filings = load_local_sec_filings(SEC_DATA_ROOT / "manifest.json")

    assert {filing.ticker for filing in filings} == {"NVDA", "MSFT"}
    assert {filing.form_type for filing in filings} == {"10-Q", "10-K"}
    assert {filing.file_path for filing in filings} == {
        "NVDA/local-10q.txt",
        "MSFT/local-10k.txt",
    }


def test_local_sec_ingestor_returns_section_documents_with_metadata():
    documents = LocalSecFilingIngestor().ingest(["NVDA"], form_types=["10-Q"])

    assert {document.section for document in documents} == {
        "Management's Discussion and Analysis",
        "Risk Factors",
    }
    risk_document = next(document for document in documents if document.section == "Risk Factors")
    assert risk_document.source_type == SourceFilter.SEC
    assert risk_document.source_id == "sec-nvda-10q-risk-factors"
    assert risk_document.metadata["cik"] == "0001045810"
    assert risk_document.metadata["form_type"] == "10-Q"
    assert risk_document.metadata["accession_number"] == "local-nvda-2026q1-10q"
    assert risk_document.metadata["source_path"] == "NVDA/local-10q.txt"
    assert "export licensing uncertainty" in risk_document.text


def test_local_sec_ingestor_filters_by_ticker_and_form_type():
    documents = LocalSecFilingIngestor().ingest(["MSFT"], form_types=["10-K"])

    assert documents
    assert {document.ticker for document in documents} == {"MSFT"}
    assert {document.metadata["form_type"] for document in documents} == {"10-K"}
