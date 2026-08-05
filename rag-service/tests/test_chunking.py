from rag_service.chunking import chunk_document
from rag_service.corpus import EvidenceDocument
from rag_service.models import SourceFilter


def test_chunk_document_creates_stable_chunk_metadata():
    document = EvidenceDocument(
        source_id="nvda-sec-test",
        ticker="NVDA",
        source_type=SourceFilter.SEC,
        title="NVDA test filing",
        url="https://example.com/nvda-sec-test",
        section="Risk Factors",
        text="one two three four five six seven eight nine ten",
        metadata={"cik": "0001045810", "form_type": "10-Q"},
    )

    chunks = chunk_document(document, max_tokens=4, overlap_tokens=1)

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
    assert chunks[0].metadata == {"cik": "0001045810", "form_type": "10-Q"}
