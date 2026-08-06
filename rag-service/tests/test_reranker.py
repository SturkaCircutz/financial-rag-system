from rag_service.models import ReportType, SourceFilter
from rag_service.reranker import (
    CrossEncoderReranker,
    LocalCrossEncoderScorer,
    RerankInput,
    UnavailableCrossEncoderScorer,
    rerank_input_for,
)
from rag_service.state import RetrievedChunk


def test_rerank_input_combines_question_report_intent_and_candidate_chunk():
    chunk = retrieved_chunk(
        source_id="nvda-risk",
        source_type=SourceFilter.SEC,
        text="Export licensing uncertainty affected AI accelerator shipment timing.",
        metadata={"ticker": "NVDA", "form_type": "10-Q"},
    )

    rerank_input = rerank_input_for(
        chunk,
        user_question="Which risk factors mention export controls?",
        report_intent=ReportType.FILING_ANALYSIS,
    )

    assert rerank_input.user_question == "Which risk factors mention export controls?"
    assert rerank_input.report_intent == ReportType.FILING_ANALYSIS
    assert rerank_input.chunk_id == "nvda-risk#chunk-001"
    assert rerank_input.source_type == SourceFilter.SEC
    assert "Export licensing uncertainty" in rerank_input.chunk_text
    assert rerank_input.metadata["form_type"] == "10-Q"


def test_cross_encoder_reranker_batches_scores_and_reorders_candidates():
    scorer = CountingScorer([0.12, 0.91, 0.2])
    reranker = CrossEncoderReranker(scorer=scorer, batch_size=2, min_relevance_score=0.18)
    chunks = [
        retrieved_chunk("generic-risk", SourceFilter.SEC, "Generic risk checklist text.", score=0.9, rank=1),
        retrieved_chunk(
            "specific-export-risk",
            SourceFilter.SEC,
            "Risk factors mention export licensing uncertainty and customer concentration.",
            score=0.4,
            rank=2,
        ),
        retrieved_chunk("market-note", SourceFilter.NEWS, "Market update text.", score=0.3, rank=3),
    ]

    result = reranker.rerank(
        chunks,
        user_question="Which risk factors discuss export licensing uncertainty?",
        report_intent=ReportType.FILING_ANALYSIS,
    )

    assert scorer.batch_sizes == [2, 1]
    assert [chunk["source_id"] for chunk in result.chunks] == ["specific-export-risk", "market-note"]
    assert result.chunks[0]["reranker_score"] == 0.91
    assert result.chunks[0]["reranker_rank"] == 1
    assert result.diagnostics[0].chunk_id == "specific-export-risk#chunk-001"
    assert result.diagnostics[-1].reason == "below_min_relevance"


def test_local_cross_encoder_improves_known_answer_over_raw_hybrid_order():
    reranker = CrossEncoderReranker(scorer=LocalCrossEncoderScorer(), min_relevance_score=0.18)
    raw_hybrid_candidates = [
        retrieved_chunk(
            "generic-earnings",
            SourceFilter.EARNINGS,
            "Revenue, guidance, margin, and cash flow are common earnings review topics.",
            score=0.9,
            rank=1,
            metadata={"ticker": "MSFT", "source_type": "EARNINGS", "fiscal_quarter": "Q4"},
        ),
        retrieved_chunk(
            "amy-hood-capex",
            SourceFilter.EARNINGS,
            "Amy Hood discussed capital expenditure priorities for AI infrastructure capacity.",
            score=0.4,
            rank=2,
            metadata={
                "ticker": "MSFT",
                "source_type": "EARNINGS",
                "fiscal_quarter": "Q4",
                "speaker": "Amy Hood",
                "topic": "Capital Expenditure",
            },
        ),
    ]

    result = reranker.rerank(
        raw_hybrid_candidates,
        user_question="Which speaker discussed capital expenditure priorities?",
        report_intent=ReportType.EARNINGS_BRIEF,
    )

    assert raw_hybrid_candidates[0]["source_id"] == "generic-earnings"
    assert result.chunks[0]["source_id"] == "amy-hood-capex"
    generic_diagnostic = next(
        diagnostic
        for diagnostic in result.diagnostics
        if diagnostic.chunk_id == "generic-earnings#chunk-001"
    )
    assert result.chunks[0]["reranker_score"] > generic_diagnostic.reranker_score


