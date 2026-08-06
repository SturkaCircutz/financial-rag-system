from dataclasses import asdict

from rag_service.context_builder import ContextBuilder
from rag_service.documents import ChunkMetadataFilter
from rag_service.financial_report import (
    financial_report_generator_from_env,
    flatten_report_to_key_findings,
)
from rag_service.models import (
    Citation,
    Diagnostics,
    GenerateReportResponse,
    SourceCoverage,
    SourceFilter,
)
from rag_service.operations import record_graph_node
from rag_service.retrieval import retrieve_agent_results
from rag_service.reranker import CrossEncoderReranker
from rag_service.source_memory import LocalSourceMemory
from rag_service.state import AgentResult, RagGraphState, RetrievedChunk, TraceEvent

SOURCE_MEMORY = LocalSourceMemory()
RERANKER = CrossEncoderReranker(exclude_low_confidence=False)
CONTEXT_BUILDER = ContextBuilder()
REPORT_GENERATOR = financial_report_generator_from_env()


def append_trace(state: RagGraphState, node: str, status: str, detail: str) -> list[TraceEvent]:
    record_graph_node(node, status, detail)
    return [*state.get("trace", []), {"node": node, "status": status, "detail": detail}]


def plan_request(state: RagGraphState) -> RagGraphState:
    request = state["request"]
    source_filters = request.source_filters or SourceFilter.defaults()
    return {
        "normalized_tickers": [ticker.strip().upper() for ticker in request.tickers if ticker.strip()],
        "source_filters": list(dict.fromkeys(source_filters)),
        "diagnostics": {
            "mode": "local_retrieval",
            "ragServiceStatus": "running",
            "retrievalStatus": "not_started",
            "generationStatus": "not_started",
        },
        "trace": append_trace(state, "plan_request", "completed", "normalized request"),
    }


def pass_through(state: RagGraphState) -> RagGraphState:
    return {}


def collect_sec(state: RagGraphState) -> RagGraphState:
    return collect_source(state, SourceFilter.SEC)


def collect_news(state: RagGraphState) -> RagGraphState:
    return collect_source(state, SourceFilter.NEWS)


def collect_earnings(state: RagGraphState) -> RagGraphState:
    return collect_source(state, SourceFilter.EARNINGS)


def collect_source(state: RagGraphState, source_filter: SourceFilter) -> RagGraphState:
    memory_result = SOURCE_MEMORY.collect(source_filter, state["normalized_tickers"])
    results: list[AgentResult] = memory_result.chunks
    store_detail = ""
    if memory_result.store_write:
        store_detail = f" and persisted {memory_result.store_write.chunk_count} total stored chunks"
    return {
        "agent_results": [*state.get("agent_results", []), *results],
        "trace": append_trace(
            state,
            f"{source_filter.value.lower()}_agent",
            "completed",
            (
                f"loaded {len(memory_result.manifests)} source manifests "
                f"and {len(memory_result.chunk_pointers)} chunk pointers"
                f"{store_detail}"
            ),
        ),
    }


def retrieve_chunks(state: RagGraphState) -> RagGraphState:
    retrieval_result = retrieve_agent_results(
        state.get("agent_results", []),
        build_retrieval_query(state),
        filters=build_retrieval_metadata_filter(state),
    )
    chunks = retrieval_result.chunks
    diagnostics = {**state.get("diagnostics", {}), "retrievalStatus": "completed"}
    return {
        "retrieved_chunks": chunks,
        "retrieval_diagnostics": [asdict(diagnostic) for diagnostic in retrieval_result.diagnostics],
        "diagnostics": diagnostics,
        "trace": append_trace(
            state,
            "hybrid_retriever",
            "completed",
            f"retrieved {len(chunks)} chunks from {len(retrieval_result.diagnostics)} diagnostic events",
        ),
    }


def rerank_chunks(state: RagGraphState) -> RagGraphState:
    request = state["request"]
    result = RERANKER.rerank(
        state.get("retrieved_chunks", []),
        user_question=request.question,
        report_intent=request.report_type,
    )
    diagnostics = {
        **state.get("diagnostics", {}),
        "rerankerStatus": result.status,
        "rerankerLatencyMs": str(result.latency_ms),
    }
    return {
        "retrieved_chunks": result.chunks,
        "rerank_diagnostics": [asdict(diagnostic) for diagnostic in result.diagnostics],
        "diagnostics": diagnostics,
        "trace": append_trace(
            state,
            "reranker",
            result.status,
            (
                f"reranked {len(result.diagnostics)} candidates "
                f"to {len(result.chunks)} chunks in {result.latency_ms}ms"
            ),
        ),
    }


