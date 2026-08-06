from rag_service.chunking import chunk_document
from rag_service.corpus import EvidenceDocument
from rag_service.models import SourceFilter


def test_sec_chunking_creates_section_aware_overlapping_chunks_with_canonical_metadata():
    document = EvidenceDocument(
        source_id="nvda-sec-test",
        ticker="NVDA",
        source_type=SourceFilter.SEC,
        title="NVDA test filing",
        url="https://example.com/nvda-sec-test",
        section="Risk Factors",
        text="one two three four five six seven eight nine ten",
        metadata={
            "cik": "0001045810",
            "company_name": "NVIDIA Corporation",
            "form_type": "10-Q",
            "filing_date": "2026-06-01",
            "report_period": "2026-Q1",
        },
    )

    chunks = chunk_document(document, max_tokens=4, overlap_tokens=1, ingested_at="2026-08-06T00:00:00Z")

    assert [chunk.chunk_id for chunk in chunks] == [
        "nvda-sec-test#chunk-001",
        "nvda-sec-test#chunk-002",
        "nvda-sec-test#chunk-003",
    ]
    assert chunks[0].source_id == "nvda-sec-test"
    assert chunks[0].ticker == "NVDA"
    assert chunks[0].section == "Risk Factors"
    assert chunks[0].text == "one two three four"
    assert chunks[1].text == "four five six seven"
    assert len(chunks[0].content_hash) == 64
    assert chunks[0].metadata["source_id"] == "nvda-sec-test"
    assert chunks[0].metadata["source_type"] == "SEC"
    assert chunks[0].metadata["ticker"] == "NVDA"
    assert chunks[0].metadata["company_name"] == "NVIDIA Corporation"
    assert chunks[0].metadata["published_at"] == "2026-06-01"
    assert chunks[0].metadata["ingested_at"] == "2026-08-06T00:00:00Z"
    assert chunks[0].metadata["document_url"] == "https://example.com/nvda-sec-test"
    assert chunks[0].metadata["document_title"] == "NVDA test filing"
    assert chunks[0].metadata["section"] == "Risk Factors"
    assert chunks[0].metadata["period"] == "2026-Q1"
    assert chunks[0].metadata["provider"] == "local-sec"
    assert chunks[0].metadata["chunk_id"] == "nvda-sec-test#chunk-001"
    assert chunks[0].metadata["content_hash"] == chunks[0].content_hash
    assert chunks[0].metadata["form_type"] == "10-Q"


def test_news_chunking_prefers_article_paragraph_chunks():
    document = EvidenceDocument(
        source_id="nvda-news-test",
        ticker="NVDA",
        source_type=SourceFilter.NEWS,
        title="NVDA paragraph article",
        url="https://example.com/news/nvda-test",
        section="analysis",
        text="First paragraph keeps one article idea.\n\nSecond paragraph keeps another article idea.",
        metadata={"published_at": "2026-08-01T13:30:00Z", "publisher": "Local Market Wire"},
    )

    chunks = chunk_document(document, max_tokens=20, overlap_tokens=1)

    assert [chunk.text for chunk in chunks] == [
        "First paragraph keeps one article idea.",
        "Second paragraph keeps another article idea.",
    ]
    assert chunks[0].metadata["provider"] == "Local Market Wire"
    assert chunks[0].metadata["published_at"] == "2026-08-01T13:30:00Z"


def test_earnings_chunking_keeps_speaker_turns_intact_when_possible():
    document = EvidenceDocument(
        source_id="earnings-nvda-test",
        ticker="NVDA",
        source_type=SourceFilter.EARNINGS,
        title="NVDA test earnings call",
        url="https://example.com/earnings/nvda-test",
        section="Q&A",
        text="The CFO discussed gross margin, product transition costs, and deployment timing.",
        metadata={
            "fiscal_year": "2026",
            "fiscal_quarter": "Q1",
            "speaker": "Colette Kress",
            "role": "CFO",
            "topic": "Gross Margin",
        },
    )

    chunks = chunk_document(document, max_tokens=20, overlap_tokens=1)

    assert len(chunks) == 1
    assert chunks[0].text == document.text
    assert chunks[0].metadata["speaker"] == "Colette Kress"
    assert chunks[0].metadata["period"] == "2026 Q1"
