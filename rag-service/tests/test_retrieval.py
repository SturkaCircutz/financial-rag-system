from rag_service.documents import ChunkMetadataFilter
from rag_service.models import SourceFilter
from rag_service.retrieval import rank_agent_results, retrieve_agent_results, rewrite_finance_query
from rag_service.state import AgentResult


def test_rank_agent_results_scores_question_terms_first():
    agent_results: list[AgentResult] = [
        {
            "source_id": "generic-source",
            "chunk_id": "generic-source#chunk-001",
            "source_type": SourceFilter.SEC,
            "status": "completed",
            "evidence_id": "generic-source#chunk-001",
            "title": "Generic risk evidence",
            "url": "https://example.com/generic",
            "section": "Risk Factors",
            "text": "Revenue, margins, and liquidity are useful filing review topics.",
            "content_hash": "generic-hash",
            "metadata": {"ticker": "NVDA", "source_type": "SEC"},
        },
        {
            "source_id": "export-controls-source",
            "chunk_id": "export-controls-source#chunk-001",
            "source_type": SourceFilter.SEC,
            "status": "completed",
            "evidence_id": "export-controls-source#chunk-001",
            "title": "Export controls and risk factors",
            "url": "https://example.com/export-controls",
            "section": "Risk Factors",
            "text": "Export controls create supply and demand risk for AI accelerator shipments.",
            "content_hash": "export-controls-hash",
            "metadata": {"ticker": "NVDA", "source_type": "SEC"},
        },
    ]

    ranked_chunks = rank_agent_results(agent_results, "export controls risk")

    assert ranked_chunks[0]["source_id"] == "export-controls-source"
    assert ranked_chunks[0]["chunk_id"] == "export-controls-source#chunk-001"
    assert ranked_chunks[0]["evidence_id"] == "export-controls-source#chunk-001"
    assert ranked_chunks[0]["score"] > ranked_chunks[1]["score"]
    assert ranked_chunks[0]["bm25_score"] > 0


def test_hybrid_retriever_can_retrieve_semantic_only_candidates():
    agent_results = [
        agent_result(
            source_id="generic-margin-source",
            text="Gross margin and product cost are useful earnings review topics.",
            section="Earnings Call",
            source_type=SourceFilter.EARNINGS,
        ),
        agent_result(
            source_id="cash-pressure-source",
            text="Liquidity stress increased as customers delayed payments.",
            section="Risk Factors",
            source_type=SourceFilter.SEC,
        ),
    ]

    result = retrieve_agent_results(agent_results, "cash pressure")

    assert result.chunks[0]["source_id"] == "cash-pressure-source"
    assert result.chunks[0]["bm25_score"] == 0
    assert result.chunks[0]["vector_score"] > 0
    assert result.chunks[0]["matched_by"] == ["vector"]


def test_hybrid_retriever_applies_metadata_filters_before_ranking():
    agent_results = [
        agent_result(
            source_id="nvda-10k-risk",
            text="Annual filing risk factors discuss export restrictions.",
            section="Risk Factors",
            source_type=SourceFilter.SEC,
            metadata={
                "ticker": "NVDA",
                "source_type": "SEC",
                "form_type": "10-K",
                "published_at": "2026-03-15",
                "period": "2026-FY",
            },
        ),
        agent_result(
            source_id="nvda-10q-risk",
            text="Quarterly filing risk factors discuss export restrictions.",
            section="Risk Factors",
            source_type=SourceFilter.SEC,
            metadata={
                "ticker": "NVDA",
                "source_type": "SEC",
                "form_type": "10-Q",
                "published_at": "2026-06-01",
                "period": "2026-Q1",
            },
        ),
        agent_result(
            source_id="msft-10q-risk",
            text="Quarterly filing risk factors discuss cloud capacity.",
            section="Risk Factors",
            source_type=SourceFilter.SEC,
            metadata={
                "ticker": "MSFT",
                "source_type": "SEC",
                "form_type": "10-Q",
                "published_at": "2026-06-01",
                "period": "2026-Q1",
            },
        ),
    ]

    result = retrieve_agent_results(
        agent_results,
        "export restrictions",
        filters=ChunkMetadataFilter(
            tickers=("NVDA",),
            source_types=(SourceFilter.SEC,),
            published_after="2026-05-01",
            published_before="2026-06-30",
            form_types=("10-Q",),
            sections=("Risk Factors",),
        ),
    )

    assert [chunk["source_id"] for chunk in result.chunks] == ["nvda-10q-risk"]
    assert result.chunks[0]["filter_path"] == [
        "ticker:included:NVDA",
        "source_type:included:SEC",
        "published_at:included:2026-06-01",
        "form_type:included:10-Q",
        "section:included:Risk Factors",
        "metadata_filter:included",
    ]


def test_hybrid_retriever_diagnostics_explain_excluded_chunks():
    agent_results = [
        agent_result(
            source_id="nvda-q1-margin",
            text="Gross margin improved in the latest quarter.",
            section="Q&A",
            source_type=SourceFilter.EARNINGS,
            metadata={
                "ticker": "NVDA",
                "source_type": "EARNINGS",
                "period": "2026 Q1",
                "fiscal_year": "2026",
                "fiscal_quarter": "Q1",
            },
        ),
        agent_result(
            source_id="nvda-q4-margin",
            text="Gross margin improved in the prior quarter.",
            section="Q&A",
            source_type=SourceFilter.EARNINGS,
            metadata={
                "ticker": "NVDA",
                "source_type": "EARNINGS",
                "period": "2025 Q4",
                "fiscal_year": "2025",
                "fiscal_quarter": "Q4",
            },
        ),
    ]

    result = retrieve_agent_results(
        agent_results,
        "profitability outlook",
        filters=ChunkMetadataFilter(
            tickers=("NVDA",),
            source_types=(SourceFilter.EARNINGS,),
            fiscal_periods=("2026 Q1",),
        ),
    )

    excluded = next(diagnostic for diagnostic in result.diagnostics if diagnostic.source_id == "nvda-q4-margin")
    included = next(diagnostic for diagnostic in result.diagnostics if diagnostic.source_id == "nvda-q1-margin")

    assert result.chunks[0]["source_id"] == "nvda-q1-margin"
    assert excluded.included is False
    assert "period:excluded:2025 Q4" in excluded.filter_path
    assert included.included is True


def test_query_rewriting_expands_financial_aliases():
    rewritten = rewrite_finance_query("capex and export controls")

    assert "capital" in rewritten
    assert "expenditure" in rewritten
    assert "licensing" in rewritten
    assert "restrictions" in rewritten


def agent_result(
    source_id: str,
    text: str,
    section: str,
    source_type: SourceFilter,
    metadata: dict[str, str] | None = None,
) -> AgentResult:
    metadata = metadata or {"ticker": "NVDA", "source_type": source_type.value}
    return {
        "source_id": source_id,
        "chunk_id": f"{source_id}#chunk-001",
        "source_type": source_type,
        "status": "completed",
        "evidence_id": f"{source_id}#chunk-001",
        "title": "Local evidence title",
        "url": f"https://example.com/{source_id}",
        "section": section,
        "text": text,
        "content_hash": f"{source_id}-hash",
        "metadata": metadata,
    }
