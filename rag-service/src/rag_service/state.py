from typing import NotRequired, TypedDict

from rag_service.models import GenerateReportRequest, GenerateReportResponse, SourceFilter


class AgentResult(TypedDict):
    source_id: str
    chunk_id: str
    source_type: SourceFilter
    status: str
    evidence_id: str
    title: str
    url: str
    section: str
    text: str
    content_hash: str
    metadata: NotRequired[dict[str, str]]


class RetrievedChunk(TypedDict):
    source_id: str
    chunk_id: str
    evidence_id: str
    source_type: SourceFilter
    title: str
    url: str
    section: str
    text: str
    content_hash: str
    score: float
    rank: NotRequired[int]
    bm25_score: NotRequired[float]
    vector_score: NotRequired[float]
    fusion_score: NotRequired[float]
    matched_by: NotRequired[list[str]]
    filter_path: NotRequired[list[str]]
    reranker_score: NotRequired[float]
    reranker_rank: NotRequired[int]
    reranker_status: NotRequired[str]
    low_confidence: NotRequired[bool]
    context_rank: NotRequired[int]
    context_citation_id: NotRequired[str]
    context_span_start_token: NotRequired[int]
    context_span_end_token: NotRequired[int]
    context_token_count: NotRequired[int]
    context_truncated: NotRequired[bool]
    evidence_signal: NotRequired[str]
    materiality_score: NotRequired[float]
    recency_score: NotRequired[float]
    metadata: NotRequired[dict[str, str]]


class TraceEvent(TypedDict):
    node: str
    status: str
    detail: str


class RagGraphState(TypedDict):
    request: GenerateReportRequest
    normalized_tickers: NotRequired[list[str]]
    source_filters: NotRequired[list[SourceFilter]]
    agent_results: NotRequired[list[AgentResult]]
    retrieved_chunks: NotRequired[list[RetrievedChunk]]
    retrieval_diagnostics: NotRequired[list[dict[str, object]]]
    rerank_diagnostics: NotRequired[list[dict[str, object]]]
    selected_context: NotRequired[list[RetrievedChunk]]
    context_diagnostics: NotRequired[list[dict[str, object]]]
    context_citation_map: NotRequired[list[dict[str, object]]]
    structured_report: NotRequired[dict[str, object]]
    generation_prompt: NotRequired[str]
    generation_warnings: NotRequired[list[str]]
    diagnostics: NotRequired[dict[str, str]]
    trace: NotRequired[list[TraceEvent]]
    response: NotRequired[GenerateReportResponse]