def build_context(state: RagGraphState) -> RagGraphState:
    request = state["request"]
    result = CONTEXT_BUILDER.build(
        state.get("retrieved_chunks", []),
        state.get("source_filters", SourceFilter.defaults()),
        question=request.question,
        report_type=request.report_type,
    )
    diagnostics = {
        **state.get("diagnostics", {}),
        "contextTokenCount": str(result.total_tokens),
        "contextTokenBudget": str(result.max_tokens),
    }
    return {
        "selected_context": result.chunks,
        "context_diagnostics": [asdict(diagnostic) for diagnostic in result.diagnostics],
        "context_citation_map": [asdict(citation) for citation in result.citation_map],
        "diagnostics": diagnostics,
        "trace": append_trace(
            state,
            "context_builder",
            "completed",
            f"packed {len(result.chunks)} chunks into {result.total_tokens}/{result.max_tokens} tokens",
        ),
    }


def generate_report(state: RagGraphState) -> RagGraphState:
    request = state["request"]
    normalized_tickers = state["normalized_tickers"]
    selected_context = state.get("selected_context", [])
    generation_result = REPORT_GENERATOR.generate(
        request,
        normalized_tickers,
        selected_context,
    )
    report = generation_result.report
    citations = [
        Citation(
            evidence_id=citation.evidence_id,
            source_type=citation.source_type,
            title=citation.title,
            url=citation.url,
            section=citation.section,
            source_metadata=citation.source_metadata,
        )
        for citation in report.source_citations
    ]
    diagnostics = {
        **state.get("diagnostics", {}),
        "mode": generation_result.provider,
        "ragServiceStatus": "completed",
        "generationStatus": "completed",
        "reportValidationStatus": generation_result.validation_status,
        "reportRepairAttempted": str(generation_result.repair_attempted).lower(),
        "hallucinationWarningCount": str(len(generation_result.hallucination_warnings)),
    }
    response = GenerateReportResponse(
        summary=report.executive_summary,
        key_findings=flatten_report_to_key_findings(report),
        citations=citations,
        source_coverage=source_coverage(selected_context),
        diagnostics=Diagnostics(**diagnostics),
    )
    return {
        "response": response,
        "structured_report": report.model_dump(mode="json", by_alias=True),
        "generation_prompt": generation_result.prompt,
        "generation_warnings": generation_result.hallucination_warnings,
        "diagnostics": diagnostics,
        "trace": append_trace(
            state,
            "llm_generation",
            "completed",
            f"structured report generated with {len(report.source_citations)} citations",
        ),
    }


def build_retrieval_query(state: RagGraphState) -> str:
    request = state["request"]
    return " ".join(
        [
            *state["normalized_tickers"],
            request.question,
            request.report_type.value.lower().replace("_", " "),
            request.time_horizon,
        ]
    )


def build_retrieval_metadata_filter(state: RagGraphState) -> ChunkMetadataFilter:
    return ChunkMetadataFilter(
        tickers=tuple(state.get("normalized_tickers", [])),
        source_types=tuple(state.get("source_filters", [])),
    )


def validate_report(state: RagGraphState) -> RagGraphState:
    response = state["response"]
    structured_report = state.get("structured_report", {})
    status = "completed" if response.summary and response.key_findings and structured_report else "failed"
    return {
        "trace": append_trace(state, "report_validation", status, "structured response schema validated"),
    }


def source_coverage(chunks: list[RetrievedChunk]) -> SourceCoverage:
    return SourceCoverage(
        sec_chunks=sum(1 for chunk in chunks if chunk["source_type"] == SourceFilter.SEC),
        news_chunks=sum(1 for chunk in chunks if chunk["source_type"] == SourceFilter.NEWS),
        earnings_chunks=sum(1 for chunk in chunks if chunk["source_type"] == SourceFilter.EARNINGS),
    )
