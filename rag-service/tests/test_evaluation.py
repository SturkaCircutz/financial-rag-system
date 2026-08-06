from rag_service.evaluation import (
    WorkflowEvaluationInput,
    benchmark_metrics,
    evaluate_quality_gate,
    evaluate_workflow_result,
    generation_metrics,
    load_baseline_metrics,
    load_golden_questions,
    retrieval_metrics,
    reranking_metrics,
)
from rag_service.financial_report import EvidenceClaim, ReportCitation, StructuredFinancialReport
from rag_service.models import SourceFilter
from rag_service.state import RetrievedChunk


def test_loads_golden_questions_by_ticker_source_type_and_report_type():
    questions = load_golden_questions()

    assert {question.question_id for question in questions} == {
        "nvda-sec-export-risk",
        "nvda-news-export-controls",
        "msft-earnings-capex",
    }
    assert questions[0].tickers == ("NVDA",)
    assert questions[0].source_filters == (SourceFilter.SEC,)
    assert questions[0].expected_evidence_ids[0] == "sec-nvda-10q-risk-factors#chunk-001"


def test_retrieval_metrics_cover_recall_mrr_ndcg_diversity_and_metadata_accuracy():
    golden = load_golden_questions()[0]
    chunks = [
        retrieved_chunk(
            "sec-nvda-10q-risk-factors",
            SourceFilter.SEC,
            metadata={"ticker": "NVDA", "source_type": "SEC", "form_type": "10-Q"},
            section="Risk Factors",
        ),
        retrieved_chunk(
            "sec-nvda-10k-risk-factors",
            SourceFilter.SEC,
            metadata={"ticker": "NVDA", "source_type": "SEC", "form_type": "10-K"},
            section="Risk Factors",
        ),
    ]

    metrics = retrieval_metrics(golden, chunks, k=2)

    assert metrics.recall_at_k == 1.0
    assert metrics.mrr == 1.0
    assert metrics.ndcg_at_k == 1.0
    assert metrics.source_diversity == 1.0
    assert metrics.metadata_filter_accuracy == 1.0


def test_retrieval_metrics_expose_misses_and_filter_errors():
    golden = load_golden_questions()[0]
    chunks = [
        retrieved_chunk(
            "generic-risk",
            SourceFilter.NEWS,
            metadata={"ticker": "MSFT", "source_type": "NEWS", "form_type": ""},
            section="Market News",
        )
    ]

    metrics = retrieval_metrics(golden, chunks, k=2)

    assert metrics.recall_at_k == 0.0
    assert metrics.mrr == 0.0
    assert metrics.ndcg_at_k == 0.0
    assert metrics.source_diversity == 0.0
    assert metrics.metadata_filter_accuracy == 0.0


def test_reranking_metrics_measure_preference_and_recall_improvement():
    golden = load_golden_questions()[0]
    raw_chunks = [
        retrieved_chunk("generic-risk", SourceFilter.SEC, rank=1),
        retrieved_chunk("sec-nvda-10k-risk-factors", SourceFilter.SEC, rank=2),
    ]
    reranked_chunks = [
        retrieved_chunk("sec-nvda-10q-risk-factors", SourceFilter.SEC, rank=1),
        retrieved_chunk("sec-nvda-10k-risk-factors", SourceFilter.SEC, rank=2),
    ]

    metrics = reranking_metrics(golden, raw_chunks, reranked_chunks, k=2)

    assert metrics.pairwise_preference_accuracy == 1.0
    assert metrics.recall_improvement == 0.5


def test_generation_metrics_measure_citation_faithfulness_and_tone():
    golden = load_golden_questions()[0]
    context = [retrieved_chunk("sec-nvda-10q-risk-factors", SourceFilter.SEC, citation_id="C1")]

    metrics = generation_metrics(golden, cited_report(), context)

    assert metrics.citation_coverage == 1.0
    assert metrics.unsupported_claim_rate == 0.0
    assert metrics.answer_completeness == 1.0
    assert metrics.tone_compliance == 1.0


