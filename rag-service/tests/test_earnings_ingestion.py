from rag_service.earnings_ingestion import (
    EARNINGS_DATA_ROOT,
    LocalEarningsIngestor,
    load_local_earnings_sources,
    parse_earnings_segments,
)
from rag_service.models import SourceFilter


def test_load_local_earnings_sources_reads_manifest():
    sources = load_local_earnings_sources(EARNINGS_DATA_ROOT / "manifest.json")

    assert {source.ticker for source in sources} == {"NVDA", "MSFT"}
    assert {source.source_kind for source in sources} == {"transcript"}
    assert "NVDA/2026-q1-call.txt" in {source.file_path for source in sources}


def test_parse_earnings_segments_extracts_speaker_role_and_topic():
    segments = parse_earnings_segments(
        """
SEGMENT: Prepared Remarks
SPEAKER: Example CEO
ROLE: CEO
TOPIC: Demand
Demand text.

SEGMENT: Q&A
SPEAKER: Example CFO
ROLE: CFO
TOPIC: Margin
Margin text.
"""
    )

    assert [segment.transcript_segment for segment in segments] == ["Prepared Remarks", "Q&A"]
    assert segments[0].speaker == "Example CEO"
    assert segments[1].role == "CFO"
    assert segments[1].topic == "Margin"


def test_local_earnings_ingestor_returns_latest_quarter_segments_with_metadata():
    documents = LocalEarningsIngestor().ingest(["NVDA"], latest_only=True)

    assert {document.section for document in documents} == {"Prepared Remarks", "Q&A", "Guidance"}
    guidance = next(document for document in documents if document.section == "Guidance")
    assert guidance.source_type == SourceFilter.EARNINGS
    assert guidance.metadata["fiscal_quarter"] == "Q1"
    assert guidance.metadata["fiscal_year"] == "2026"
    assert guidance.metadata["speaker"] == "Colette Kress"
    assert guidance.metadata["role"] == "CFO"
    assert guidance.metadata["topic"] == "Supply Availability"
    assert guidance.metadata["transcript_segment"] == "Guidance"
    assert "supply availability" in guidance.text
