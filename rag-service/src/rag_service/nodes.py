from rag_service.models import (
    Citation,
    Diagnostics,
    GenerateReportResponse,
    SourceCoverage,
    SourceFilter,
)
from rag_service.state import AgentResult, RagGraphState, RetrievedChunk, TraceEvent


def append_trace(state: RagGraphState, node: str, status: str, detail: str) -> list[TraceEvent]:
    return [*state.get("trace", []), {"node": node, "status": status, "detail": detail}]


def plan_request(state: RagGraphState) -> RagGraphState:
    request = state["request"]
    source_filters = request.source_filters or SourceFilter.defaults()
    return {
        "normalized_tickers": [ticker.strip().upper() for ticker in request.tickers if ticker.strip()],
        "source_filters": list(dict.fromkeys(source_filters)),
        "diagnostics": {
            "mode": "mock",
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
    tickers = ", ".join(state["normalized_tickers"])
    evidence_id = f"{source_filter.value.lower()}-mock-001"
    result: AgentResult = {
        "source_type": source_filter,
        "status": "completed",
        "evidence_id": evidence_id,
        "title": f"{tickers} {source_filter.value} mock evidence",
        "url": f"https://example.com/{evidence_id}",
        "text": f"Mock {source_filter.value} evidence for {tickers}.",
    }
    return {
        "agent_results": [*state.get("agent_results", []), result],
        "trace": append_trace(state, f"{source_filter.value.lower()}_agent", "completed", "mock evidence created"),
    }


def retrieve_chunks(state: RagGraphState) -> RagGraphState:
    chunks: list[RetrievedChunk] = [
        {
            "evidence_id": result["evidence_id"],
            "source_type": result["source_type"],
            "title": result["title"],
            "url": result["url"],
            "text": result["text"],
            "score": 1.0 - index * 0.05,
        }
        for index, result in enumerate(state.get("agent_results", []))
    ]
    diagnostics = {**state.get("diagnostics", {}), "retrievalStatus": "completed"}
    return {
        "retrieved_chunks": chunks,
        "diagnostics": diagnostics,
        "trace": append_trace(state, "hybrid_retriever", "completed", f"retrieved {len(chunks)} chunks"),
    }


def rerank_chunks(state: RagGraphState) -> RagGraphState:
    chunks = sorted(state.get("retrieved_chunks", []), key=lambda chunk: chunk["score"], reverse=True)
    return {
        "retrieved_chunks": chunks,
        "trace": append_trace(state, "reranker", "completed", "ranked candidate chunks"),
    }


def build_context(state: RagGraphState) -> RagGraphState:
    selected_context = state.get("retrieved_chunks", [])[:6]
    return {
        "selected_context": selected_context,
        "trace": append_trace(state, "context_builder", "completed", f"selected {len(selected_context)} chunks"),
    }


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
        )
        for chunk in selected_context
    ]
    diagnostics = {
        **state.get("diagnostics", {}),
        "ragServiceStatus": "completed",
        "generationStatus": "completed",
    }
    response = GenerateReportResponse(
        summary=f"Mock {request.report_type.value.lower().replace('_', ' ')} generated for {tickers}.",
        key_findings=[chunk["text"] for chunk in selected_context],
        citations=citations,
        source_coverage=source_coverage(selected_context),
        diagnostics=Diagnostics(**diagnostics),
    )
    return {
        "response": response,
        "diagnostics": diagnostics,
        "trace": append_trace(state, "llm_generation", "completed", "mock report generated"),
    }


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
