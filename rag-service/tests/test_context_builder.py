from rag_service.context_builder import ContextBuilder, ContextBuilderConfig
from rag_service.models import ReportType, SourceFilter
from rag_service.state import RetrievedChunk


def test_context_builder_is_deterministic_and_enforces_token_budget():
    chunks = [
        retrieved_chunk(
            "sec-risk",
            SourceFilter.SEC,
            "Risk factors discuss export controls, customer concentration, supply constraints, and demand shifts.",
            reranker_score=0.8,
            published_at="2026-05-28",
        ),
        retrieved_chunk(
            "news-export",
            SourceFilter.NEWS,
            "Recent news says export-control rule changes affected China demand and investor reaction.",
            reranker_score=0.7,
            published_at="2026-08-01T13:30:00Z",
        ),
        retrieved_chunk(
            "earnings-supply",
            SourceFilter.EARNINGS,
            "Management guidance depends on supply availability and customer deployment timing.",
            reranker_score=0.6,
            published_at="2026-05-29",
        ),
    ]
    builder = ContextBuilder(ContextBuilderConfig(max_context_tokens=24, max_context_items=3, max_item_tokens=10))

    first = builder.build(chunks, SourceFilter.defaults(), "What changed in export controls?", ReportType.COMPANY_BRIEF)
    second = builder.build(chunks, SourceFilter.defaults(), "What changed in export controls?", ReportType.COMPANY_BRIEF)

    assert [chunk["chunk_id"] for chunk in first.chunks] == [chunk["chunk_id"] for chunk in second.chunks]
    assert first.total_tokens <= 24
    assert sum(chunk["context_token_count"] for chunk in first.chunks) <= 24
    assert all(chunk["context_span_end_token"] <= 24 for chunk in first.chunks)


def test_context_builder_maps_every_context_item_to_citation_metadata():
    result = ContextBuilder().build(
        [
            retrieved_chunk(
                "sec-risk",
                SourceFilter.SEC,
                "Risk factors mention export licensing uncertainty and customer concentration.",
                metadata={
                    "ticker": "NVDA",
                    "source_type": "SEC",
                    "document_title": "NVIDIA local 10-Q filing",
                    "document_url": "https://example.com/sec/nvda",
                    "form_type": "10-Q",
                    "published_at": "2026-05-28",
                },
            )
        ],
        [SourceFilter.SEC],
        "Which filing mentions export licensing uncertainty?",
        ReportType.FILING_ANALYSIS,
    )

    selected = result.chunks[0]
    citation = result.citation_map[0]

    assert selected["context_citation_id"] == "C1"
    assert selected["metadata"]["context_citation_id"] == "C1"
    assert selected["metadata"]["context_span_start_token"] == "0"
    assert selected["metadata"]["context_span_end_token"] == str(selected["context_span_end_token"])
    assert citation.citation_id == "C1"
    assert citation.chunk_id == selected["chunk_id"]
    assert citation.source_metadata["document_title"] == "NVIDIA local 10-Q filing"


def test_context_builder_keeps_source_diversity_across_requested_sources():
    chunks = [
        retrieved_chunk("sec-risk", SourceFilter.SEC, "Filing risk factors discuss export uncertainty.", reranker_score=0.9),
        retrieved_chunk("news-reaction", SourceFilter.NEWS, "News reaction says investors watched export controls.", reranker_score=0.3),
        retrieved_chunk(
            "earnings-supply",
            SourceFilter.EARNINGS,
            "Earnings guidance depends on supply availability.",
            reranker_score=0.3,
        ),
    ]

    result = ContextBuilder().build(
        chunks,
        SourceFilter.defaults(),
        "Summarize recent signals.",
        ReportType.COMPANY_BRIEF,
    )

    assert {chunk["source_type"] for chunk in result.chunks} == {
        SourceFilter.SEC,
        SourceFilter.NEWS,
        SourceFilter.EARNINGS,
    }


def test_context_builder_prefers_primary_source_for_filing_analysis():
    news = retrieved_chunk(
        "news-risk",
        SourceFilter.NEWS,
        "News mentions filing risk factors and export controls.",
        reranker_score=0.7,
    )
    filing = retrieved_chunk(
        "sec-risk",
        SourceFilter.SEC,
        "SEC filing risk factors mention export controls.",
        reranker_score=0.7,
    )

    result = ContextBuilder().build(
        [news, filing],
        [SourceFilter.NEWS, SourceFilter.SEC],
        "Which filing risk factors changed?",
        ReportType.FILING_ANALYSIS,
    )

    assert result.chunks[0]["source_type"] == SourceFilter.SEC


