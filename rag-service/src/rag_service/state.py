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
    selected_context: NotRequired[list[RetrievedChunk]]
    diagnostics: NotRequired[dict[str, str]]
    trace: NotRequired[list[TraceEvent]]
    response: NotRequired[GenerateReportResponse]