def test_reranker_excludes_low_confidence_evidence():
    reranker = CrossEncoderReranker(scorer=CountingScorer([0.4, 0.05]), min_relevance_score=0.18)
    chunks = [
        retrieved_chunk("relevant", SourceFilter.SEC, "Relevant filing text.", rank=1),
        retrieved_chunk("weak", SourceFilter.NEWS, "Unrelated market color.", rank=2),
    ]

    result = reranker.rerank(
        chunks,
        user_question="Which filing discussed risk factors?",
        report_intent=ReportType.FILING_ANALYSIS,
    )

    assert [chunk["source_id"] for chunk in result.chunks] == ["relevant"]
    weak_diagnostic = next(diagnostic for diagnostic in result.diagnostics if diagnostic.chunk_id == "weak#chunk-001")
    assert weak_diagnostic.included is False
    assert weak_diagnostic.low_confidence is True
    assert weak_diagnostic.reason == "below_min_relevance"


def test_reranker_falls_back_to_hybrid_score_when_model_unavailable():
    reranker = CrossEncoderReranker(scorer=UnavailableCrossEncoderScorer())
    chunks = [
        retrieved_chunk("lower", SourceFilter.SEC, "Lower score text.", score=0.2, rank=2),
        retrieved_chunk("higher", SourceFilter.SEC, "Higher score text.", score=0.8, rank=1),
    ]

    result = reranker.rerank(
        chunks,
        user_question="Which filing discussed risk factors?",
        report_intent=ReportType.FILING_ANALYSIS,
    )

    assert result.fallback_used is True
    assert result.status == "fallback_unavailable"
    assert [chunk["source_id"] for chunk in result.chunks] == ["higher", "lower"]
    assert {chunk["reranker_status"] for chunk in result.chunks} == {"fallback_unavailable"}


def test_reranker_latency_stays_inside_budget_for_local_candidates():
    reranker = CrossEncoderReranker(latency_budget_ms=250)
    chunks = [
        retrieved_chunk(
            f"candidate-{index}",
            SourceFilter.SEC,
            "Risk factors discuss export controls, customer concentration, and supply constraints.",
            rank=index,
        )
        for index in range(1, 25)
    ]

    result = reranker.rerank(
        chunks,
        user_question="Which risk factors discuss export controls?",
        report_intent=ReportType.FILING_ANALYSIS,
    )

    assert result.status == "completed"
    assert result.latency_ms <= 250


class CountingScorer:
    available = True

    def __init__(self, scores: list[float]):
        self._scores = scores
        self.batch_sizes: list[int] = []

    def score_batch(self, inputs: list[RerankInput]) -> list[float]:
        self.batch_sizes.append(len(inputs))
        batch_scores = self._scores[:len(inputs)]
        self._scores = self._scores[len(inputs):]
        return batch_scores


def retrieved_chunk(
    source_id: str,
    source_type: SourceFilter,
    text: str,
    score: float = 0.5,
    rank: int = 1,
    metadata: dict[str, str] | None = None,
) -> RetrievedChunk:
    return {
        "source_id": source_id,
        "chunk_id": f"{source_id}#chunk-001",
        "evidence_id": f"{source_id}#chunk-001",
        "source_type": source_type,
        "title": "Local candidate",
        "url": f"https://example.com/{source_id}",
        "section": "Risk Factors",
        "text": text,
        "content_hash": f"{source_id}-hash",
        "score": score,
        "rank": rank,
        "bm25_score": score,
        "vector_score": 0.0,
        "fusion_score": score,
        "matched_by": ["bm25"],
        "filter_path": ["metadata_filter:included"],
        "metadata": metadata or {"ticker": "NVDA", "source_type": source_type.value},
    }
