import json

from rag_service.chunking import chunk_documents
from rag_service.corpus import EvidenceDocument
from rag_service.document_store import LocalDocumentStore
from rag_service.documents import ChunkMetadataFilter
from rag_service.models import SourceFilter


def test_local_document_store_is_idempotent_and_persists_ingestion_manifest(tmp_path):
    documents = sample_documents()
    chunks = chunk_documents(documents, max_tokens=40, overlap_tokens=5, ingested_at="2026-08-06T00:00:00Z")
    store = LocalDocumentStore(root=tmp_path)

    first_write = store.persist(documents, chunks)
    second_write = store.persist(documents, chunks)

    assert first_write.raw_document_count == len(documents)
    assert first_write.parsed_document_count == len(documents)
    assert first_write.chunk_count == len(chunks)
    assert first_write.embedding_count == len(chunks)
    assert second_write.raw_document_count == first_write.raw_document_count
    assert second_write.parsed_document_count == first_write.parsed_document_count
    assert second_write.chunk_count == first_write.chunk_count
    assert second_write.embedding_count == first_write.embedding_count

    manifest = json.loads((tmp_path / "manifests" / "ingestion_manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["raw_documents"]) == len(documents)
    assert len(manifest["parsed_documents"]) == len(documents)
    assert len(manifest["chunks"]) == len(chunks)
    assert len(manifest["embeddings"]) == len(chunks)


def test_local_document_store_filters_chunks_by_traceable_metadata(tmp_path):
    documents = sample_documents()
    chunks = chunk_documents(documents, max_tokens=40, overlap_tokens=5, ingested_at="2026-08-06T00:00:00Z")
    store = LocalDocumentStore(root=tmp_path)

    store.persist(documents, chunks)

    sec_chunks = store.query_chunks(
        ChunkMetadataFilter(
            tickers=("NVDA",),
            source_types=(SourceFilter.SEC,),
            published_after="2026-05-01",
            published_before="2026-06-30",
            form_types=("10-Q",),
            sections=("Risk Factors",),
        )
    )
    earnings_chunks = store.query_chunks(
        ChunkMetadataFilter(
            tickers=("NVDA",),
            source_types=(SourceFilter.EARNINGS,),
            fiscal_periods=("2026 Q1",),
        )
    )
    news_chunks = store.query_chunks(
        ChunkMetadataFilter(
            tickers=("NVDA",),
            source_types=(SourceFilter.NEWS,),
            published_after="2026-08-01T00:00:00Z",
            published_before="2026-08-02T00:00:00Z",
        )
    )

    assert [chunk.section for chunk in sec_chunks] == ["Risk Factors"]
    assert sec_chunks[0].metadata["document_url"] == "https://example.com/sec/nvda-10q#risk"
    assert sec_chunks[0].metadata["document_title"] == "NVIDIA local 10-Q filing"
    assert sec_chunks[0].metadata["content_hash"] == sec_chunks[0].content_hash
    assert sec_chunks[0].metadata["chunk_id"] == sec_chunks[0].chunk_id
    assert sec_chunks[0].metadata["provider"] == "local-sec"

    assert [chunk.metadata["topic"] for chunk in earnings_chunks] == ["Gross Margin"]
    assert [chunk.metadata["publisher"] for chunk in news_chunks] == ["Local Market Wire"]


def sample_documents() -> list[EvidenceDocument]:
    return [
        EvidenceDocument(
            source_id="sec-nvda-10q-risk-factors",
            ticker="NVDA",
            source_type=SourceFilter.SEC,
            title="NVIDIA local 10-Q filing",
            url="https://example.com/sec/nvda-10q#risk",
            section="Risk Factors",
            text="NVDA risk factors include export licensing uncertainty and customer concentration.",
            metadata={
                "cik": "0001045810",
                "company_name": "NVIDIA Corporation",
                "form_type": "10-Q",
                "filing_date": "2026-06-01",
                "report_period": "2026-Q1",
            },
            company_name="NVIDIA Corporation",
            published_at="2026-06-01",
            period="2026-Q1",
            provider="local-sec",
        ),
        EvidenceDocument(
            source_id="news-nvda-export-control",
            ticker="NVDA",
            source_type=SourceFilter.NEWS,
            title="NVDA export-control update",
            url="https://example.com/news/nvda/export-control-update",
            section="breaking news",
            text="NVDA investors watched export-control rule changes and China demand.",
            metadata={
                "publisher": "Local Market Wire",
                "published_at": "2026-08-01T13:30:00Z",
                "article_type": "breaking news",
            },
            published_at="2026-08-01T13:30:00Z",
            provider="Local Market Wire",
        ),
        EvidenceDocument(
            source_id="earnings-nvda-2026-q1-gross-margin",
            ticker="NVDA",
            source_type=SourceFilter.EARNINGS,
            title="NVIDIA Q1 2026 earnings call",
            url="https://example.com/earnings/nvda-2026-q1#gross-margin",
            section="Q&A",
            text="The CFO discussed gross margin, product transition costs, and deployment timing.",
            metadata={
                "fiscal_year": "2026",
                "fiscal_quarter": "Q1",
                "speaker": "Colette Kress",
                "role": "CFO",
                "topic": "Gross Margin",
                "call_date": "2026-05-28",
            },
            published_at="2026-05-28",
            period="2026 Q1",
            provider="local-earnings",
        ),
    ]