def test_quality_gate_blocks_unsupported_claims_and_citation_regressions():
    golden = load_golden_questions()[0]
    bad_report = cited_report(
        citation_ids=["C99"],
        source_citation_ids=["C1"],
        limitations=["Generated from selected cited local RAG context only."],
    )
    evaluation = evaluate_workflow_result(
        golden,
        WorkflowEvaluationInput(
            workflow="mocked_local_graph",
            retrieved_chunks=[retrieved_chunk("sec-nvda-10q-risk-factors", SourceFilter.SEC)],
            reranked_chunks=[retrieved_chunk("sec-nvda-10q-risk-factors", SourceFilter.SEC)],
            selected_context=[retrieved_chunk("sec-nvda-10q-risk-factors", SourceFilter.SEC, citation_id="C1")],
            structured_report=bad_report,
            latency_ms=50,
        ),
        k=1,
    )

    gate = evaluate_quality_gate(evaluation, load_baseline_metrics())

    assert gate.passed is False
    assert any("generation.citation_coverage" in reason for reason in gate.reasons)
    assert any("generation.unsupported_claim_rate" in reason for reason in gate.reasons)
    assert any("generation.tone_compliance" in reason for reason in gate.reasons)


def test_workflow_evaluation_records_latency_and_local_zero_cost():
    golden = load_golden_questions()[0]
    context = [
        retrieved_chunk("sec-nvda-10q-risk-factors", SourceFilter.SEC, citation_id="C1"),
        retrieved_chunk("sec-nvda-10k-risk-factors", SourceFilter.SEC, citation_id="C2"),
    ]

    evaluation = evaluate_workflow_result(
        golden,
        WorkflowEvaluationInput(
            workflow="mocked_local_graph",
            retrieved_chunks=context,
            reranked_chunks=context,
            selected_context=context,
            structured_report=cited_report(),
            prompt="Use cited context only.",
            response_text="Local answer with citation C1.",
            latency_ms=42,
        ),
        k=2,
    )

    assert evaluation.benchmark.workflow == "mocked_local_graph"
    assert evaluation.benchmark.latency_ms == 42
    assert evaluation.benchmark.prompt_tokens > 0
    assert evaluation.benchmark.estimated_cost_usd == 0.0
    assert evaluate_quality_gate(evaluation, load_baseline_metrics()).passed is True


def test_benchmark_metrics_can_estimate_paid_provider_cost_later():
    metrics = benchmark_metrics(
        "openai_future",
        latency_ms=120,
        prompt="one two three",
        response_text="four five",
        prompt_cost_per_1k=0.01,
        completion_cost_per_1k=0.02,
    )

    assert metrics.prompt_tokens == 3
    assert metrics.completion_tokens == 2
    assert metrics.estimated_cost_usd == 0.00007


def cited_report(
    citation_ids: list[str] | None = None,
    source_citation_ids: list[str] | None = None,
    limitations: list[str] | None = None,
) -> StructuredFinancialReport:
    citation_ids = citation_ids or ["C1"]
    source_citation_ids = source_citation_ids or citation_ids
    claim = EvidenceClaim(
        claim="SEC evidence says NVDA risk factors mention export controls. [C1]",
        citation_ids=citation_ids,
    )
    return StructuredFinancialReport(
        executive_summary="Local filing analysis uses cited evidence. [C1]",
        key_evidence=[claim],
        latest_sec_filing_signals=[claim],
        source_citations=[
            ReportCitation(
                citation_id=citation_id,
                evidence_id="sec-nvda-10q-risk-factors#chunk-001",
                source_type=SourceFilter.SEC,
                title="NVIDIA Corporation local 10-Q filing",
                url="https://example.com/sec/nvda/local-10q#risk-factors",
                section="Risk Factors",
                source_metadata={"ticker": "NVDA", "source_type": "SEC", "form_type": "10-Q"},
            )
            for citation_id in source_citation_ids
        ],
        methodology_and_limitations=limitations or [
            "Generated from selected cited local RAG context only.",
            "This is not trading advice and does not place orders.",
        ],
    )


def retrieved_chunk(
    source_id: str,
    source_type: SourceFilter,
    metadata: dict[str, str] | None = None,
    section: str = "Risk Factors",
    rank: int = 1,
    citation_id: str = "C1",
) -> RetrievedChunk:
    metadata = metadata or {"ticker": "NVDA", "source_type": source_type.value, "form_type": "10-Q"}
    return {
        "source_id": source_id,
        "chunk_id": f"{source_id}#chunk-001",
        "evidence_id": f"{source_id}#chunk-001",
        "source_type": source_type,
        "title": "Local source title",
        "url": f"https://example.com/{source_id}",
        "section": section,
        "text": "Risk factors discuss export controls and customer concentration.",
        "content_hash": f"{source_id}-hash",
        "score": 0.8,
        "rank": rank,
        "context_citation_id": citation_id,
        "metadata": {**metadata, "context_citation_id": citation_id},
    }
