from dataclasses import asdict

from rag_service.documents import ChunkMetadataFilter
from rag_service.models import (
    Citation,
    Diagnostics,
    GenerateReportResponse,
    SourceCoverage,
    SourceFilter,
)
from rag_service.retrieval import retrieve_agent_results
from rag_service.source_memory import LocalSourceMemory
from rag_service.state import AgentResult, RagGraphState, RetrievedChunk, TraceEvent

SOURCE_MEMORY = LocalSourceMemory()


def append_trace(state: RagGraphState, node: str, status: str, detail: str) -> list[TraceEvent]:
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
    chunks = sorted(state.get("retrieved_chunks", []), key=lambda chunk: chunk["score"], reverse=True)
    return {
        "retrieved_chunks": chunks,
        "trace": append_trace(state, "reranker", "completed", "ranked candidate chunks"),
    }


def build_context(state: RagGraphState) -> RagGraphState:
    selected_context = select_context_chunks(
        state.get("retrieved_chunks", []),
        state.get("source_filters", SourceFilter.defaults()),
    )
    return {
        "selected_context": selected_context,
        "trace": append_trace(state, "context_builder", "completed", f"selected {len(selected_context)} chunks"),
    }


def select_context_chunks(
    chunks: list[RetrievedChunk],
    source_filters: list[SourceFilter],
    max_chunks: int = 6,
) -> list[RetrievedChunk]:
    selected: list[RetrievedChunk] = []
    selected_ids: set[str] = set()

    for source_filter in source_filters:
        source_chunk = next((chunk for chunk in chunks if chunk["source_type"] == source_filter), None)
        if source_chunk:
            selected.append(source_chunk)
            selected_ids.add(source_chunk["chunk_id"])

    for chunk in chunks:
        if len(selected) >= max_chunks:
            break
        if chunk["chunk_id"] in selected_ids:
            continue
        selected.append(chunk)
        selected_ids.add(chunk["chunk_id"])

    return selected[:max_chunks]


def generate_report(state: RagGraphState) -> RagGraphState:
    request = state["request"]
    tickers = ", ".join(state["normalized_tickers"])
    selected_context = state.get("selected_context", [])
    citations = [
        Citation(
            evidence_id=chunk["evidence_id"],
            source_type=chunk["source_type"],
            title=chunk["title"],
            url=chunk["url"],
            section=chunk["section"],
            source_metadata=chunk.get("metadata", {}),
        )
        for chunk in selected_context
    ]
    diagnostics = {
        **state.get("diagnostics", {}),
        "ragServiceStatus": "completed",
        "generationStatus": "completed",
    }
    response = GenerateReportResponse(
        summary=build_summary(request.report_type.value, tickers, selected_context),
        key_findings=build_key_findings(selected_context),
        citations=citations,
        source_coverage=source_coverage(selected_context),
        diagnostics=Diagnostics(**diagnostics),
    )
    return {
        "response": response,
        "diagnostics": diagnostics,
        "trace": append_trace(state, "llm_generation", "completed", "mock report generated"),
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


def build_summary(report_type: str, tickers: str, selected_context: list[RetrievedChunk]) -> str:
    report_label = report_type.lower().replace("_", " ")
    if not selected_context:
        return f"Local retrieval {report_label} generated for {tickers} with no matching evidence."
    return (
        f"Local retrieval {report_label} generated for {tickers} "
        f"using {len(selected_context)} ranked evidence chunks."
    )


def build_key_findings(selected_context: list[RetrievedChunk]) -> list[str]:
    if not selected_context:
        return ["No local evidence matched the requested tickers and source filters."]
    return [
        f"{chunk['source_type'].value} evidence ({chunk['section']}): {chunk['text']}"
        for chunk in selected_context
    ]


def validate_report(state: RagGraphState) -> RagGraphState:
    response = state["response"]
    status = "completed" if response.summary and response.key_findings else "failed"
    return {
        "trace": append_trace(state, "report_validation", status, "response schema validated"),
    }


def source_coverage(chunks: list[RetrievedChunk]) -> SourceCoverage:
    return SourceCoverage(
        sec_chunks=sum(1 for chunk in chunks if chunk["source_type"] == SourceFilter.SEC),
        news_chunks=sum(1 for chunk in chunks if chunk["source_type"] == SourceFilter.NEWS),
        earnings_chunks=sum(1 for chunk in chunks if chunk["source_type"] == SourceFilter.EARNINGS),
    )