def test_context_builder_prefers_recent_material_news_for_event_context():
    old_generic = retrieved_chunk(
        "old-generic",
        SourceFilter.NEWS,
        "Older article discusses broad market activity.",
        reranker_score=0.5,
        published_at="2025-01-01T00:00:00Z",
    )
    recent_material = retrieved_chunk(
        "recent-material",
        SourceFilter.NEWS,
        "Recent article discusses material export controls and demand risk.",
        reranker_score=0.5,
        published_at="2026-08-01T00:00:00Z",
    )

    result = ContextBuilder().build(
        [old_generic, recent_material],
        [SourceFilter.NEWS],
        "What recent event changed export controls?",
        ReportType.EVENT_DRIVEN,
    )

    assert result.chunks[0]["source_id"] == "recent-material"
    assert result.chunks[0]["recency_score"] > result.chunks[-1]["recency_score"]


def test_context_builder_preserves_positive_and_negative_evidence_when_available():
    chunks = [
        retrieved_chunk(
            "positive-demand",
            SourceFilter.EARNINGS,
            "Management described strong demand growth and improved customer deployments.",
            reranker_score=0.8,
        ),
        retrieved_chunk(
            "negative-risk",
            SourceFilter.SEC,
            "Risk factors cite customer concentration pressure and supply constraints.",
            reranker_score=0.7,
        ),
        retrieved_chunk(
            "neutral-note",
            SourceFilter.NEWS,
            "Market note describes the trading range.",
            reranker_score=0.6,
        ),
    ]

    result = ContextBuilder().build(
        chunks,
        [SourceFilter.EARNINGS, SourceFilter.SEC],
        "Compare bullish and bearish signals.",
        ReportType.COMPANY_BRIEF,
    )

    assert {"positive", "negative"} <= {chunk["evidence_signal"] for chunk in result.chunks}


def test_context_builder_preserves_uncertainty_and_timestamps():
    uncertain = retrieved_chunk(
        "guidance-uncertainty",
        SourceFilter.EARNINGS,
        "Guidance depends on uncertain supply availability and customer timing.",
        reranker_score=0.7,
        published_at="2026-05-29",
    )
    positive = retrieved_chunk(
        "demand-growth",
        SourceFilter.EARNINGS,
        "Management described strong demand growth.",
        reranker_score=0.8,
        published_at="2026-05-29",
    )

    result = ContextBuilder().build(
        [positive, uncertain],
        [SourceFilter.EARNINGS],
        "What does guidance depend on?",
        ReportType.EARNINGS_BRIEF,
    )

    selected_uncertainty = next(chunk for chunk in result.chunks if chunk["source_id"] == "guidance-uncertainty")
    assert selected_uncertainty["evidence_signal"] == "uncertainty"
    assert selected_uncertainty["metadata"]["published_at"] == "2026-05-29"
    assert result.citation_map[0].source_metadata["published_at"] == "2026-05-29"


def test_context_builder_filters_near_duplicate_chunks():
    first = retrieved_chunk(
        "dup-risk-1",
        SourceFilter.SEC,
        "Risk factors discuss export controls and customer concentration.",
        content_hash="same-hash",
    )
    duplicate = retrieved_chunk(
        "dup-risk-2",
        SourceFilter.SEC,
        "Risk factors discuss export controls and customer concentration.",
        content_hash="same-hash",
    )

    result = ContextBuilder().build(
        [first, duplicate],
        [SourceFilter.SEC],
        "Which risk factors changed?",
        ReportType.FILING_ANALYSIS,
    )

    assert len(result.chunks) == 1
    assert any(diagnostic.reason == "near_duplicate" for diagnostic in result.diagnostics)


def retrieved_chunk(
    source_id: str,
    source_type: SourceFilter,
    text: str,
    reranker_score: float = 0.7,
    published_at: str = "2026-06-01",
    metadata: dict[str, str] | None = None,
    content_hash: str | None = None,
) -> RetrievedChunk:
    return {
        "source_id": source_id,
        "chunk_id": f"{source_id}#chunk-001",
        "evidence_id": f"{source_id}#chunk-001",
        "source_type": source_type,
        "title": "Local source title",
        "url": f"https://example.com/{source_id}",
        "section": "Risk Factors",
        "text": text,
        "content_hash": content_hash or f"{source_id}-hash",
        "score": reranker_score,
        "rank": 1,
        "bm25_score": reranker_score,
        "vector_score": 0.0,
        "fusion_score": reranker_score,
        "matched_by": ["bm25"],
        "filter_path": ["metadata_filter:included"],
        "reranker_score": reranker_score,
        "reranker_rank": 1,
        "reranker_status": "completed",
        "low_confidence": False,
        "metadata": metadata or {
            "ticker": "NVDA",
            "source_type": source_type.value,
            "published_at": published_at,
            "document_title": "Local source title",
            "document_url": f"https://example.com/{source_id}",
        },
    }
